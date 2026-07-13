"""Shared frontend-display predicates."""

from typing import Any

from sqlalchemy import and_, func, or_


UNKNOWN_PRODUCT = "未知"


def is_displayable_product(product: str | None) -> bool:
    """Return whether an analysis product should be exposed by frontend APIs."""
    normalized = (product or "").strip()
    return bool(normalized) and normalized != UNKNOWN_PRODUCT


def is_displayable_analysis_result(result: Any) -> bool:
    return is_displayable_product(getattr(result, "product", None))


def displayable_product_clause(product_column: Any):
    product = func.trim(product_column)
    return and_(product != "", product != UNKNOWN_PRODUCT)


def formal_analysis_clause(result_model: Any):
    """Exclude evidence-less review suggestions from formal aggregations."""
    return and_(
        displayable_product_clause(result_model.product),
        or_(
            result_model.need_manual_review.is_(False),
            and_(
                result_model.reason.is_not(None),
                func.trim(result_model.reason) != "",
            ),
        ),
    )
