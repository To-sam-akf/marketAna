"""
pn04 主解析器

协调各个子解析器，提供统一的 parse_article() 入口。
根据文章文件类型选择对应解析器，解析后将结果通过 ArticleRepository 写入数据库。
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

from pn04.exceptions import (
    EmptyContentError,
    FileNotFoundError_,
    FileReadError,
    OCRError,
    ParserError,
    UnsupportedFormatError,
)
from pn04.models import (
    EXTENSION_MAP,
    ParseConfig,
    ParserType,
    detect_parser_type,
)

logger = logging.getLogger(__name__)

__all__ = ["parse_article", "ParseConfig"]


def parse_article(
    article: Any,
    session: Any,
    *,
    config: ParseConfig | None = None,
    base_dir: str | None = None,
) -> str:
    """
    解析单篇文章的主入口。

    根据 article.file_type / file_url 选择解析器，解析文件，
    将 raw_text 通过 ArticleRepository 写入数据库，并更新文章状态。

    Args:
        article: Article ORM 对象，至少包含 id, file_url, file_type
        session: SQLAlchemy Session 对象
        config: 解析器配置，为 None 时使用默认配置
        base_dir: 文件基础目录，用于解析相对路径。
                  为 None 时默认使用当前工作目录。

    Returns:
        str: 解析后的 raw_text

    Raises:
        ParserError: 解析失败，已自动写入 error_msg + status=-1
    """
    from back_end.app.repositories.articles import ArticleRepository

    config = config or ParseConfig()
    repo = ArticleRepository(session)
    article_id = article.id
    file_url = getattr(article, "file_url", None)
    file_type = getattr(article, "file_type", None)

    if not file_url:
        raise _handle_failure(
            repo, article_id, "parser",
            "file_url 为空，无法解析",
        )

    # 解析文件路径
    file_path = _resolve_file_path(file_url, base_dir)

    # 检测解析器类型
    parser_type = detect_parser_type(file_type, file_url)
    if parser_type == ParserType.UNKNOWN:
        raise _handle_failure(
            repo, article_id, "parser",
            f"不支持的文件格式: file_type={file_type}, file_url={file_url}",
        )

    logger.info(
        "开始解析 article_id=%s, parser=%s, path=%s",
        article_id, parser_type.value, file_path,
    )
    start_time = time.monotonic()

    try:
        raw_text = _run_parser(parser_type, file_path, config)
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # 写入数据库
        repo.save_raw_text(
            article_id=article_id,
            raw_text=raw_text,
            parser_type=parser_type.value,
        )
        repo.save_task_log(
            article_id=article_id,
            stage="parser",
            status="success",
            message=f"parsed {parser_type.value}, {len(raw_text)} chars",
            duration_ms=elapsed_ms,
        )

        logger.info(
            "解析成功 article_id=%s, parser=%s, length=%s, duration=%sms",
            article_id, parser_type.value, len(raw_text), elapsed_ms,
        )
        return raw_text

    except (FileNotFoundError_, FileReadError, OCRError, EmptyContentError, UnsupportedFormatError) as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        raise _handle_failure(
            repo, article_id, "parser",
            str(exc),
            duration_ms=elapsed_ms,
        ) from exc
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.exception("解析器内部错误 article_id=%s", article_id)
        raise _handle_failure(
            repo, article_id, "parser",
            f"解析器内部错误: {exc}",
            duration_ms=elapsed_ms,
        ) from exc


def _resolve_file_path(file_url: str, base_dir: str | None = None) -> str:
    """
    解析文件路径。

    - 绝对路径直接返回
    - 相对路径基于 base_dir（默认为当前工作目录）拼接
    - file_url 可能是 URL 路径如 /files/report.pdf
    """
    # 去掉可能的 file:// 前缀
    if file_url.startswith("file://"):
        file_url = file_url[7:]

    # 绝对路径
    if os.path.isabs(file_url):
        return file_url

    # 基于 base_dir
    base = base_dir or os.getcwd()
    return os.path.join(base, file_url.lstrip("/"))


def _run_parser(parser_type: ParserType, file_path: str, config: ParseConfig) -> str:
    """选择并执行对应的子解析器。"""
    if parser_type == ParserType.PDF:
        from pn04.pdf_parser import PdfParser

        result = PdfParser(config=config).parse(file_path)
        return result.raw_text

    elif parser_type == ParserType.HTML:
        from pn04.html_parser import HtmlParser

        result = HtmlParser(config=config).parse(file_path)
        return result.raw_text

    elif parser_type == ParserType.IMAGE:
        from pn04.image_parser import ImageParser

        result = ImageParser(config=config).parse(file_path)
        return result.raw_text

    else:
        raise UnsupportedFormatError(file_url=file_path)


def _handle_failure(
    repo: Any,
    article_id: int,
    stage: str,
    message: str,
    duration_ms: int | None = None,
) -> ParserError:
    """
    统一处理解析失败：写入 error_msg、status=-1、task_log，
    并返回对应的 ParserError 异常。
    """
    try:
        repo.mark_failed(
            article_id=article_id,
            stage=stage,
            message=message,
            duration_ms=duration_ms,
        )
    except Exception as log_exc:
        logger.error("写入失败日志时发生异常: %s", log_exc)

    return ParserError(message)
