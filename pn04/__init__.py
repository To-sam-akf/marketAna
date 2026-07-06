"""
pn04 文件解析模块 Parser

支持 PDF、HTML、图片（PNG/JPG 等）格式的文章文件解析，
将原始文件转换为可供清洗模块处理的纯文本。

主要入口:
    parse_article(article, session) -> str
"""

from pn04.parser import parse_article, ParseConfig

__all__ = ["parse_article", "ParseConfig"]
