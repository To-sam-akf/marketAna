"""
pn04 数据模型

定义解析器类型枚举、解析结果和解析配置。
"""

from dataclasses import dataclass, field
from enum import Enum


class ParserType(str, Enum):
    """解析器类型枚举，值对应 article_texts.parser_type 字段。"""

    PDF = "pdf"
    HTML = "html"
    IMAGE = "image"
    UNKNOWN = "unknown"


# 支持的文件扩展名映射
EXTENSION_MAP: dict[str, ParserType] = {
    ".pdf": ParserType.PDF,
    ".html": ParserType.HTML,
    ".htm": ParserType.HTML,
    ".png": ParserType.IMAGE,
    ".jpg": ParserType.IMAGE,
    ".jpeg": ParserType.IMAGE,
    ".bmp": ParserType.IMAGE,
    ".tiff": ParserType.IMAGE,
    ".tif": ParserType.IMAGE,
    ".webp": ParserType.IMAGE,
    ".gif": ParserType.IMAGE,
}

# MIME 类型映射（用于 file_type 字段或实际文件检测）
MIME_MAP: dict[str, ParserType] = {
    "application/pdf": ParserType.PDF,
    "text/html": ParserType.HTML,
    "image/png": ParserType.IMAGE,
    "image/jpeg": ParserType.IMAGE,
    "image/bmp": ParserType.IMAGE,
    "image/tiff": ParserType.IMAGE,
    "image/webp": ParserType.IMAGE,
    "image/gif": ParserType.IMAGE,
}


@dataclass
class ParseResult:
    """单次解析的结果。"""

    parser_type: ParserType
    raw_text: str
    raw_length: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.raw_length == 0:
            self.raw_length = len(self.raw_text)


@dataclass
class ParseConfig:
    """解析器配置。"""

    # OCR 语言，默认中文+英文
    ocr_lang: str = "chi_sim+eng"
    # 是否对扫描件 PDF 降级到 OCR
    pdf_ocr_fallback: bool = True
    # PDF 每页最少字符数，低于此值视为扫描页，触发 OCR
    pdf_min_chars_per_page: int = 10
    # HTML 是否保留图片 alt 文本
    html_keep_alt_text: bool = True
    # 是否提取表格为 Markdown
    extract_tables: bool = True
    # 表格 Markdown 前后是否添加自然语言描述
    table_add_description: bool = True
    # 最大解析文本长度（字符），超过则截断并加标记
    max_text_length: int = 500_000


def detect_parser_type(file_type: str | None, file_url: str | None) -> ParserType:
    """
    根据 file_type 字段和 file_url 扩展名判断解析器类型。

    优先级：file_type > URL 扩展名。

    Args:
        file_type: Article.file_type 值，如 "pdf", "html", "image/png"
        file_url: Article.file_url 值，如 "/files/report.pdf"

    Returns:
        ParserType 枚举值，无法判断时返回 ParserType.UNKNOWN
    """
    # 1. 按 file_type 字段判断
    if file_type:
        ft = file_type.lower().strip()
        # 直接匹配枚举值
        if ft in {t.value for t in ParserType}:
            return ParserType(ft)
        # 匹配 MIME 类型
        if ft in MIME_MAP:
            return MIME_MAP[ft]
        # 匹配扩展名（去掉点）
        ext = f".{ft.lstrip('.')}"
        if ext in EXTENSION_MAP:
            return EXTENSION_MAP[ext]

    # 2. 按 URL 扩展名判断
    if file_url:
        url_lower = file_url.lower().split("?")[0]  # 去掉查询参数
        for ext, ptype in EXTENSION_MAP.items():
            if url_lower.endswith(ext):
                return ptype

    return ParserType.UNKNOWN
