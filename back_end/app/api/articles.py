from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from back_end.app.api.serializers import serialize_article_detail, serialize_article_list_item
from back_end.app.core.database import get_session
from back_end.app.core.responses import success_response
from back_end.app.repositories import ArticleRepository

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("")
def list_articles(
    product: str | None = None,
    company: str | None = None,
    direction: str | None = None,
    status: int | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    repository = ArticleRepository(session)
    items, total = repository.list_articles(
        product=product,
        company=company,
        direction=direction,
        status=status,
        start_time=start_time,
        end_time=end_time,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return success_response(
        {
            "items": [serialize_article_list_item(article) for article in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{article_id}")
def get_article_detail(
    article_id: int,
    session: Session = Depends(get_session),
) -> dict:
    repository = ArticleRepository(session)
    article = repository.get_article_detail(article_id)
    if article is None:
        repository.require_article(article_id)
    return success_response(serialize_article_detail(article))
