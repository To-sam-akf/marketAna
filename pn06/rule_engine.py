"""
pn06 规则识别引擎

识别期货品种、走势方向和置信度。
高置信（≥0.7）直接入库，低置信标记 need_llm 交由 pn07 处理。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from back_end.app.core.status import ArticleProcessingStatus

from pn06.confidence import calculate_confidence
from pn06.direction_rules import detect_direction, extract_reason
from pn06.models import RuleConfig, RuleResult
from pn06.product_dict import detect_products, get_primary_product

logger = logging.getLogger(__name__)

__all__ = ["analyze_article", "RuleConfig"]


def analyze_article(
    article_id: int,
    session: Any,
    *,
    config: RuleConfig | None = None,
) -> RuleResult:
    """
    对单篇文章的 cleaned_text 执行规则识别。

    流程:
    1. 读取 article_texts.cleaned_text
    2. 品种检测
    3. 方向检测
    4. 理由提取
    5. 置信度计算
    6. 高置信 → 直接入库 (mark_stored)
       低置信 → status=3, need_llm=True
    7. 写 task_log

    Args:
        article_id: 文章 ID
        session: SQLAlchemy Session
        config: 规则配置

    Returns:
        RuleResult: 识别结果
    """
    from back_end.app.repositories.articles import ArticleRepository

    config = config or RuleConfig()
    repo = ArticleRepository(session)
    start_time = time.monotonic()

    # 1. 读取 cleaned_text
    article = repo.get_article_detail(article_id)
    if article is None or article.text is None:
        raise _fail(repo, article_id, "article 或 article_text 不存在")

    cleaned_text = article.text.cleaned_text or ""
    if not cleaned_text.strip():
        raise _fail(repo, article_id, "cleaned_text 为空")

    try:
        # 2. 品种检测
        _products = detect_products(cleaned_text)
        product = get_primary_product(cleaned_text)

        # 3. 方向检测
        dir_result = detect_direction(cleaned_text)

        # 4. 理由提取
        reason = extract_reason(cleaned_text, dir_result["direction"], config.reason_window)

        # 5. 置信度计算
        confidence = calculate_confidence(product, dir_result, config)

        # 6. 决策
        if confidence >= config.confidence_threshold and product and dir_result["direction"]:
            # 高置信 → 直接入库
            repo.save_analysis_result(
                article_id=article_id,
                product=product,
                direction=dir_result["direction"],
                reason=reason or f"规则识别: {dir_result['direction']}",
                confidence=confidence,
                analysis_method="rule",
                need_manual_review=False,
                mark_stored=True,
            )
            result = RuleResult(
                product=product,
                direction=dir_result["direction"],
                reason=reason,
                confidence=confidence,
                need_llm=False,
                detail=dir_result,
            )
        else:
            # 低置信 → status=3, 交由 LLM
            repo.update_status(article_id, ArticleProcessingStatus.RULE_ANALYZED)
            result = RuleResult(
                product=product,
                direction=dir_result["direction"],
                reason=reason,
                confidence=confidence,
                need_llm=True,
                detail=dir_result,
            )

        # 7. task_log
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        repo.save_task_log(
            article_id=article_id,
            stage="rule_engine",
            status="success",
            message=result.summary(),
            duration_ms=elapsed_ms,
        )

        logger.info("规则识别完成 article_id=%s: %s", article_id, result.summary())
        return result

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        raise _fail(repo, article_id, f"规则识别异常: {exc}", duration_ms=elapsed_ms) from exc


def _fail(repo: Any, article_id: int, msg: str, duration_ms: int | None = None) -> ValueError:
    try:
        repo.mark_failed(article_id=article_id, stage="rule_engine", message=msg, duration_ms=duration_ms)
    except Exception as e:
        logger.error("写入失败日志异常: %s", e)
    return ValueError(msg)
