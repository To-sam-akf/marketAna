from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from back_end.app.api.articles import router as articles_router
from back_end.app.api.companies import router as companies_router
from back_end.app.api.dashboard import router as dashboard_router
from back_end.app.api.health import router as health_router
from back_end.app.api.products import router as products_router
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(dashboard_router)
    app.include_router(articles_router)
    app.include_router(products_router)
    app.include_router(companies_router)
    app.include_router(trends_router)
    app.include_router(tasks_router)
    app.include_router(results_router)
    return app

# 创建 FastAPI 应用实例
app = create_app()
