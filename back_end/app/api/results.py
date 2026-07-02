from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from back_end.app.api.schemas import ConfirmResultRequest
from back_end.app.api.serializers import serialize_manual_confirmation
from back_end.app.core.database import get_session
from back_end.app.core.responses import success_response
from back_end.app.repositories import ArticleRepository

router = APIRouter(prefix="/api/results", tags=["results"])


@router.post("/{result_id}/confirm")
def confirm_result(
    result_id: int,
    request: ConfirmResultRequest,
    session: Session = Depends(get_session),
) -> dict:
    repository = ArticleRepository(session)
    confirmation = repository.confirm_result(
        result_id,
        product=request.product,
        direction=request.direction,
        reason=request.reason,
        confidence=request.confidence,
        confirmed_by=request.confirmed_by,
        note=request.note,
    )
    session.commit()
    return success_response(serialize_manual_confirmation(confirmation))
