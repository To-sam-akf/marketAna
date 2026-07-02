from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from back_end.app.core.database import Base
from back_end.app.core.status import ARTICLE_STATUS_VALUES, ArticleProcessingStatus


TEXT_BODY = Text().with_variant(LONGTEXT, "mysql")
DIRECTION_VALUES = ("看涨", "看跌", "中性")
ANALYSIS_METHOD_VALUES = ("rule", "llm", "manual")


class Article(Base):
    __tablename__ = "articles"
    __table_args__ = (
        CheckConstraint(
            f"status in {ARTICLE_STATUS_VALUES}",
            name="ck_articles_status",
        ),
        Index("ix_articles_status_created_at", "status", "created_at"),
        Index("ix_articles_company", "company"),
        Index("ix_articles_publish_time", "publish_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    company: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    publish_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=ArticleProcessingStatus.PENDING.value,
        index=True,
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    text: Mapped[Optional["ArticleText"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        uselist=False,
    )
    analysis_result: Mapped[Optional["AnalysisResult"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        uselist=False,
    )
    task_logs: Mapped[list["TaskLog"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )
    manual_confirmations: Mapped[list["ManualConfirmation"]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
    )


class ArticleText(Base):
    __tablename__ = "article_texts"
    __table_args__ = (
        UniqueConstraint("article_id", name="uq_article_texts_article_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_text: Mapped[str | None] = mapped_column(TEXT_BODY, nullable=True)
    cleaned_text: Mapped[str | None] = mapped_column(TEXT_BODY, nullable=True)
    raw_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleaned_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parser_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    article: Mapped[Article] = relationship(back_populates="text")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        UniqueConstraint("article_id", name="uq_analysis_results_article_id"),
        CheckConstraint(
            f"direction in {DIRECTION_VALUES}",
            name="ck_analysis_results_direction",
        ),
        CheckConstraint(
            "confidence >= 0 and confidence <= 1",
            name="ck_analysis_results_confidence",
        ),
        CheckConstraint(
            f"analysis_method in {ANALYSIS_METHOD_VALUES}",
            name="ck_analysis_results_method",
        ),
        Index("ix_analysis_results_product", "product"),
        Index("ix_analysis_results_direction", "direction"),
        Index("ix_analysis_results_product_direction", "product", "direction"),
        Index("ix_analysis_results_analysis_time", "analysis_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product: Mapped[str] = mapped_column(String(128), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    analysis_method: Mapped[str] = mapped_column(String(32), nullable=False)
    need_manual_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    analysis_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    article: Mapped[Article] = relationship(back_populates="analysis_result")


class TaskLog(Base):
    __tablename__ = "task_logs"
    __table_args__ = (
        Index("ix_task_logs_article_stage", "article_id", "stage"),
        Index("ix_task_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    article: Mapped[Article | None] = relationship(back_populates="task_logs")


class ManualConfirmation(Base):
    __tablename__ = "manual_confirmations"
    __table_args__ = (
        CheckConstraint(
            f"confirmed_direction in {DIRECTION_VALUES}",
            name="ck_manual_confirmations_direction",
        ),
        CheckConstraint(
            "confirmed_confidence >= 0 and confirmed_confidence <= 1",
            name="ck_manual_confirmations_confidence",
        ),
        Index("ix_manual_confirmations_confirmed_at", "confirmed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    original_product: Mapped[str | None] = mapped_column(String(128), nullable=True)
    original_direction: Mapped[str | None] = mapped_column(String(16), nullable=True)
    original_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confirmed_product: Mapped[str] = mapped_column(String(128), nullable=False)
    confirmed_direction: Mapped[str] = mapped_column(String(16), nullable=False)
    confirmed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    confirmed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    article: Mapped[Article] = relationship(back_populates="manual_confirmations")
