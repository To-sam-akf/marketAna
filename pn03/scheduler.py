"""
pn03 核心调度器

Scheduler 是 pn03 的唯一对外接口类。它封装了：
- 定时后台调度（APScheduler BackgroundScheduler）
- 手动单次扫描（scan_and_dispatch）
- 并发安全（通过 Repository 的行级锁）
- 扫描级汇总日志

Pipeline 回调通过函数注入，pn03 不直接依赖 pn04-pn07。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler

from pn03.models import ScanResult

logger = logging.getLogger(__name__)

# Pipeline 回调类型：(article_id, session) -> bool
PipelineCallback = Callable[[int, Any], bool]
# Session 工厂类型
SessionFactory = Callable[[], Any]


def noop_callback(article_id: int, session: Any) -> bool:
    """无操作回调，用于测试和占位。

    仅标记文章为成功，不做实际处理。
    注意：此回调需要调用方在外部持有 repository。
    """
    from back_end.app.repositories.articles import ArticleRepository

    repo = ArticleRepository(session)
    try:
        repo.save_task_log(
            article_id=article_id,
            stage="scheduler",
            status="success",
            message="noop callback (pipeline not wired)",
        )
    except Exception:
        pass
    return True


class Scheduler:
    """定时调度器。

    定时扫描 status=0 的文章，逐条调用 pipeline_callback 进行处理。

    Usage:
        from pn03 import Scheduler, ScanResult

        def my_pipeline(article_id, session) -> bool:
            # ... 完整的解析→清洗→规则→LLM 流程
            return True

        scheduler = Scheduler(
            session_factory=lambda: next(get_session()),
            pipeline_callback=my_pipeline,
            batch_size=20,
            poll_interval_seconds=300,
        )
        scheduler.start()
        # ... 应用运行中 ...
        scheduler.stop()
    """

    def __init__(
        self,
        session_factory: SessionFactory,
        pipeline_callback: PipelineCallback | None = None,
        *,
        batch_size: int = 20,
        poll_interval_seconds: int = 300,
        timezone: str = "Asia/Shanghai",
    ) -> None:
        """
        Args:
            session_factory: 返回 SQLAlchemy Session 的可调用对象
            pipeline_callback: 处理单篇文章的回调 (article_id, session) -> bool
            batch_size: 每次扫描取出的最大文章数
            poll_interval_seconds: 定时扫描间隔（秒）
            timezone: 调度器时区
        """
        self._session_factory = session_factory
        self._pipeline_callback = pipeline_callback or noop_callback
        self._batch_size = batch_size
        self._poll_interval_seconds = poll_interval_seconds
        self._timezone = timezone

        self._scheduler = BackgroundScheduler(timezone=timezone)
        self._scheduler.configure(
            job_defaults={
                "coalesce": True,       # 合并积压任务
                "max_instances": 1,     # 单实例，避免自己重叠
            }
        )
        self._running = False

    # ---- 公共方法 ----

    def scan_and_dispatch(self) -> ScanResult:
        """
        手动执行一次扫描和分发。

        这是调度器的核心逻辑，也是定时任务和手动触发的共同入口。

        Returns:
            ScanResult: 本轮扫描的统计结果
        """
        from back_end.app.repositories.articles import ArticleRepository

        start = time.monotonic()
        session = self._session_factory()
        repo = ArticleRepository(session)
        scan_result = ScanResult()

        try:
            # 1. 查询待处理文章（带行级锁）
            articles = repo.get_pending_articles(
                limit=self._batch_size,
                lock=True,
            )
            scan_result.scanned = len(articles)

            if not articles:
                scan_result.message = "no pending articles"
                scan_result.duration_ms = int((time.monotonic() - start) * 1000)
                repo.save_task_log(
                    article_id=None,
                    stage="scheduler",
                    status="ok",
                    message=f"扫描完成：无待处理文章",
                    duration_ms=scan_result.duration_ms,
                )
                session.commit()
                logger.debug("扫描完成：无待处理文章")
                return scan_result

            logger.info("扫描到 %d 篇待处理文章，开始分发", len(articles))
            scan_result.triggered = len(articles)

            # 2. 逐条处理
            for article in articles:
                article_id = article.id
                article_start = time.monotonic()

                try:
                    success = self._pipeline_callback(article_id, session)
                    article_ms = int((time.monotonic() - article_start) * 1000)

                    if success:
                        scan_result.succeeded += 1
                    else:
                        scan_result.failed += 1
                        repo.save_task_log(
                            article_id=article_id,
                            stage="scheduler",
                            status="failed",
                            message="pipeline 回调返回 False",
                            duration_ms=article_ms,
                        )

                except Exception as exc:
                    scan_result.failed += 1
                    article_ms = int((time.monotonic() - article_start) * 1000)
                    logger.exception(
                        "pipeline 执行失败 article_id=%s, duration=%sms",
                        article_id, article_ms,
                    )
                    try:
                        repo.save_task_log(
                            article_id=article_id,
                            stage="scheduler",
                            status="failed",
                            message=f"pipeline 异常: {exc}",
                            duration_ms=article_ms,
                        )
                    except Exception:
                        logger.error("写入失败日志时异常", exc_info=True)

            # 3. 提交并写扫描汇总日志
            scan_result.duration_ms = int((time.monotonic() - start) * 1000)
            scan_result.message = scan_result.summary()

            repo.save_task_log(
                article_id=None,
                stage="scheduler",
                status="ok",
                message=scan_result.message,
                duration_ms=scan_result.duration_ms,
            )
            session.commit()
            logger.info("扫描完成: %s", scan_result.message)

        except Exception as exc:
            session.rollback()
            scan_result.duration_ms = int((time.monotonic() - start) * 1000)
            scan_result.message = f"扫描异常: {exc}"
            logger.exception("调度器扫描异常")
        finally:
            session.close()

        return scan_result

    def start(self) -> None:
        """
        启动后台定时调度。

        会注册一个 interval 定时任务，并启动 APScheduler。
        如果已经启动，调用此方法无效果。
        """
        if self._running:
            logger.warning("调度器已在运行中，忽略重复 start")
            return

        self._scheduler.add_job(
            self.scan_and_dispatch,
            trigger="interval",
            seconds=self._poll_interval_seconds,
            id="pn03_article_pipeline",
            name="pn03_article_pipeline",
            replace_existing=True,
        )
        self._scheduler.start()
        self._running = True
        logger.info(
            "pn03 调度器已启动，间隔=%ss, 批次=%s, 时区=%s",
            self._poll_interval_seconds,
            self._batch_size,
            self._timezone,
        )

    def stop(self, *, wait: bool = True) -> None:
        """
        停止后台调度器。

        Args:
            wait: 是否等待当前正在执行的任务完成
        """
        if not self._running:
            return
        self._scheduler.shutdown(wait=wait)
        self._running = False
        logger.info("pn03 调度器已停止")

    # ---- 属性 ----

    @property
    def is_running(self) -> bool:
        """调度器是否正在运行。"""
        return self._running

    @property
    def batch_size(self) -> int:
        return self._batch_size

    @property
    def poll_interval_seconds(self) -> int:
        return self._poll_interval_seconds
