"""
pn06 方向识别规则

通过关键词匹配和正则模式识别文章中的期货走势方向：
看涨 / 看跌 / 中性。
同时提取支撑该方向的理由（句子窗口）。
"""

from __future__ import annotations

import re

# ------- 方向关键词 -------

# 看涨类 — 确定词（直接匹配）
BULLISH_STRONG: list[str] = [
    "看涨", "上涨", "偏强", "反弹", "走强", "做多", "多头",
    "上行", "回升", "冲高", "走高", "利好", "看多", "牛市",
    "增持", "偏多", "上移", "上探", "强势",
]

# 看涨类 — 模糊词（正则模式）
BULLISH_WEAK: list[str] = [
    r"预计.*上涨",
    r"短期.*偏强",
    r"后市.*看涨",
    r"有望.*上行",
    r"预期.*偏多",
    r"或.*反弹",
]

# 看跌类 — 确定词
BEARISH_STRONG: list[str] = [
    "看跌", "下跌", "偏弱", "回落", "走弱", "做空", "空头",
    "下行", "下滑", "走低", "利空", "看空", "熊市",
    "减持", "偏空", "下移", "下探", "弱势",
]

# 看跌类 — 模糊词
BEARISH_WEAK: list[str] = [
    r"预计.*下跌",
    r"短期.*偏弱",
    r"后市.*看跌",
    r"面临.*压力",
    r"预期.*偏空",
    r"或.*回落",
]

# 中性类 — 确定词
NEUTRAL_STRONG: list[str] = [
    "震荡", "区间", "观望", "盘整", "横盘", "整理", "波动",
    "持稳", "平稳", "震荡整理", "窄幅",
]

# 中性类 — 模糊词
NEUTRAL_WEAK: list[str] = [
    r"以.*震荡.*为主",
    r"短期.*整理",
    r"区间.*运行",
    r"维持.*震荡",
    r"方向.*不.*明",
    r"等待.*选择.*方向",
]

# ------- 方向检测 -------

def detect_direction(text: str) -> dict:
    """
    检测文本中的走势方向。

    Returns:
        {
            "direction": "看涨"|"看跌"|"中性"|None,
            "bullish_count": int,     # 看涨匹配数
            "bearish_count": int,     # 看跌匹配数
            "neutral_count": int,     # 中性匹配数
            "strong_matches": [...],  # 确定词匹配列表
            "weak_matches": [...],    # 模糊词匹配列表
            "is_conflict": bool,      # 是否存在看涨+看跌冲突
        }
    """
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    strong_matches: list[str] = []
    weak_matches: list[str] = []

    # 看涨-确定词
    for word in BULLISH_STRONG:
        count = text.count(word)
        if count:
            bullish_count += count
            strong_matches.append(f"bullish:{word}")

    # 看涨-模糊词
    for pattern in BULLISH_WEAK:
        matches = re.findall(pattern, text)
        if matches:
            bullish_count += len(matches)
            weak_matches.append(f"bullish:{pattern}")

    # 看跌-确定词
    for word in BEARISH_STRONG:
        count = text.count(word)
        if count:
            bearish_count += count
            strong_matches.append(f"bearish:{word}")

    # 看跌-模糊词
    for pattern in BEARISH_WEAK:
        matches = re.findall(pattern, text)
        if matches:
            bearish_count += len(matches)
            weak_matches.append(f"bearish:{pattern}")

    # 中性-确定词
    for word in NEUTRAL_STRONG:
        count = text.count(word)
        if count:
            neutral_count += count
            strong_matches.append(f"neutral:{word}")

    # 中性-模糊词
    for pattern in NEUTRAL_WEAK:
        matches = re.findall(pattern, text)
        if matches:
            neutral_count += len(matches)
            weak_matches.append(f"neutral:{pattern}")

    # 判定方向
    is_conflict = bullish_count > 0 and bearish_count > 0
    direction = _resolve_direction(bullish_count, bearish_count, neutral_count)

    return {
        "direction": direction,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "strong_matches": strong_matches,
        "weak_matches": weak_matches,
        "is_conflict": is_conflict,
    }


def extract_reason(text: str, direction: str | None, window: int = 2) -> str:
    """
    提取支撑方向的理由：方向关键词前后各 window 句。

    Args:
        text: 文章文本
        direction: 已判定的方向（"看涨"/"看跌"/"中性"）
        window: 前后句子窗口大小

    Returns:
        理由文本
    """
    if not direction:
        return ""

    # 找方向关键词所在位置
    direction_keywords = _get_keywords_for_direction(direction)
    sentences = _split_sentences(text)
    if not sentences:
        return ""

    # 找包含方向关键词的句子索引
    target_indices: set[int] = set()
    for i, sentence in enumerate(sentences):
        for kw in direction_keywords:
            if kw in sentence:
                target_indices.add(i)
                break

    if not target_indices:
        return ""

    # 取窗口
    reason_indices: set[int] = set()
    for idx in target_indices:
        start = max(0, idx - window)
        end = min(len(sentences), idx + window + 1)
        reason_indices.update(range(start, end))

    reason_sentences = [sentences[i] for i in sorted(reason_indices)]
    return "".join(reason_sentences)


# ------- 内部 -------

def _resolve_direction(bullish: int, bearish: int, neutral: int) -> str | None:
    """根据匹配计数判定最终方向。"""
    if bullish == 0 and bearish == 0 and neutral == 0:
        return None
    # 取最多的方向
    counts = {"看涨": bullish, "看跌": bearish, "中性": neutral}
    return max(counts, key=lambda k: counts[k])


def _get_keywords_for_direction(direction: str) -> list[str]:
    """获取指定方向的所有关键词（用于理由定位）。"""
    if direction == "看涨":
        return BULLISH_STRONG + [p.replace(r".*", "").replace(r".*?", "") for p in BULLISH_WEAK]
    elif direction == "看跌":
        return BEARISH_STRONG + [p.replace(r".*", "").replace(r".*?", "") for p in BEARISH_WEAK]
    elif direction == "中性":
        return NEUTRAL_STRONG + [p.replace(r".*", "").replace(r".*?", "") for p in NEUTRAL_WEAK]
    return []


def _split_sentences(text: str) -> list[str]:
    """按中文标点分句。"""
    # 在 。！？；\n 处分割
    parts = re.split(r"(?<=[。！？；\n])", text)
    return [p.strip() for p in parts if p.strip()]
