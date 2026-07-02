from fastapi import FastAPI

from back_end.app.api.health import router as health_router
from back_end.app.core.config import get_settings
from back_end.app.core.exceptions import register_exception_handlers
from back_end.app.core.logging import setup_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)

    app = FastAPI(title=settings.app_name)
    register_exception_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
