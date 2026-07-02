from fastapi import APIRouter

from back_end.app.api.schemas import TaskRunRequest
from back_end.app.core.responses import success_response

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("/run")
def run_task(request: TaskRunRequest | None = None) -> dict:
    return success_response(
        {
            "triggered": False,
            "article_id": request.article_id if request else None,
            "limit": request.limit if request else None,
            "message": "Pipeline runner is not wired yet",
        }
    )
