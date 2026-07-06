"""
pn03 定时调度模块 Scheduler

定时扫描 status=0 的待处理文章，按 FIFO 顺序取固定批次，
逐条触发 Pipeline，并通过行级锁防止重复消费。

主要入口:
    Scheduler(session_factory, pipeline_callback)  — 调度器
    ScanResult                                      — 扫描结果
"""

from pn03.scheduler import Scheduler, noop_callback
from pn03.models import ScanResult

__all__ = ["Scheduler", "ScanResult", "noop_callback"]
