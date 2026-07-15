"""Pure text cleaning and presentation cleanup for the standalone pipeline.

The cleaner deliberately never changes ``Document.raw_text``.  It produces a
cleaned view for storage, evidence display, and LLM context while signal
matching continues to use the original text and its stable offsets.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True, slots=True)
class CleaningConfig:
    normalize_whitespace: bool = True
    normalize_fullwidth: bool = True
    remove_html_residue: bool = True
    drop_disclaimer_blocks: bool = True
    drop_numeric_noise: bool = True
    preserve_markdown_tables: bool = True
    min_semantic_line_chars: int = 3


@dataclass(frozen=True, slots=True)
class CleaningStats:
    noise_lines_removed: int = 0
    numeric_lines_removed: int = 0
    disclaimer_lines_removed: int = 0


_NOISE_KEYWORDS = (
    "免责声明", "免责申明", "风险提示", "投资有风险", "入市需谨慎",
    "扫码关注", "添加微信", "加我微信", "QQ群", "微信号", "点击关注",
    "公众号", "广告", "二维码", "下载APP", "客服电话", "咨询电话",
    "免费热线", "联系电话", "客服热线", "不得转载", "不得复制",
    "未经许可", "不构成投资", "不构成买卖建议", "不作任何保证",
    "版权所有", "Copyright", "All Rights Reserved", "返回顶部",
    "上一篇：", "下一篇：", "无障碍浏览", "ICP备案",
)
_NOISE_BLOCKS = (
    r"免责声明[\s\S]*?(?=\n\n|\n(?=[^\s])|\Z)",
    r"免责申明[\s\S]*?(?=\n\n|\n(?=[^\s])|\Z)",
    r"风险提示[：:][\s\S]*?(?=\n\n|\n(?=[^\s])|\Z)",
    r"分析师\s*(?:声明|承诺|简介)[\s\S]*?(?=\n\n|\n(?=[^\s])|\Z)",
)
_CONTACT_PATTERNS = (
    r"(?:投资咨询|从业资格|执业资格|期货从业|证券从业)\s*证号\s*[:：]?\s*[A-Z]?\d{5,}",
    r"(?:E[-\s]?MAIL|Email|邮箱|电子邮箱)\s*[:：]?\s*[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
    r"(?:联系电话|咨询电话|客服电话|客服热线|电话|传真|手机)\s*[:：]?\s*(?:\+?86[-\s]?)?(?:\d{3,4}[-\s]?\d{6,8}|\d{7,12})",
    r"https?://\S+",
    r"\bwww\.[A-Za-z0-9./-]+",
)
_SEMANTIC_HINTS = (
    "观点", "逻辑", "建议", "策略", "展望", "预测", "预计", "预期", "价格",
    "上涨", "下跌", "上行", "下行", "偏强", "偏弱", "震荡", "库存", "需求",
    "供应", "成本", "利润", "基差", "现货", "期货", "产业链", "利多", "利空",
    "支撑", "压力", "风险", "产能", "装置", "原油", "开工率", "投产",
)
_NAVIGATION_ONLY = {"晨报", "日报", "周报", "月报", "年报", "农产品", "能源化工", "有色金属", "黑色金属", "交易策略"}


def clean_text(text: str, config: CleaningConfig | None = None) -> tuple[str, CleaningStats]:
    """Clean report noise while retaining market semantics and Markdown tables."""
    config = config or CleaningConfig()
    original = text or ""
    text = _normalize_base(original, config)
    removed_noise = removed_numeric = removed_disclaimer = 0
    for pattern in _NOISE_BLOCKS:
        text, count = re.subn(pattern, "", text, flags=re.IGNORECASE | re.MULTILINE)
        removed_disclaimer += count

    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if stripped.startswith("[PAGE ") and stripped.endswith("]"):
            removed_noise += 1
            continue
        cleaned = _remove_inline_noise(stripped)
        if not cleaned:
            removed_noise += 1
            continue
        if _is_noise_line(cleaned):
            removed_noise += 1
            continue
        if config.drop_numeric_noise and _is_numeric_noise(cleaned, config):
            removed_numeric += 1
            continue
        cleaned = _repair_ocr_line(cleaned)
        kept.append(cleaned)

    result = _compact_lines(kept)
    stats = CleaningStats(removed_noise, removed_numeric, removed_disclaimer)
    if not result.strip() and original.strip():
        return original.strip(), stats
    return result, stats


def clean_display_text(text: str | None, *, max_chars: int | None = None) -> str:
    """Return compact user-facing text with report footer noise removed."""
    if not text:
        return ""
    normalized = str(text).replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"```(?:\w+)?\s*([\s\S]*?)\s*```", r"\1", normalized)
    normalized = re.sub(r"(?m)^#{2,}\s*Page\s+\d+\s*$", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(?m)^#+\s*文档信息\s*$", "", normalized)
    normalized = re.sub(r"(?m)^(来源文件|解析器)\s*[:：].*$", "", normalized)
    lines: list[str] = []
    for raw_line in normalized.splitlines():
        line = _compact_inline_spaces(_remove_inline_noise(raw_line))
        if line and not _is_noise_line(line):
            lines.append(line)
    result = "\n".join(_dedupe_adjacent(lines))
    result = re.sub(r"\n{2,}", "\n", result)
    result = re.sub(r"[ \t]{2,}", " ", result).strip()
    if max_chars and len(result) > max_chars:
        result = result[:max_chars].rstrip("，,；;、 ") + "。"
    return result


def has_residual_display_noise(text: str | None) -> bool:
    if not text:
        return False
    compact = re.sub(r"\s+", "", str(text))
    if any(item in compact for item in ("从业资格证号", "投资咨询证号", "免责申明", "免责声明")):
        return True
    return any(re.search(pattern, str(text), flags=re.IGNORECASE) for pattern in _CONTACT_PATTERNS)


def _normalize_base(text: str, config: CleaningConfig) -> str:
    text = (text or "").replace("\x00", "").replace("�" * 2, "�")
    if config.remove_html_residue:
        entities = {"&nbsp;": " ", "&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": '"', "&mdash;": "—"}
        for source, target in entities.items():
            text = text.replace(source, target)
        text = re.sub(r"&#(?:\d+|x[0-9a-fA-F]+);", " ", text)
        text = re.sub(r"</?[A-Za-z][^>]*/?>", " ", text)
    if config.normalize_fullwidth:
        text = _normalize_fullwidth(text)
    if config.normalize_whitespace:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n"))
    return text


def _normalize_fullwidth(text: str) -> str:
    preserved = {0xFF0C, 0x3001, 0x3002, 0xFF01, 0xFF1F, 0xFF1B, 0xFF1A, 0xFF08, 0xFF09, 0xFF3B, 0xFF3D}
    chars: list[str] = []
    for char in text:
        code = ord(char)
        if code in preserved:
            chars.append(char)
        elif code == 0x3000:
            chars.append(" ")
        else:
            chars.append(unicodedata.normalize("NFKC", char))
    return "".join(chars)


def _remove_inline_noise(line: str) -> str:
    result = line.strip()
    for pattern in _CONTACT_PATTERNS:
        result = re.sub(pattern, " ", result, flags=re.IGNORECASE)
    result = re.sub(r"\b\d+\s*/\s*\d+\b", " ", result)
    return _compact_inline_spaces(result)


def _compact_inline_spaces(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([，。；：！？、])", r"\1", text)
    text = re.sub(r"([【（(])\s+", r"\1", text)
    text = re.sub(r"\s+([】）)])", r"\1", text)
    return text.strip(" \t:：,，;；")


def _is_noise_line(line: str) -> bool:
    compact = re.sub(r"\s+", "", line)
    if not compact or any(keyword.casefold() in compact.casefold() for keyword in _NOISE_KEYWORDS):
        return True
    if compact in _NAVIGATION_ONLY or re.fullmatch(r"第?\d+页?", compact):
        return True
    if re.fullmatch(r"[\d/\-.]+", compact) or re.fullmatch(r"[=\-_]{3,}", compact):
        return True
    if re.fullmatch(r"[\u4e00-\u9fff]{2,16}(?:期货)?(?:有限责任)?公司(?:研究所)?", compact):
        return True
    return False


def _is_numeric_noise(line: str, config: CleaningConfig) -> bool:
    if line.startswith("#") or (config.preserve_markdown_tables and line.startswith("|")):
        return False
    if any(hint in line for hint in _SEMANTIC_HINTS):
        return False
    compact = line.replace(" ", "")
    if not compact:
        return True
    cjk = len(re.findall(r"[一-鿿]", compact))
    digits = len(re.findall(r"\d", compact))
    numeric_tokens = len(re.findall(r"[-+]?\d[\d,.]*", line))
    date_count = len(re.findall(r"\b\d{1,2}[-/.]\d{1,2}\b", line))
    ratio = digits / max(len(compact), 1)
    return date_count >= 3 or (ratio >= 0.55 and numeric_tokens >= 2 and cjk <= 2) or bool(re.fullmatch(r"[\d\s,.\-+/%()]+", line))


def _repair_ocr_line(line: str) -> str:
    line = re.sub(r"\s{2,}", " ", line)
    line = re.sub(r"([一-鿿])\s+([一-鿿])", r"\1\2", line)
    return line.replace("年未", "年末").replace("装直", "装置").strip()


def _compact_lines(lines: list[str]) -> str:
    result: list[str] = []
    for line in lines:
        if not line and result and result[-1] != "":
            result.append("")
        elif line:
            result.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(result)).strip()


def _dedupe_adjacent(lines: list[str]) -> list[str]:
    result: list[str] = []
    previous = ""
    for line in lines:
        key = re.sub(r"\s+", "", line)
        if key and key != previous:
            result.append(line)
            previous = key
    return result
