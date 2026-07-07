from back_end.app.api.schemas import datetime_to_iso
from back_end.app.models import AnalysisResult, Article, ArticleText, ManualConfirmation, TaskLog


def serialize_analysis_result(result: AnalysisResult | None) -> dict | None:
    if result is None:
        return None
    return {
        "id": result.id,
        "article_id": result.article_id,
        "product": result.product,
        "contract": result.contract,
        "contract_key": result.contract_key,
        "direction": result.direction,
        "reason": result.reason,
        "confidence": result.confidence,
        "analysis_method": result.analysis_method,
        "need_manual_review": result.need_manual_review,
        "is_primary": result.is_primary,
        "model_name": result.model_name,
        "llm_duration_ms": result.llm_duration_ms,
        "llm_retry_count": result.llm_retry_count,
        "llm_error_msg": result.llm_error_msg,
        "analysis_time": datetime_to_iso(result.analysis_time),
    }


def serialize_article_list_item(article: Article) -> dict:
    result = article.analysis_result
    return {
        "id": article.id,
        "title": article.title,
        "source": article.source,
        "company": article.company,
        "file_url": article.file_url,
        "file_type": article.file_type,
        "publish_time": datetime_to_iso(article.publish_time),
        "status": article.status,
        "error_msg": article.error_msg,
        "created_at": datetime_to_iso(article.created_at),
        "updated_at": datetime_to_iso(article.updated_at),
        "product": result.product if result else None,
        "direction": result.direction if result else None,
        "reason": result.reason if result else None,
        "confidence": result.confidence if result else None,
        "need_manual_review": result.need_manual_review if result else False,
        "analysis_time": datetime_to_iso(result.analysis_time) if result else None,
    }


def serialize_article_text(article_text: ArticleText | None) -> dict | None:
    if article_text is None:
        return None
    return {
        "id": article_text.id,
        "article_id": article_text.article_id,
        "raw_text": article_text.raw_text,
        "cleaned_text": article_text.cleaned_text,
        "raw_length": article_text.raw_length,
        "cleaned_length": article_text.cleaned_length,
        "parser_type": article_text.parser_type,
        "created_at": datetime_to_iso(article_text.created_at),
        "updated_at": datetime_to_iso(article_text.updated_at),
    }


def serialize_task_log(log: TaskLog) -> dict:
    return {
        "id": log.id,
        "article_id": log.article_id,
        "stage": log.stage,
        "status": log.status,
        "message": log.message,
        "duration_ms": log.duration_ms,
        "created_at": datetime_to_iso(log.created_at),
    }


def serialize_manual_confirmation(confirmation: ManualConfirmation) -> dict:
    return {
        "id": confirmation.id,
        "article_id": confirmation.article_id,
        "original_product": confirmation.original_product,
        "original_direction": confirmation.original_direction,
        "original_reason": confirmation.original_reason,
        "original_confidence": confirmation.original_confidence,
        "confirmed_product": confirmation.confirmed_product,
        "confirmed_direction": confirmation.confirmed_direction,
        "confirmed_reason": confirmation.confirmed_reason,
        "confirmed_confidence": confirmation.confirmed_confidence,
        "confirmed_by": confirmation.confirmed_by,
        "note": confirmation.note,
        "confirmed_at": datetime_to_iso(confirmation.confirmed_at),
    }


def serialize_article_detail(article: Article) -> dict:
    return {
        "article": serialize_article_list_item(article),
        "text": serialize_article_text(article.text),
        "analysis_result": serialize_analysis_result(article.analysis_result),
        "analysis_results": [
            serialize_analysis_result(result)
            for result in sorted(
                article.analysis_results,
                key=lambda item: (not item.is_primary, item.product, item.contract_key, item.id),
            )
        ],
        "task_logs": [
            serialize_task_log(log)
            for log in sorted(article.task_logs, key=lambda item: item.id)
        ],
        "manual_confirmations": [
            serialize_manual_confirmation(confirmation)
            for confirmation in sorted(article.manual_confirmations, key=lambda item: item.id)
        ],
    }
