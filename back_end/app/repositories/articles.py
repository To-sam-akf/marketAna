"""
文章仓库层 - 封装 Article 相关的所有数据库操作
包括：文章 CRUD、文本处理、分析结果存储、状态管理、任务日志、趋势查询等
"""
from datetime import datetime, time
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session, selectinload

from back_end.app.core.exceptions import AppException, ErrorCode
from back_end.app.core.status import ARTICLE_STATUS_VALUES, ArticleProcessingStatus
from back_end.app.models import (
    ANALYSIS_METHOD_VALUES,
    DIRECTION_VALUES,
    AnalysisResult,
    Article,
    ArticleText,
    ManualConfirmation,
    TaskLog,
)
from back_end.app.repositories.base import BaseRepository


class ArticleRepository(BaseRepository):
    """文章数据仓库，提供文章全生命周期的数据访问方法"""

    def __init__(self, session: Session) -> None:
        super().__init__(session)
        
    # 向articles表中插入一条新记录
    def create_article(
        self,
        *,
        title: str,
        source: str | None = None,
        company: str | None = None,
        file_url: str | None = None,
        file_type: str | None = None,
        publish_time: datetime | None = None,
    ) -> Article:
        """创建新文章记录。

        Args:
            title:       文章标题
            source:      文章来源
            company:     关联公司名称
            file_url:    上传文件地址
            file_type:   文件类型（如 pdf、docx）
            publish_time:文章发布时间

        Returns:
            创建的 Article 实例
        """
        article = Article(
            title=title,
            source=source,
            company=company,
            file_url=file_url,
            file_type=file_type,
            publish_time=publish_time,
        )
        self.session.add(article)
        self.session.flush()
        return article

    def get_article(self, article_id: int) -> Article | None:
        """根据 ID 查询单篇文章（不含关联数据）。"""
        return self.session.scalar(select(Article).where(Article.id == article_id))

    def get_article_detail(self, article_id: int) -> Article | None:
        """根据 ID 查询文章详情，同时加载关联的文本、分析结果、任务日志、人工确认记录。"""
        return self.session.scalar(
            select(Article)
            .options(
                selectinload(Article.text),
                selectinload(Article.analysis_result),
                selectinload(Article.task_logs),
                selectinload(Article.manual_confirmations),
            )
            .where(Article.id == article_id)
        )

    def require_article(self, article_id: int) -> Article:
        """根据 ID 查找文章，不存在则抛出 404 异常。"""
        article = self.get_article(article_id)
        if article is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="Article not found",
                detail={"article_id": article_id},
                status_code=404,
            )
        return article

    def get_pending_articles(self, limit: int, *, lock: bool = False) -> list[Article]:
        """获取待处理的文章队列。

        Args:
            limit: 最大获取数量
            lock:  是否对选中记录加锁（防止并发重复处理）
                   仅在支持行级锁的数据库（MySQL/PostgreSQL）中生效

        Returns:
            待处理的 Article 列表，按创建时间升序排列
        """
        stmt = (
            select(Article)
            .where(Article.status == ArticleProcessingStatus.PENDING.value)
            .order_by(Article.created_at.asc(), Article.id.asc())
            .limit(limit)
        )
        if lock and self._supports_skip_locked():
            stmt = stmt.with_for_update(skip_locked=True)
        return list(self.session.scalars(stmt).all())

    def save_raw_text(
        self,
        article_id: int,
        raw_text: str,
        *,
        parser_type: str | None = None,
    ) -> ArticleText:
        """保存从文件提取的原始文本。

        Args:
            article_id:  文章 ID
            raw_text:    原始文本内容
            parser_type: 文本解析器类型

        Returns:
            更新后的 ArticleText 实例
        """
        self.require_article(article_id)
        article_text = self._get_or_create_article_text(article_id)
        article_text.raw_text = raw_text
        article_text.raw_length = len(raw_text)
        article_text.parser_type = parser_type
        self.update_status(article_id, ArticleProcessingStatus.PARSED)
        self.session.flush()
        return article_text

    def save_cleaned_text(self, article_id: int, cleaned_text: str) -> ArticleText:
        """保存清洗后的文本。

        Args:
            article_id:   文章 ID
            cleaned_text: 清洗后的文本内容

        Returns:
            更新后的 ArticleText 实例
        """
        self.require_article(article_id)
        article_text = self._get_or_create_article_text(article_id)
        article_text.cleaned_text = cleaned_text
        article_text.cleaned_length = len(cleaned_text)
        self.update_status(article_id, ArticleProcessingStatus.CLEANED)
        self.session.flush()
        return article_text

    def save_analysis_result(
        self,
        article_id: int,
        *,
        product: str,
        direction: str,
        reason: str | None,
        confidence: float,
        analysis_method: str,
        need_manual_review: bool = False,
        analysis_time: datetime | None = None,
        mark_stored: bool = True,
    ) -> AnalysisResult:
        """保存 LLM 分析结果。

        若该文章已有分析结果则更新，否则新建。
        同时可根据参数决定是否将文章状态标记为 STORED。

        Args:
            article_id:       文章 ID
            product:          产品名称
            direction:        市场方向（涨/跌等）
            reason:           分析原因
            confidence:       置信度（0 ~ 1）
            analysis_method:  分析方法（如 gpt4, claude 等）
            need_manual_review: 是否需要人工复核
            analysis_time:    分析时间
            mark_stored:      是否将文章状态标记为已存储

        Returns:
            保存后的 AnalysisResult 实例
        """
        self.require_article(article_id)
        self._validate_direction(direction)
        self._validate_confidence(confidence)
        self._validate_analysis_method(analysis_method)

        # 查询现有分析结果，存在则更新，不存在则新建
        result = self.session.scalar(
            select(AnalysisResult).where(AnalysisResult.article_id == article_id)
        )
        if result is None:
            result = AnalysisResult(article_id=article_id)
            self.session.add(result)

        result.product = product
        result.direction = direction
        result.reason = reason
        result.confidence = confidence
        result.analysis_method = analysis_method
        result.need_manual_review = need_manual_review
        if analysis_time is not None:
            result.analysis_time = analysis_time
        if mark_stored:
            self.update_status(article_id, ArticleProcessingStatus.STORED)
        self.session.flush()
        return result

    def update_status(
        self,
        article_id: int,
        status: ArticleProcessingStatus | int,
        *,
        error_msg: str | None = None,
    ) -> Article:
        """更新文章处理状态。

        Args:
            article_id: 文章 ID
            status:     目标状态（ArticleProcessingStatus 枚举或整数值）
            error_msg:  失败时的错误信息（仅在 status == FAILED 时写入）

        Returns:
            更新后的 Article 实例
        """
        article = self.require_article(article_id)
        status_value = int(status)
        if status_value not in ARTICLE_STATUS_VALUES:
            raise AppException(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid article status",
                detail={"status": status_value},
            )
        article.status = status_value
        article.error_msg = error_msg if status_value == ArticleProcessingStatus.FAILED else None
        self.session.flush()
        return article

    def mark_failed(
        self,
        article_id: int,
        *,
        stage: str,
        message: str,
        duration_ms: int | None = None,
    ) -> Article:
        """将文章标记为失败状态，并记录任务日志。

        Args:
            article_id:  文章 ID
            stage:       失败阶段
            message:     失败原因描述
            duration_ms: 耗时（毫秒）

        Returns:
            更新后的 Article 实例
        """
        article = self.update_status(
            article_id,
            ArticleProcessingStatus.FAILED,
            error_msg=message,
        )
        self.save_task_log(
            article_id=article_id,
            stage=stage,
            status="failed",
            message=message,
            duration_ms=duration_ms,
        )
        self.session.flush()
        return article

    def save_task_log(
        self,
        *,
        article_id: int | None,
        stage: str,
        status: str,
        message: str | None = None,
        duration_ms: int | None = None,
    ) -> TaskLog:
        """记录任务执行日志。

        Args:
            article_id:  关联的文章 ID（允许为 None，用于全局任务）
            stage:       任务阶段
            status:      状态（如 success / failed）
            message:     日志消息
            duration_ms: 耗时（毫秒）

        Returns:
            创建的 TaskLog 实例
        """
        if article_id is not None:
            self.require_article(article_id)
        log = TaskLog(
            article_id=article_id,
            stage=stage,
            status=status,
            message=message,
            duration_ms=duration_ms,
        )
        self.session.add(log)
        self.session.flush()
        return log

    def list_articles(
        self,
        *,
        product: str | None = None,
        company: str | None = None,
        direction: str | None = None,
        status: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Article], int]:
        """分页查询文章列表，支持多字段组合筛选。

        Args:
            product:    产品名称筛选
            company:    公司名称筛选
            direction:  市场方向筛选
            status:     文章状态筛选
            start_time: 发布时间范围（起始）
            end_time:   发布时间范围（截止）
            keyword:    关键词模糊搜索（匹配标题、来源、公司、分析原因）
            page:       页码（从 1 开始）
            page_size:  每页条数

        Returns:
            (文章列表, 总记录数)
        """
        stmt = self._article_filter_stmt(
            product=product,
            company=company,
            direction=direction,
            status=status,
            start_time=start_time,
            end_time=end_time,
            keyword=keyword,
        )
        total_stmt = stmt.with_only_columns(func.count(Article.id)).order_by(None)
        total = int(self.session.scalar(total_stmt) or 0)
        items = list(
            self.session.scalars(
                stmt.options(
                    selectinload(Article.analysis_result),
                    selectinload(Article.text),
                )
                .order_by(
                    Article.publish_time.is_(None),
                    Article.publish_time.desc(),
                    Article.created_at.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    def get_dashboard_summary(self, *, today: datetime | None = None) -> dict[str, Any]:
        """获取仪表盘概览统计数据。

        Args:
            today: 指定作为"今天"的日期（用于测试时注入），默认为当前时间

        Returns:
            dict 包含：
            - today_articles:         今日新增文章数
            - total_articles:         文章总数
            - success_count:          处理成功数
            - failed_count:           处理失败数
            - success_rate:           成功率
            - manual_review_count:    待人工复核数
            - direction_distribution: 各方向的预测分布
        """
        resolved_today = (today or datetime.now()).date()
        start = datetime.combine(resolved_today, time.min)
        end = datetime.combine(resolved_today, time.max)

        # 今日新增文章数
        today_count = int(
            self.session.scalar(
                select(func.count(Article.id)).where(
                    Article.created_at >= start,
                    Article.created_at <= end,
                )
            )
            or 0
        )
        # 成功存储数
        success_count = int(
            self.session.scalar(
                select(func.count(Article.id)).where(Article.status == ArticleProcessingStatus.STORED.value)
            )
            or 0
        )
        # 失败数
        failed_count = int(
            self.session.scalar(
                select(func.count(Article.id)).where(Article.status == ArticleProcessingStatus.FAILED.value)
            )
            or 0
        )
        # 文章总数
        total_count = int(self.session.scalar(select(func.count(Article.id))) or 0)
        # 待人工复核数
        manual_review_count = int(
            self.session.scalar(
                select(func.count(AnalysisResult.id)).where(
                    AnalysisResult.need_manual_review.is_(True)
                )
            )
            or 0
        )
        # 方向分布统计
        direction_rows = self.session.execute(
            select(AnalysisResult.direction, func.count(AnalysisResult.id)).group_by(
                AnalysisResult.direction
            )
        ).all()
        direction_distribution = {direction: 0 for direction in DIRECTION_VALUES}
        direction_distribution.update({row[0]: int(row[1]) for row in direction_rows})

        return {
            "today_articles": today_count,
            "total_articles": total_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "success_rate": success_count / total_count if total_count else 0,
            "manual_review_count": manual_review_count,
            "direction_distribution": direction_distribution,
        }

    def get_trends(
        self,
        *,
        product: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """获取趋势分析数据，按日期、产品、方向分组统计预测数量。

        Args:
            product:    筛选特定产品
            start_time: 统计起始时间
            end_time:   统计截止时间

        Returns:
            列表，每项包含 date、product、direction、count 字段
        """
        # 日期取文章发布时间和分析时间的非空值
        trend_date = func.date(func.coalesce(Article.publish_time, AnalysisResult.analysis_time))
        stmt = (
            select(
                trend_date.label("date"),
                AnalysisResult.product,
                AnalysisResult.direction,
                func.count(AnalysisResult.id).label("count"),
            )
            .join(Article, Article.id == AnalysisResult.article_id)
            .group_by("date", AnalysisResult.product, AnalysisResult.direction)
            .order_by("date", AnalysisResult.product)
        )
        if product:
            stmt = stmt.where(AnalysisResult.product == product)
        if start_time is not None:
            stmt = stmt.where(func.coalesce(Article.publish_time, AnalysisResult.analysis_time) >= start_time)
        if end_time is not None:
            stmt = stmt.where(func.coalesce(Article.publish_time, AnalysisResult.analysis_time) <= end_time)

        return [
            {
                "date": str(row.date),
                "product": row.product,
                "direction": row.direction,
                "count": int(row.count),
            }
            for row in self.session.execute(stmt).all()
        ]

    def confirm_result(
        self,
        result_id: int,
        *,
        product: str,
        direction: str,
        reason: str | None,
        confidence: float,
        confirmed_by: str | None = None,
        note: str | None = None,
    ) -> ManualConfirmation:
        """人工确认并修正分析结果。

        创建一条修正记录（ManualConfirmation），同时更新原分析结果的数据，
        并将文章状态置为 STORED。

        Args:
            result_id:     原分析结果 ID
            product:       确认后的产品名称
            direction:     确认后的方向
            reason:        确认后的原因
            confidence:    确认后的置信度
            confirmed_by:  确认人
            note:          备注说明

        Returns:
            创建的 ManualConfirmation 实例
        """
        self._validate_direction(direction)
        self._validate_confidence(confidence)
        result = self.session.scalar(
            select(AnalysisResult).where(AnalysisResult.id == result_id)
        )
        if result is None:
            raise AppException(
                code=ErrorCode.NOT_FOUND,
                message="Analysis result not found",
                detail={"result_id": result_id},
                status_code=404,
            )

        # 保存原始数据与修正后数据的对比记录
        confirmation = ManualConfirmation(
            article_id=result.article_id,
            original_product=result.product,
            original_direction=result.direction,
            original_reason=result.reason,
            original_confidence=result.confidence,
            confirmed_product=product,
            confirmed_direction=direction,
            confirmed_reason=reason,
            confirmed_confidence=confidence,
            confirmed_by=confirmed_by,
            note=note,
        )
        self.session.add(confirmation)

        # 用修正数据覆盖原分析结果
        result.product = product
        result.direction = direction
        result.reason = reason
        result.confidence = confidence
        result.analysis_method = "manual"
        result.need_manual_review = False
        self.update_status(result.article_id, ArticleProcessingStatus.STORED)
        self.session.flush()
        return confirmation

    # ==================== 私有辅助方法 ====================

    def _get_or_create_article_text(self, article_id: int) -> ArticleText:
        """获取或创建文章对应的 ArticleText 记录。"""
        article_text = self.session.scalar(
            select(ArticleText).where(ArticleText.article_id == article_id)
        )
        if article_text is None:
            article_text = ArticleText(article_id=article_id)
            self.session.add(article_text)
            self.session.flush()
        return article_text

    def _article_filter_stmt(
        self,
        *,
        product: str | None,
        company: str | None,
        direction: str | None,
        status: int | None,
        start_time: datetime | None,
        end_time: datetime | None,
        keyword: str | None,
    ) -> Select[tuple[Article]]:
        """构建文章列表的筛选查询语句。

        左连接 AnalysisResult 表，按传入条件动态拼接 WHERE 子句。
        """
        stmt = select(Article).outerjoin(AnalysisResult)
        if product:
            stmt = stmt.where(AnalysisResult.product == product)
        if company:
            stmt = stmt.where(Article.company == company)
        if direction:
            self._validate_direction(direction)
            stmt = stmt.where(AnalysisResult.direction == direction)
        if status is not None:
            if status not in ARTICLE_STATUS_VALUES:
                raise AppException(
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Invalid article status",
                    detail={"status": status},
                )
            stmt = stmt.where(Article.status == status)
        if start_time is not None:
            stmt = stmt.where(Article.publish_time >= start_time)
        if end_time is not None:
            stmt = stmt.where(Article.publish_time <= end_time)
        if keyword:
            pattern = f"%{keyword}%"
            stmt = stmt.where(
                or_(
                    Article.title.like(pattern),
                    Article.source.like(pattern),
                    Article.company.like(pattern),
                    AnalysisResult.reason.like(pattern),
                )
            )
        return stmt

    def _supports_skip_locked(self) -> bool:
        """检测当前数据库是否支持 SKIP LOCKED 语法。

        仅 MySQL 和 PostgreSQL 支持该特性，SQLite 不支持。
        """
        bind = self.session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        return dialect_name in {"mysql", "postgresql"}

    @staticmethod
    def _validate_direction(direction: str) -> None:
        """校验市场方向值是否在允许列表中。"""
        if direction not in DIRECTION_VALUES:
            raise AppException(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid direction",
                detail={"direction": direction, "allowed": DIRECTION_VALUES},
            )

    @staticmethod
    def _validate_analysis_method(analysis_method: str) -> None:
        """校验分析方法值是否在允许列表中。"""
        if analysis_method not in ANALYSIS_METHOD_VALUES:
            raise AppException(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid analysis method",
                detail={"analysis_method": analysis_method, "allowed": ANALYSIS_METHOD_VALUES},
            )

    @staticmethod
    def _validate_confidence(confidence: float) -> None:
        """校验置信度是否在 0 ~ 1 范围内。"""
        if confidence < 0 or confidence > 1:
            raise AppException(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid confidence",
                detail={"confidence": confidence},
            )
