"""
pn06 规则识别模块 RuleEngine

优先使用关键词词典+正则规则识别期货品种和走势方向。
高置信度（≥0.7）直接入库，低置信度交由 pn07 LLMInfer 处理。

主要入口:
    analyze_article(article_id, session) -> RuleResult
"""

from pn06.rule_engine import analyze_article, RuleConfig

__all__ = ["analyze_article", "RuleConfig"]
