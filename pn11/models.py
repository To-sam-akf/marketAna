"""
pn11 流水线数据模型
"""

from dataclasses import dataclass, field


@dataclass
class PipelineResult:
    """单篇文章的流水线执行结果。"""

    article_id: int
    success: bool
    start_status: int            # 流水线入口时的状态
    final_status: int             # 流水线出口时的状态
    stages_run: list[str] = field(default_factory=list)
    error_stage: str = ""         # 失败阶段名（成功时为空）
    error_message: str = ""
    total_duration_ms: int = 0

    def summary(self) -> str:
        stages = "→".join(self.stages_run) or "none"
        status = "OK" if self.success else f"FAIL({self.error_stage})"
        return (
            f"[{self.total_duration_ms}ms] article={self.article_id} "
            f"status={self.start_status}→{self.final_status} "
            f"stages={stages} {status}"
        )


@dataclass
class BatchResult:
    """批量处理结果汇总。"""

    total: int
    succeeded: int
    failed: int
    results: list[PipelineResult] = field(default_factory=list)
    total_duration_ms: int = 0

    @property
    def all_success(self) -> bool:
        return self.failed == 0

    def summary(self) -> str:
        return (
            f"批量处理完成: {self.total}篇, "
            f"成功={self.succeeded}, 失败={self.failed}, "
            f"总耗时={self.total_duration_ms}ms"
        )
