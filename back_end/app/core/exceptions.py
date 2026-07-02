from enum import IntEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorCode(IntEnum):
    OK = 0
    INTERNAL_ERROR = 10000
    VALIDATION_ERROR = 10001
    DATABASE_UNCONFIGURED = 20001
    DATABASE_ERROR = 20002
    LLM_UNCONFIGURED = 30001


class AppException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        detail: Any | None = None,
        status_code: int = 400,
    ) -> None:
        self.code = code
        self.message = message
        self.detail = detail
        self.status_code = status_code


def error_payload(code: ErrorCode, message: str, detail: Any | None = None) -> dict:
    return {
        "code": int(code),
        "message": message,
        "data": None,
        "detail": detail,
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def handle_app_exception(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_payload(
                ErrorCode.VALIDATION_ERROR,
                "Request validation failed",
                exc.errors(),
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=error_payload(ErrorCode.INTERNAL_ERROR, "Internal server error"),
        )
