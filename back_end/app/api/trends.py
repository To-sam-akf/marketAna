from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from back_end.app.core.database import get_session
from back_end.app.core.responses import success_response
from back_end.app.repositories import ArticleRepository

router = APIRouter(prefix="/api/trends", tags=["trends"])


@router.get("")
def get_trends(
    product: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    session: Session = Depends(get_session),
) -> dict:
    repository = ArticleRepository(session)
    return success_response(
        {
            "items": repository.get_trends(
                product=product,
                start_time=start_time,
                end_time=end_time,
            )
        }
    )
