"""
pn05 主清洗器

协调各个规范化器和噪声过滤器，提供统一的 clean_article() 入口。
从 article_texts 读取 raw_text，清洗后通过 ArticleRepository 写入 cleaned_text。
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

from pn05.models import CleanConfig, CleanResult
from pn05.normalizer import (
    detect_and_clean_encoding,
    normalize_fullwidth,
    normalize_whitespace,
    remove_html_residue,
)
from pn05.noise_rules import filter_noise_lines, filter_noise_regex

logger = logging.getLogger(__name__)

__all__ = ["clean_article", "CleanConfig"]


def clean_article(
    article_id: int,
    session: Any,
    *,
    config: CleanConfig | None = None,
) -> str:
    """
    清洗单篇文章的 raw_text，写入 cleaned_text。

    流程:
    1. 从 article_texts 读取 raw_text
    2. 编码检测与修复
    3. HTML 残留移除
    4. 噪声行过滤（关键词 + 正则段落）
    5. 低密度块过滤（页眉/页脚）
    6. 空白规范化 + 全半角转换
    7. 写入 cleaned_text，更新 status=2 + task_log

    Args:
        article_id: 文章 ID
        session: SQLAlchemy Session
        config: 清洗配置

    Returns:
        str: 清洗后的 cleaned_text

    Raises:
        ValueError: raw_text 为空或清洗后为空
    """
    from back_end.app.repositories.articles import ArticleRepository

    config = config or CleanConfig()
    repo = ArticleRepository(session)
    start_time = time.monotonic()

    # 1. 读取 raw_text
    article = repo.get_article_detail(article_id)
    if article is None or article.text is None:
        raise _handle_failure(repo, article_id, "raw_text 不存在")

    raw_text = article.text.raw_text or ""
    if not raw_text.strip():
        raise _handle_failure(repo, article_id, "raw_text 为空")

    raw_length = len(raw_text)
    result = CleanResult(raw_length=raw_length)

    try:
        # 2. 编码检测与修复
        text = detect_and_clean_encoding(raw_text)

        # 3. HTML 残留移除
        if config.remove_html_residue:
            text = remove_html_residue(text)

        # 4. 噪声行过滤
        if config.filter_noise_lines:
            lines = text.split("\n")
            lines, noise_removed = filter_noise_lines(lines)
            text = "\n".join(lines)
            result.noise_lines_removed = noise_removed

            # 正则段落模式
            text, regex_removed = filter_noise_regex(text)
            result.noise_lines_removed += (1 if regex_removed > 0 else 0)

        # 5. 低密度块过滤（页眉/页脚）
        if config.filter_low_density:
            text, low_density_chars = _filter_low_density(text, config)
            result.low_density_removed = low_density_chars

        # 6. 空白规范化 + 全半角
        if config.normalize_whitespace:
            text = normalize_whitespace(text)
        if config.normalize_fullwidth:
            text = normalize_fullwidth(text)

        # 7. 后处理：去除首尾空白 + 合并多余空行
        text = text.strip()
        text = re.sub(r"\n{3,}", "\n\n", text)

        cleaned_length = len(text)
        result.cleaned_length = cleaned_length

        # 清洗比例检查
        if raw_length > 0:
            result.removal_ratio = (raw_length - cleaned_length) / raw_length
            if result.removal_ratio < 0.05:
                logger.warning("article_id=%s: 几乎无清洗效果 (ratio=%.3f)", article_id, result.removal_ratio)
            elif result.removal_ratio > 0.95:
                logger.warning("article_id=%s: 清洗比例异常高 (ratio=%.3f)，可能过度清洗", article_id, result.removal_ratio)

        # 空结果检查
        if not text.strip():
            raise ValueError("清洗后文本为空")

        # 截断保护
        if len(text) > config.max_text_length:
            text = text[: config.max_text_length] + f"\n\n[文本过长，已截断，原长度: {len(text)} 字符]"

        # 8. 写入数据库
        repo.save_cleaned_text(article_id=article_id, cleaned_text=text)
        result.duration_ms = int((time.monotonic() - start_time) * 1000)
        repo.save_task_log(
            article_id=article_id,
            stage="cleaner",
            status="success",
            message=result.summary(),
            duration_ms=result.duration_ms,
        )

        logger.info("清洗完成 article_id=%s: %s", article_id, result.summary())
        return text

    except ValueError:
        raise
    except Exception as exc:
        result.duration_ms = int((time.monotonic() - start_time) * 1000)
        raise _handle_failure(
            repo, article_id,
            f"清洗异常: {exc}",
            duration_ms=result.duration_ms,
        ) from exc


def _filter_low_density(text: str, config: CleanConfig) -> tuple[str, int]:
    """
    基于文本密度剔除低质量块（页眉、页脚、导航）。

    算法：
    1. 按 \\n\\n 分段
    2. 对每段计算中文字符占比
    3. 密度 < min_density_ratio 的段视为噪声 → 移除
    """
    paragraphs = text.split("\n\n")
    kept: list[str] = []
    removed_chars = 0

    for para in paragraphs:
        stripped = para.strip()
        if not stripped:
            kept.append(para)
            continue

        # 短段落：检查是否值得保留
        if len(stripped) < config.min_paragraph_chars:
            removed_chars += len(para)
            continue

        # 计算中文密度
        chinese_chars = len(re.findall(r"[一-鿿]", stripped))
        total_chars = len(stripped.replace(" ", ""))
        density = chinese_chars / max(total_chars, 1)

        if density < config.min_density_ratio:
            removed_chars += len(para)
        else:
            kept.append(para)

    return "\n\n".join(kept), removed_chars


def _handle_failure(
    repo: Any,
    article_id: int,
    message: str,
    duration_ms: int | None = None,
) -> ValueError:
    """统一处理清洗失败。"""
    try:
        repo.mark_failed(
            article_id=article_id,
            stage="cleaner",
            message=message,
            duration_ms=duration_ms,
        )
    except Exception as log_exc:
        logger.error("写入失败日志时异常: %s", log_exc)
    return ValueError(message)
