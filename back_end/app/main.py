from fastapi import FastAPI

from back_end.app.api.articles import router as articles_router
from back_end.app.api.dashboard import router as dashboard_router
from back_end.app.api.health import router as health_router
from back_end.app.api.results import router as results_router
from back_end.app.api.tasks import router as tasks_router
from back_end.app.api.trends import router as trends_router
from back_end.app.core.config import get_settings
from back_end.app.core.exceptions import register_exception_handlers
from back_end.app.core.logging import setup_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)

    app = FastAPI(title=settings.app_name)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(dashboard_router)
    app.include_router(articles_router)
    app.include_router(trends_router)
    app.include_router(tasks_router)
    app.include_router(results_router)
    return app


app = create_app()
