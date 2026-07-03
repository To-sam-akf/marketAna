"""
pn11 流水线联调与异常处理

将 pn03-pn07 串成完整的端到端流水线。

主要入口:
    run_pipeline(article_id, session) → bool   # pn03 Scheduler 的 callback
    batch_process(article_ids, session_factory)  # 批量并发处理
"""

from pn11.pipeline import run_pipeline
from pn11.batch import batch_process
from pn11.models import PipelineResult, BatchResult

__all__ = ["run_pipeline", "batch_process", "PipelineResult", "BatchResult"]
