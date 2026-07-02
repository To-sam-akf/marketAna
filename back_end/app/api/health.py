from fastapi import APIRouter

from back_end.app.core.config import get_settings
from back_end.app.core.database import check_database_connection
from back_end.app.core.responses import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    database_status = check_database_connection(settings.database_url)
    return success_response(
        {
            "status": "ok",
            "database": database_status,
        }
    )
