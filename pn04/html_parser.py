"""
pn04 HTML 解析器

使用 BeautifulSoup 解析 HTML 文件，移除脚本、样式、广告和导航噪声，
提取正文文本，并将 <table> 转换为 Markdown 格式。
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

from pn04.exceptions import EmptyContentError, FileReadError, FileNotFoundError_
from pn04.models import ParseConfig, ParseResult, ParserType
from pn04.table_utils import extract_table_text, html_table_to_markdown

logger = logging.getLogger(__name__)


# 需移除的标签
_REMOVE_TAGS = [
    "script", "style", "noscript", "iframe",
    "nav", "footer", "header", "aside",
    "form", "input", "button", "select",
]

# 需移除的 class/id 关键词（广告、导航、页脚等）
_REMOVE_SELECTORS = [
    '[class*="ad"]', '[id*="ad"]',
    '[class*="banner"]', '[id*="banner"]',
    '[class*="nav"]', '[id*="nav"]',
    '[class*="menu"]', '[id*="menu"]',
    '[class*="footer"]', '[id*="footer"]',
    '[class*="sidebar"]', '[id*="sidebar"]',
    '[class*="widget"]', '[id*="widget"]',
    '[class*="comment"]', '[id*="comment"]',
    '[class*="share"]', '[id*="share"]',
    '[class*="social"]', '[id*="social"]',
    '[class*="popup"]', '[id*="popup"]',
    '[class*="cookie"]', '[id*="cookie"]',
    '[class*="disclaimer"]', '[id*="disclaimer"]',
    '[role="navigation"]',
    '[role="banner"]',
    '[role="contentinfo"]',
]

# 免责声明/版权声明关键词模式
_DISCLAIMER_PATTERNS = [
    r"免责声明[\s\S]*?$",
    r"风险提示[\s\S]*?$",
    r"版权所有[\s\S]*?$",
    r"投资有风险[\s\S]*?$",
    r"市场有风险[\s\S]*?$",
    r"本报告仅供参考[\s\S]*?$",
    r"扫码关注[\s\S]*?$",
    r"未经许可.*?不得[\s\S]*?$",
    r"Copyright\s.*?$",
    r"All Rights Reserved[\s\S]*?$",
]


class HtmlParser:
    """HTML 文件解析器。

    使用 BeautifulSoup + lxml 解析 HTML，移除噪声节点，
    提取正文文本和表格。

    Usage:
        parser = HtmlParser(config=ParseConfig())
        result = parser.parse("/path/to/report.html")
    """

    def __init__(self, config: ParseConfig | None = None) -> None:
        self.config = config or ParseConfig()
        self._table_count = 0

    def parse(self, file_path: str) -> ParseResult:
        """
        解析 HTML 文件并返回纯文本。

        Args:
            file_path: HTML 文件的本地路径

        Returns:
            ParseResult: 包含解析文本和元数据

        Raises:
            FileNotFoundError_: 文件不存在
            FileReadError: 文件读取或解析失败
            EmptyContentError: 解析结果为空
        """
        self._validate_file(file_path)
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError(
                "beautifulsoup4 未安装，请执行: pip install beautifulsoup4 lxml"
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        except UnicodeDecodeError:
            # 尝试 gbk 编码（国内网站常见）
            try:
                with open(file_path, "r", encoding="gbk") as f:
                    html_content = f.read()
            except Exception:
                with open(file_path, "r", encoding="latin-1") as f:
                    html_content = f.read()
        except Exception as exc:
            raise FileReadError(file_path, reason=str(exc)) from exc

        self._table_count = 0

        try:
            soup = BeautifulSoup(html_content, "lxml")
        except Exception:
            # lxml 不可用时降级到 html.parser
            soup = BeautifulSoup(html_content, "html.parser")

        # 1. 移除噪声节点
        self._remove_noise(soup)

        # 2. 先处理表格（转换为 Markdown 后从 DOM 移除，避免重复）
        table_texts = self._process_tables(soup)

        # 3. 提取正文
        body_text = self._extract_body(soup)

        # 4. 合并正文和表格
        parts: list[str] = []
        if body_text.strip():
            parts.append(body_text.strip())
        if table_texts:
            parts.append(table_texts)

        raw_text = "\n\n".join(parts)

        # 5. 后处理：移除免责声明
        raw_text = self._remove_disclaimers(raw_text)

        if not raw_text.strip():
            raise EmptyContentError(
                parser_type=ParserType.HTML.value,
                file_path=file_path,
            )

        # 截断处理
        if len(raw_text) > self.config.max_text_length:
            raw_text = (
                raw_text[: self.config.max_text_length]
                + f"\n\n[文本过长，已截断，原长度: {len(raw_text)} 字符]"
            )

        return ParseResult(
            parser_type=ParserType.HTML,
            raw_text=raw_text,
            metadata={
                "file_path": file_path,
                "tables_found": self._table_count,
            },
        )

    def parse_html_string(self, html: str) -> str:
        """
        直接解析 HTML 字符串（用于 PDF 内嵌 HTML 或在线内容）。

        Args:
            html: HTML 字符串

        Returns:
            解析后的纯文本
        """
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("beautifulsoup4 未安装")

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        self._table_count = 0
        self._remove_noise(soup)
        table_texts = self._process_tables(soup)
        body_text = self._extract_body(soup)

        parts = [p for p in [body_text.strip(), table_texts] if p.strip()]
        return "\n\n".join(parts)

    # ---- 内部方法 ----

    @staticmethod
    def _validate_file(file_path: str) -> None:
        """验证文件存在且可读。"""
        if not os.path.exists(file_path):
            raise FileNotFoundError_(file_path)
        if not os.path.isfile(file_path):
            raise FileReadError(file_path, reason="路径不是文件")

    def _remove_noise(self, soup: Any) -> None:
        """移除 HTML 中的噪声节点。"""
        # 移除指定标签
        for tag in _REMOVE_TAGS:
            for node in soup.find_all(tag):
                node.decompose()

        # 移除匹配 CSS 选择器的节点
        for selector in _REMOVE_SELECTORS:
            try:
                for node in soup.select(selector):
                    # 避免移除了主要内容容器
                    if not self._is_main_content(node):
                        node.decompose()
            except Exception:
                pass

    @staticmethod
    def _is_main_content(node: Any) -> bool:
        """判断节点是否可能是正文内容（保护不被误删）。"""
        protect_ids = {"content", "main", "article", "post", "entry", "body"}
        protect_classes = {"content", "main", "article", "post", "entry", "body", "text"}

        node_id = (node.get("id") or "").lower()
        node_class = " ".join(node.get("class") or []).lower()

        if any(pid in node_id for pid in protect_ids):
            return True
        if any(pc in node_class for pc in protect_classes):
            return True
        return False

    def _process_tables(self, soup: Any) -> str:
        """提取所有 <table> 并转换为 Markdown，然后从 DOM 移除。"""
        tables = soup.find_all("table")
        if not tables:
            return ""

        results: list[str] = []
        for table in tables:
            md = html_table_to_markdown(
                table,
                add_description=self.config.table_add_description,
            )
            if md.strip():
                results.append(md)
                self._table_count += 1

            # 同时添加纯文本版本辅助理解
            text_desc = extract_table_text(table)
            if text_desc.strip():
                results.append(text_desc)

            # 移除已处理的表格
            table.decompose()

        return "\n\n".join(results)

    def _extract_body(self, soup: Any) -> str:
        """提取 HTML 正文文本。"""
        # 优先查找正文容器
        content_selectors = [
            soup.find("article"),
            soup.find("main"),
            soup.find("div", class_=re.compile(r"content|article|post|entry|body|text", re.I)),
            soup.find("div", id=re.compile(r"content|article|post|entry|body|text", re.I)),
            soup.body,
        ]

        content = None
        for selector in content_selectors:
            if selector:
                content = selector
                break

        if content is None:
            content = soup

        # 提取文本
        text = content.get_text(separator="\n", strip=True)

        # 处理保留的 alt 文本
        if self.config.html_keep_alt_text:
            imgs = content.find_all("img")
            for img in imgs:
                alt = img.get("alt", "").strip()
                if alt:
                    text += f"\n[图片说明: {alt}]"

        # 清理多余空白
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)

        return text

    @staticmethod
    def _remove_disclaimers(text: str) -> str:
        """移除文本中的免责声明/版权声明行。"""
        for pattern in _DISCLAIMER_PATTERNS:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
        return text.strip()
