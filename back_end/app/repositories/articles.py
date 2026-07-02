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
    def __init__(self, session: Session) -> None:
        super().__init__(session)

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
        return self.session.scalar(select(Article).where(Article.id == article_id))

    def get_article_detail(self, article_id: int) -> Article | None:
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
        self.require_article(article_id)
        article_text = self._get_or_create_article_text(article_id)
        article_text.raw_text = raw_text
        article_text.raw_length = len(raw_text)
        article_text.parser_type = parser_type
        self.update_status(article_id, ArticleProcessingStatus.PARSED)
        self.session.flush()
        return article_text

    def save_cleaned_text(self, article_id: int, cleaned_text: str) -> ArticleText:
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
        self.require_article(article_id)
        self._validate_direction(direction)
        self._validate_confidence(confidence)
        self._validate_analysis_method(analysis_method)

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
                stmt.options(selectinload(Article.analysis_result))
                .order_by(Article.publish_time.desc().nullslast(), Article.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return items, total

    def get_dashboard_summary(self, *, today: datetime | None = None) -> dict[str, Any]:
        resolved_today = (today or datetime.now()).date()
        start = datetime.combine(resolved_today, time.min)
        end = datetime.combine(resolved_today, time.max)

        today_count = int(
            self.session.scalar(
                select(func.count(Article.id)).where(
                    Article.created_at >= start,
                    Article.created_at <= end,
                )
            )
            or 0
        )
        success_count = int(
            self.session.scalar(
                select(func.count(Article.id)).where(Article.status == ArticleProcessingStatus.STORED.value)
            )
            or 0
        )
        failed_count = int(
            self.session.scalar(
                select(func.count(Article.id)).where(Article.status == ArticleProcessingStatus.FAILED.value)
            )
            or 0
        )
        total_count = int(self.session.scalar(select(func.count(Article.id))) or 0)
        manual_review_count = int(
            self.session.scalar(
                select(func.count(AnalysisResult.id)).where(
                    AnalysisResult.need_manual_review.is_(True)
                )
            )
            or 0
        )
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

        result.product = product
        result.direction = direction
        result.reason = reason
        result.confidence = confidence
        result.analysis_method = "manual"
        result.need_manual_review = False
        self.update_status(result.article_id, ArticleProcessingStatus.STORED)
        self.session.flush()
        return confirmation

    def _get_or_create_article_text(self, article_id: int) -> ArticleText:
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
        bind = self.session.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        return dialect_name in {"mysql", "postgresql"}

    @staticmethod
    def _validate_direction(direction: str) -> None:
        if direction not in DIRECTION_VALUES:
            raise AppException(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid direction",
                detail={"direction": direction, "allowed": DIRECTION_VALUES},
            )

    @staticmethod
    def _validate_analysis_method(analysis_method: str) -> None:
        if analysis_method not in ANALYSIS_METHOD_VALUES:
            raise AppException(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid analysis method",
                detail={"analysis_method": analysis_method, "allowed": ANALYSIS_METHOD_VALUES},
            )

    @staticmethod
    def _validate_confidence(confidence: float) -> None:
        if confidence < 0 or confidence > 1:
            raise AppException(
                code=ErrorCode.VALIDATION_ERROR,
                message="Invalid confidence",
                detail={"confidence": confidence},
            )
