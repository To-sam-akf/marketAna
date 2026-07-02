from typing import Any

from back_end.app.core.exceptions import ErrorCode


def success_response(data: Any | None = None, message: str = "ok") -> dict:
    return {
        "code": int(ErrorCode.OK),
        "message": message,
        "data": data,
    }
