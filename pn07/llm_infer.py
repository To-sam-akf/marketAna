"""
pn07 LLM 推理主入口

编排完整推理流程：读取文本→构建Prompt→调用LLM→解析JSON→入库。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from back_end.app.core.status import ArticleProcessingStatus

from pn07.json_parser import parse_llm_json
from pn07.models import InferResult, LLMConfig
from pn07.prompt_builder import build_messages

logger = logging.getLogger(__name__)

__all__ = ["infer_article", "LLMConfig"]


def infer_article(
    article_id: int,
    session: Any,
    *,
    config: LLMConfig | None = None,
) -> InferResult:
    """
    对单篇文章执行 LLM 推理。

    流程:
    1. 读取 article_texts.cleaned_text + article 元信息
    2. 构建 prompt
    3. 调用 LLM API（最多 3 次重试）
    4. 解析 JSON 响应
    5. 校验字段 + 方向枚举
    6. confidence < threshold → need_manual_review
    7. save_analysis_result(mark_stored=True)
    8. status → LLM_INFERRED → STORED

    Args:
        article_id: 文章 ID
        session: SQLAlchemy Session
        config: LLM 配置（None=从 Settings 自动读取）

    Returns:
        InferResult

    Raises:
        ValueError: 前序数据缺失（无 cleaned_text）
        RuntimeError: LLM 调用全部失败
    """
    from back_end.app.repositories.articles import ArticleRepository

    if config is None:
        config = LLMConfig.from_settings()

    repo = ArticleRepository(session)
    start_time = time.monotonic()

    # 1. 读取文章数据
    article = repo.get_article_detail(article_id)
    if article is None or article.text is None:
        raise _fail(repo, article_id, "article 或 article_text 不存在")

    cleaned_text = article.text.cleaned_text or ""
    if not cleaned_text.strip():
        raise _fail(repo, article_id, "cleaned_text 为空")

    # 上下文
    title = article.title or ""
    source = article.source or ""
    company = article.company or ""
    pub_time = str(article.publish_time) if article.publish_time else ""

    # 2. 构建 prompt
    messages = build_messages(
        cleaned_text,
        title=title,
        source=source,
        company=company,
        publish_time=pub_time,
        max_input_chars=config.max_input_chars,
    )

    # 3. 调用 LLM（含重试）
    from pn07.llm_client import LLMAPIClient

    client = LLMAPIClient(config)
    raw_response = ""
    retry_count = 0
    last_error = ""

    for attempt in range(config.max_retries + 1):
        try:
            raw_response = client.chat(messages, retries=0)
            retry_count = attempt
            last_error = ""
            break
        except Exception as exc:
            retry_count = attempt
            last_error = str(exc)
            if attempt < config.max_retries:
                logger.warning("LLM 调用失败 (attempt %s/%s): %s", attempt + 1, config.max_retries, exc)
                continue
            # 所有重试耗尽
            elapsed = int((time.monotonic() - start_time) * 1000)
            _fail(repo, article_id, f"LLM 调用失败（已重试 {config.max_retries} 次）: {last_error}", duration_ms=elapsed)
            return InferResult(
                error_msg=last_error,
                retry_count=retry_count,
                model=config.model,
                duration_ms=elapsed,
            )

    # 4. 解析 JSON
    parsed, errors = parse_llm_json(raw_response)

    # 5. 判定
    product = parsed.get("product")
    direction = parsed.get("direction")
    reason = parsed.get("reason", "")
    confidence = parsed.get("confidence", 0.0)
    need_manual = confidence < config.manual_review_threshold

    elapsed = int((time.monotonic() - start_time) * 1000)

    # 关键字段缺失 → 低置信入库
    if not product or not direction:
        logger.warning("LLM 输出关键字段缺失 article_id=%s: errors=%s", article_id, errors)
        need_manual = True

    try:
        # 6. 入库
        repo.update_status(article_id, ArticleProcessingStatus.LLM_INFERRED)
        repo.save_analysis_result(
            article_id=article_id,
            product=product or "未知",
            direction=direction or "中性",
            reason=reason or (f"LLM 推理结果。解析问题: {'; '.join(errors)}" if errors else ""),
            confidence=confidence,
            analysis_method="llm",
            need_manual_review=need_manual,
            mark_stored=True,
        )

        # 7. task_log
        repo.save_task_log(
            article_id=article_id,
            stage="llm_infer",
            status="success",
            message=(
                f"model={config.model} retries={retry_count} "
                f"product={product} direction={direction} confidence={confidence:.2f}"
            ),
            duration_ms=elapsed,
        )

    except Exception as exc:
        raise _fail(repo, article_id, f"LLM 结果入库失败: {exc}", duration_ms=elapsed) from exc

    logger.info("LLM 推理完成 article_id=%s: %s %s %.2f", article_id, product, direction, confidence)

    return InferResult(
        product=product,
        direction=direction,
        reason=reason,
        confidence=confidence,
        need_manual_review=need_manual,
        model=config.model,
        duration_ms=elapsed,
        retry_count=retry_count,
        error_msg=last_error,
        raw_response=raw_response,
    )


def _fail(repo: Any, article_id: int, msg: str, duration_ms: int | None = None) -> ValueError:
    try:
        repo.mark_failed(article_id=article_id, stage="llm_infer", message=msg, duration_ms=duration_ms)
    except Exception as e:
        logger.error("写入失败日志异常: %s", e)
    return ValueError(msg)
