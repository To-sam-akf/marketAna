from enum import IntEnum


class ArticleProcessingStatus(IntEnum):
    FAILED = -1
    PENDING = 0
    PARSED = 1
    CLEANED = 2
    RULE_ANALYZED = 3
    LLM_INFERRED = 4
    STORED = 5


ARTICLE_STATUS_VALUES = tuple(status.value for status in ArticleProcessingStatus)
