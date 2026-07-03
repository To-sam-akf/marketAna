"""
pn03 Scheduler 单元测试

使用内存 SQLite + mock pipeline_callback 测试调度器的
扫描、分发、并发安全、异常处理和日志记录。
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from back_end.app.core.database import Base, create_database_tables
from back_end.app.core.status import ArticleProcessingStatus
from back_end.app.models.article import Article, TaskLog
from back_end.app.repositories.articles import ArticleRepository

from pn03.scheduler import Scheduler, noop_callback
from pn03.models import ScanResult


# ---- Fixtures ----

@pytest.fixture
def session_factory():
    """内存 SQLite 数据库 + Session 工厂。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_database_tables(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _factory() -> Session:
        return factory()

    _factory._engine = engine
    try:
        yield _factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _create_pending_articles(session: Session, count: int) -> list[Article]:
    """辅助函数：批量创建 PENDING 文章。"""
    repo = ArticleRepository(session)
    articles = []
    for i in range(count):
        article = repo.create_article(
            title=f"测试文章 {i+1}",
            source="日报",
            company="测试期货",
            file_type="html",
            file_url=f"/files/test_{i+1}.html",
            publish_time=datetime(2026, 7, 3, 10, i),
        )
        articles.append(article)
    session.commit()
    return articles


# ---- 测试：ScanResult ----

def test_scan_result_defaults():
    """ScanResult 默认值。"""
    r = ScanResult()
    assert r.scanned == 0
    assert r.ok is True
    assert r.empty is True


def test_scan_result_summary():
    """ScanResult 摘要格式。"""
    r = ScanResult(scanned=10, triggered=10, succeeded=8, failed=2, duration_ms=350)
    assert "10" in r.summary()
    assert "8" in r.summary()
    assert "2" in r.summary()


def test_scan_result_empty_summary():
    """空扫描摘要。"""
    r = ScanResult(duration_ms=15, message="no pending articles")
    assert "无待处理文章" in r.summary()


# ---- 测试：scan_and_dispatch ----

def test_scan_empty(session_factory):
    """无待处理文章时正常退出，记录日志。"""
    scheduler = Scheduler(
        session_factory=session_factory,
        batch_size=20,
    )
    result = scheduler.scan_and_dispatch()

    assert result.empty is True
    assert result.scanned == 0
    assert result.triggered == 0

    # 验证扫描日志
    session = session_factory()
    logs = session.query(TaskLog).filter(
        TaskLog.stage == "scheduler",
        TaskLog.article_id.is_(None),
    ).all()
    assert len(logs) >= 1
    session.close()


def test_scan_picks_batch_size(session_factory):
    """构造 25 条 PENDING，批次 20，只取前 20 条。"""
    session = session_factory()
    articles = _create_pending_articles(session, 25)
    session.close()

    processed_ids: list[int] = []

    def tracking_callback(article_id: int, sess: Session) -> bool:
        processed_ids.append(article_id)
        return True

    scheduler = Scheduler(session_factory, tracking_callback, batch_size=20)
    result = scheduler.scan_and_dispatch()

    assert result.scanned == 20
    assert result.triggered == 20
    assert result.succeeded == 20
    assert result.failed == 0
    assert len(processed_ids) == 20

    # 验证取的是前 20 条（按 created_at ASC）
    expected_ids = [a.id for a in articles[:20]]
    assert processed_ids == expected_ids


def test_scan_all_succeed(session_factory):
    """所有 pipeline 回调返回 True。"""
    session = session_factory()
    _create_pending_articles(session, 5)
    session.close()

    success_ids: list[int] = []

    def success_cb(aid, sess):
        success_ids.append(aid)
        return True

    scheduler = Scheduler(session_factory, success_cb, batch_size=20)
    result = scheduler.scan_and_dispatch()

    assert result.scanned == 5
    assert result.triggered == 5
    assert result.succeeded == 5
    assert result.failed == 0
    assert len(success_ids) == 5


def test_scan_mixed_results(session_factory):
    """部分成功部分失败，验证计数。"""
    session = session_factory()
    articles = _create_pending_articles(session, 6)
    session.close()

    fail_ids = {articles[1].id, articles[3].id, articles[5].id}

    def mixed_cb(aid, sess):
        if aid in fail_ids:
            return False
        return True

    scheduler = Scheduler(session_factory, mixed_cb, batch_size=20)
    result = scheduler.scan_and_dispatch()

    assert result.scanned == 6
    assert result.triggered == 6
    # False 返回不算异常，计入 failed
    assert result.failed == 3
    assert result.succeeded == 3


def test_scan_pipeline_exception(session_factory):
    """回调抛异常时 catch 并继续处理后续文章。"""
    session = session_factory()
    articles = _create_pending_articles(session, 5)
    session.close()

    fail_ids = {articles[1].id, articles[3].id}
    processed: list[int] = []

    def exception_cb(aid, sess):
        processed.append(aid)
        if aid in fail_ids:
            raise RuntimeError(f"mock failure for {aid}")
        return True

    scheduler = Scheduler(session_factory, exception_cb, batch_size=20)
    result = scheduler.scan_and_dispatch()

    # 所有 5 条都被处理（异常被 catch 不影响后续）
    assert len(processed) == 5
    assert result.triggered == 5
    assert result.succeeded == 3
    assert result.failed == 2

    # 验证失败的文章有 task_log
    session = session_factory()
    for fid in fail_ids:
        logs = session.query(TaskLog).filter(
            TaskLog.article_id == fid,
            TaskLog.status == "failed",
        ).all()
        assert len(logs) >= 1
    session.close()


def test_scan_does_not_touch_processed(session_factory):
    """只扫描 status=0 的文章，已处理的不会被选中。"""
    session = session_factory()
    repo = ArticleRepository(session)

    # 创建 3 条 PENDING + 2 条已处理
    pending = [repo.create_article(title=f"pending {i}") for i in range(3)]
    parsed = repo.create_article(title="parsed")
    repo.update_status(parsed.id, ArticleProcessingStatus.PARSED)
    failed = repo.create_article(title="failed")
    repo.mark_failed(failed.id, stage="parser", message="test")
    session.commit()
    session.close()

    processed: list[int] = []

    def cb(aid, sess):
        processed.append(aid)
        return True

    scheduler = Scheduler(session_factory, cb, batch_size=20)
    result = scheduler.scan_and_dispatch()

    assert result.scanned == 3
    pending_ids = {a.id for a in pending}
    assert set(processed) == pending_ids


def test_scan_result_duration(session_factory):
    """ScanResult 记录耗时。"""
    session = session_factory()
    _create_pending_articles(session, 2)
    session.close()

    scheduler = Scheduler(session_factory, batch_size=20)
    result = scheduler.scan_and_dispatch()

    assert result.duration_ms >= 0


# ---- 测试：noop_callback ----

def test_noop_callback(session_factory):
    """noop_callback 返回 True。"""
    session = session_factory()
    repo = ArticleRepository(session)
    article = repo.create_article(title="noop test")
    session.commit()
    session.close()

    session2 = session_factory()
    result = noop_callback(article.id, session2)
    session2.commit()

    assert result is True
    # 验证 task_log 写入
    logs = session2.query(TaskLog).filter(
        TaskLog.article_id == article.id,
        TaskLog.stage == "scheduler",
    ).all()
    assert len(logs) >= 1
    session2.close()


# ---- 测试：start / stop ----

def test_scheduler_start_stop(session_factory):
    """调度器正常启停。"""
    scheduler = Scheduler(session_factory, batch_size=20, poll_interval_seconds=9999)

    assert scheduler.is_running is False
    scheduler.start()
    assert scheduler.is_running is True
    scheduler.stop()
    assert scheduler.is_running is False


def test_scheduler_double_start(session_factory):
    """重复 start 不报错。"""
    scheduler = Scheduler(session_factory, batch_size=20, poll_interval_seconds=9999)
    scheduler.start()
    scheduler.start()  # 不应报错
    assert scheduler.is_running is True
    scheduler.stop()


# ---- 测试：并发安全 ----

def test_concurrent_scans_no_overlap(session_factory):
    """
    模拟两个 Scheduler 实例并发扫描（顺序执行），
    验证各自获取到不重叠的文章集合。

    在 SQLite 上 FOR UPDATE SKIP LOCKED 不支持，但测试通过
    事务隔离验证逻辑正确性。
    """
    session = session_factory()
    _create_pending_articles(session, 15)
    session.close()

    seen_a: list[int] = []
    seen_b: list[int] = []

    def cb_a(aid, sess):
        seen_a.append(aid)
        from back_end.app.repositories.articles import ArticleRepository
        repo = ArticleRepository(sess)
        repo.update_status(aid, ArticleProcessingStatus.PARSED)
        return True

    def cb_b(aid, sess):
        seen_b.append(aid)
        from back_end.app.repositories.articles import ArticleRepository
        repo = ArticleRepository(sess)
        repo.update_status(aid, ArticleProcessingStatus.PARSED)
        return True

    sched_a = Scheduler(session_factory, cb_a, batch_size=10)
    sched_b = Scheduler(session_factory, cb_b, batch_size=10)

    # 模拟两个调度器先后执行
    result_a = sched_a.scan_and_dispatch()
    result_b = sched_b.scan_and_dispatch()

    # A 取前 10 条，B 取剩余 5 条
    assert result_a.scanned == 10
    assert result_b.scanned == 5

    # 无重叠
    assert set(seen_a) & set(seen_b) == set()
    # 合计 15
    assert len(seen_a) + len(seen_b) == 15


# ---- 测试：属性 ----

def test_scheduler_properties():
    """Scheduler 属性正确返回。"""
    scheduler = Scheduler(
        lambda: None,
        batch_size=15,
        poll_interval_seconds=120,
    )
    assert scheduler.batch_size == 15
    assert scheduler.poll_interval_seconds == 120
    assert scheduler.is_running is False
