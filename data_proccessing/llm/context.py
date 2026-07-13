"""Build a small evidence-only prompt for LLM fallback."""

from __future__ import annotations

import json

from data_proccessing.config import ProcessingConfig
from data_proccessing.models import ArbitrationResult


def build_llm_context(
    *,
    title: str,
    product: str,
    arbitration: ArbitrationResult,
    config: ProcessingConfig | None = None,
    evidence_snippets: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, str]]:
    config = config or ProcessingConfig()
    source_snippets = evidence_snippets if evidence_snippets is not None else arbitration.evidence_snippets
    snippets = list(dict.fromkeys(source_snippets))[:config.max_llm_snippets]
    context = "\n".join(f"- {item}" for item in snippets)
    context = context[:config.max_llm_chars]
    payload = {
        "product": product,
        "rule_scores": {
            "bullish": arbitration.bullish_score,
            "bearish": arbitration.bearish_score,
            "neutral": arbitration.neutral_score,
        },
        "rule_margin": arbitration.margin,
        "evidence": snippets,
    }
    return [
        {
            "role": "system",
            "content": (
                "你是期货市场研究员。只根据提供的证据判断该品种后续方向。"
                "必须返回 JSON：product、direction、reason、confidence。"
                "direction 只能是 看涨、看跌、中性；不能补充证据外的事实。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"标题：{title}\n"
                f"待判断品种：{product}\n"
                f"规则摘要：{json.dumps(payload, ensure_ascii=False)}\n"
                f"相关原文证据：\n{context}"
            ),
        },
    ]
