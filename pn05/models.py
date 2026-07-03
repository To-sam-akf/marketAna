"""
pn05 数据模型

定义清洗配置和清洗结果。
"""

from dataclasses import dataclass, field


@dataclass
class CleanConfig:
    """清洗器配置，所有参数可调。"""

    # 清洗比例阈值
    max_length_ratio: float = 0.95  # 清洗后/前 > 此值 → warn "几乎无清洗效果"
    min_length_ratio: float = 0.05  # 清洗后/前 < 此值 → warn "可能过度清洗"

    # 段落密度
    min_paragraph_chars: int = 10   # 段落最少字符数，低于此值视为噪声行
    min_density_ratio: float = 0.15 # 中文字符/总字符 < 此值 → 低密度块

    # 功能开关
    normalize_whitespace: bool = True    # 统一空白字符
    normalize_fullwidth: bool = True     # 全角→半角转换
    remove_html_residue: bool = True     # 移除 HTML 残留
    filter_noise_lines: bool = True      # 启用噪声规则库过滤
    filter_low_density: bool = True      # 基于密度剔除页眉页脚

    # 输出保护
    max_text_length: int = 500_000       # 最大输出长度（截断保护）


@dataclass
class CleanResult:
    """单次清洗的结果统计。"""

    raw_length: int = 0
    cleaned_length: int = 0
    removal_ratio: float = 0.0           # (raw - cleaned) / raw
    noise_lines_removed: int = 0         # 被噪声规则移除的行数
    low_density_removed: int = 0         # 低密度块被移除的字符数
    duration_ms: int = 0

    @property
    def total_removed(self) -> int:
        """清洗移除的总字符数。"""
        return self.raw_length - self.cleaned_length

    def summary(self) -> str:
        pct = f"{self.removal_ratio * 100:.1f}%"
        return (
            f"[{self.duration_ms}ms] "
            f"raw={self.raw_length} → cleaned={self.cleaned_length} "
            f"({pct} removed) "
            f"noise_lines={self.noise_lines_removed} "
            f"low_density_chars={self.low_density_removed}"
        )
