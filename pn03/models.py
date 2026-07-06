"""
pn03 数据模型

定义扫描结果和调度器配置。
"""

from dataclasses import dataclass, field


@dataclass
class ScanResult:
    """单次扫描的结果汇总。

    每个字段记录本轮扫描中各项操作的计数和耗时。
    """

    scanned: int = 0
    """本次扫描到的待处理文章总数（查询结果）"""

    triggered: int = 0
    """成功触发 pipeline 回调的数量（含最终失败）"""

    succeeded: int = 0
    """pipeline 回调返回 True 的数量"""

    failed: int = 0
    """pipeline 回调抛异常或返回 False 的数量"""

    duration_ms: int = 0
    """整次扫描耗时（毫秒）"""

    message: str = ""
    """本次扫描的摘要信息"""

    @property
    def ok(self) -> bool:
        """本次扫描是否无严重错误（允许个别文章失败）。"""
        return True  # 扫描本身成功，个别文章失败不影响调度器稳定性

    @property
    def empty(self) -> bool:
        """是否没有扫描到任何待处理文章。"""
        return self.scanned == 0

    def summary(self) -> str:
        """生成一行可读摘要。"""
        if self.empty:
            return f"[{self.duration_ms}ms] 无待处理文章"
        return (
            f"[{self.duration_ms}ms] "
            f"扫描={self.scanned} "
            f"触发={self.triggered} "
            f"成功={self.succeeded} "
            f"失败={self.failed}"
        )
