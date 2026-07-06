"""
pn06 数据模型

定义规则识别配置和结果。
"""

from dataclasses import dataclass, field


@dataclass
class RuleConfig:
    """规则引擎配置。"""

    confidence_threshold: float = 0.7     # >= 此值直接入库，< 此值交 LLM
    reason_window: int = 2                # 理由提取：方向词前后各 N 句
    base_score: float = 0.5              # 基础分
    boost_deterministic: float = 0.15    # 确定词加分
    penalty_vague: float = 0.1           # 模糊词减分
    boost_multi_match: float = 0.1       # 多处一致加分（每次）
    penalty_conflict: float = 0.25       # 涨跌冲突一次性扣分
    max_confidence: float = 1.0
    min_confidence: float = 0.0


@dataclass
class RuleResult:
    """规则识别结果。"""

    product: str | None = None           # 识别的品种名（正名）
    direction: str | None = None         # 看涨/看跌/中性
    reason: str = ""                     # 理由摘要
    confidence: float = 0.0              # 置信度 0-1
    analysis_method: str = "rule"
    need_llm: bool = True                # 是否需要进入 LLMInfer
    detail: dict = field(default_factory=dict)

    @property
    def is_high_confidence(self) -> bool:
        """置信度是否达到直接入库标准。"""
        return self.confidence >= 0.7

    def summary(self) -> str:
        return (
            f"product={self.product} direction={self.direction} "
            f"confidence={self.confidence:.2f} need_llm={self.need_llm}"
        )
