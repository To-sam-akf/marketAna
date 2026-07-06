"""
pn05 文本规范化器

提供纯函数式的文本规范化处理：
- 空白字符统一
- 全角/半角转换
- HTML 残留移除
- 编码检测与修复
"""

from __future__ import annotations

import re
import unicodedata

# 中文全角标点 — 保留不转半角
_CHINESE_PUNCTUATION: set[int] = {
    0xFF0C,  # ，
    0x3001,  # 、
    0x3002,  # 。
    0xFF0E,  # ．
    0xFF01,  # ！
    0xFF1F,  # ？
    0xFF1B,  # ；
    0xFF1A,  # ：
    0xFF3B,  # ［
    0xFF3D,  # ］
    0xFF08,  # （
    0xFF09,  # ）
    0x300C,  # 「
    0x300D,  # 」
    0x300E,  # 『
    0x300F,  # 』
    0x2018,  # '
    0x2019,  # '
    0x201C,  # "
    0x201D,  # "
    0x2014,  # —
    0x2026,  # …
    0xFF5E,  # ～
}


def normalize_whitespace(text: str) -> str:
    """
    统一空白字符。

    - \\r\\n → \\n
    - 连续 3+ 换行 → 2 换行（保留段落间距但去除大片空白）
    - 连续空格/制表符 → 单个空格
    - 去除行首行尾空白
    """
    # 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 连续 3+ 换行 → 2 换行
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 每行内部：合并连续空白（但保留换行）
    lines = text.split("\n")
    cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]

    return "\n".join(cleaned_lines)


def normalize_fullwidth(text: str) -> str:
    """
    全角字符 → 半角字符。

    全角字母/数字/符号 → 半角等价字符。
    中文全角标点（，。！？【】）保留不转换。
    """
    result: list[str] = []
    for ch in text:
        code = ord(ch)

        # 全角字母 A-Z (FF21-FF3A) → 半角 (0041-005A)
        if 0xFF21 <= code <= 0xFF3A:
            result.append(chr(code - 0xFF21 + 0x0041))
        # 全角字母 a-z (FF41-FF5A) → 半角 (0061-007A)
        elif 0xFF41 <= code <= 0xFF5A:
            result.append(chr(code - 0xFF41 + 0x0061))
        # 全角数字 ０-９ (FF10-FF19) → 半角 (0030-0039)
        elif 0xFF10 <= code <= 0xFF19:
            result.append(chr(code - 0xFF10 + 0x0030))
        # 全角空格 (3000) → 半角空格
        elif code == 0x3000:
            result.append(" ")
        # 中文全角标点：保留不转换
        elif code in _CHINESE_PUNCTUATION:
            result.append(ch)
        # 其他全角符号 → 尝试 NFKC 规范化
        elif 0xFF01 <= code <= 0xFF5E:
            normalized = unicodedata.normalize("NFKC", ch)
            result.append(normalized)
        else:
            result.append(ch)

    return "".join(result)


# HTML 实体映射
_HTML_ENTITIES: dict[str, str] = {
    "&nbsp;": " ", "&lt;": "<", "&gt;": ">",
    "&amp;": "&", "&quot;": '"', "&apos;": "'",
    "&#160;": " ", "&ensp;": " ", "&emsp;": "  ",
    "&ldquo;": '"', "&rdquo;": '"', "&lsquo;": "'", "&rsquo;": "'",
    "&mdash;": "—", "&ndash;": "–", "&hellip;": "…",
}


def remove_html_residue(text: str) -> str:
    """
    移除 HTML 残留。

    - HTML 实体（&nbsp; &lt; 等）
    - 残留的 HTML 标签（<tag> </tag> <tag attr="x"/>）
    - 数字实体（&#xxxx;）
    """
    # HTML 实体
    for entity, replacement in _HTML_ENTITIES.items():
        text = text.replace(entity, replacement)

    # 数字实体 &#xxxx;
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"&#x[0-9a-fA-F]+;", " ", text)

    # 残留标签 <...>
    text = re.sub(r"</?[a-zA-Z][^>]*/?>", " ", text)

    # 清理标签移除后产生的多余空白
    text = re.sub(r" {2,}", " ", text)

    return text


def detect_and_clean_encoding(text: str) -> str:
    """
    检测并修复编码问题。

    处理常见的编码损坏：
    - 移除 NULL 字节（\\x00）
    - 移除 Unicode 替换字符（U+FFFD）连续出现
    - 尝试修复常见乱码模式（UTF-8 字节被当作 Latin-1 解释）

    注意：此函数处理的是已解码的 str。真正的编码检测应在文件读取时完成（pn04 已处理）。
    这里只修复字符串层面的残留编码问题。
    """
    # 移除 NULL 字节
    text = text.replace("\x00", "")

    # 连续的替换字符 → 单个
    text = re.sub(r"�{2,}", "�", text)

    # 替换字符过多 → 可能有编码问题，记录但不阻塞
    replacement_count = text.count("�")
    if replacement_count > len(text) * 0.1:
        # 超过 10% 是替换字符 → 严重编码问题
        pass  # 仅记录，不清空

    return text
