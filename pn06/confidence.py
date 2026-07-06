"""
pn06 置信度评分器

基于方向检测的匹配结果计算置信度分数 (0.0-1.0)。

评分逻辑：
- 基础分 base_score（检测到品种+方向）
- 确定词匹配 → 加分
- 模糊词匹配 → 减分
- 多处一致结论 → 加分
- 涨跌方向冲突 → 扣分
- 仅中性 → 上限 0.6（中性本质上是"不确定"）
"""

from __future__ import annotations

from pn06.models import RuleConfig


def calculate_confidence(
    product: str | None,
    direction_result: dict,
    config: RuleConfig | None = None,
) -> float:
    """
    计算规则识别的置信度。

    Args:
        product: 检测到的品种（None 表示未检测到）
        direction_result: detect_direction() 的返回
        config: 评分配置

    Returns:
        置信度 0.0-1.0
    """
    config = config or RuleConfig()

    # 未检测到品种或方向 → 0
    if product is None or direction_result["direction"] is None:
        return 0.0

    score = config.base_score

    # 确定词加分（每次匹配 +boost）
    strong_count = len(direction_result.get("strong_matches", []))
    score += strong_count * config.boost_deterministic

    # 模糊词减分（每次匹配 -penalty）
    weak_count = len(direction_result.get("weak_matches", []))
    score -= weak_count * config.penalty_vague

    # 方向冲突 → 大幅扣分
    if direction_result.get("is_conflict", False):
        score -= config.penalty_conflict

    # 多处一致结论加分（strong >= 2 且无冲突）
    if strong_count >= 2 and not direction_result.get("is_conflict", False):
        score += config.boost_multi_match * (strong_count - 1)

    # 中性方向 → 上限 0.6（本质是不确定）
    if direction_result["direction"] == "中性":
        score = min(score, 0.6)

    # 仅模糊词无确定词 → 上限 0.55
    if strong_count == 0 and weak_count > 0:
        score = min(score, 0.55)

    return max(config.min_confidence, min(config.max_confidence, round(score, 2)))
