"""
pn07 Prompt 构建器

组装 System/User prompt，将文章上下文注入模板。
"""

from __future__ import annotations


SYSTEM_PROMPT = """你是一位资深期货市场分析师。请从以下期货研究报告文本中提取关键信息，并以 JSON 格式输出分析结果。

规则：
1. product: 涉及的期货品种名称（如螺纹钢、沪铜、豆粕、铁矿石、原油等）。如果文本提到多个品种，选择最主要讨论的那个。
2. direction: 走势预测，必须是"看涨"、"看跌"或"中性"之一。
3. reason: 支撑该判断的核心理由，控制在100字以内，引用文本中的关键信息。
4. confidence: 你对该判断的置信度(0.0-1.0)。明确信号>0.8，模糊信号<0.5，不确定时给低分。

只输出 JSON，不要添加任何解释或额外文本。"""


def build_messages(
    cleaned_text: str,
    *,
    title: str = "",
    source: str = "",
    company: str = "",
    publish_time: str = "",
    max_input_chars: int = 8000,
) -> list[dict]:
    """
    构建 LLM messages。

    Args:
        cleaned_text: 清洗后的文章正文
        title: 文章标题
        source: 来源
        company: 期货公司
        publish_time: 发布时间
        max_input_chars: 正文最大字符数（超出截断）

    Returns:
        [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    """
    # 构建用户消息
    parts = []
    if title:
        parts.append(f"标题：{title}")
    meta_parts = []
    if source:
        meta_parts.append(f"来源：{source}")
    if company:
        meta_parts.append(f"期货公司：{company}")
    if publish_time:
        meta_parts.append(f"发布时间：{publish_time}")
    if meta_parts:
        parts.append(" | ".join(meta_parts))

    # 正文（可能截断）
    if len(cleaned_text) > max_input_chars:
        truncated = cleaned_text[:max_input_chars]
        truncated += f"\n\n[文本过长，已截断，原始长度: {len(cleaned_text)} 字符]"
    else:
        truncated = cleaned_text

    parts.append(f"\n正文：\n{truncated}")
    parts.append("\n请输出 JSON：")

    user_content = "\n".join(parts)

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
