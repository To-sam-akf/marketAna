from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from back_end.app.core.database import get_session
from back_end.app.core.responses import success_response
from back_end.app.repositories import ArticleRepository

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(session: Session = Depends(get_session)) -> dict:
    repository = ArticleRepository(session)
    return success_response(repository.get_dashboard_summary())
