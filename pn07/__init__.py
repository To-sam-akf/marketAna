"""
pn07 LLM 推理模块 LLMInfer

对 pn06 RuleEngine 无法高置信识别的文章调用大语言模型。
通过结构化 Prompt 提取品种、方向、理由和置信度。
低置信（<0.5）自动标记待人工确认。

主要入口:
    infer_article(article_id, session) -> InferResult
"""

from pn07.llm_infer import infer_article, LLMConfig

__all__ = ["infer_article", "LLMConfig"]
