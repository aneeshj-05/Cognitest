import logging
import traceback
from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.config import settings

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Application-level error with an explicit HTTP status code."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.message},
    )


def _sanitize_error_item(item: Any) -> Any:
    from typing import Dict, List, Tuple
    if isinstance(item, dict):
        return {k: _sanitize_error_item(v) for k, v in item.items()}
    elif isinstance(item, list):
        return [_sanitize_error_item(x) for x in item]
    elif isinstance(item, tuple):
        return tuple(_sanitize_error_item(x) for x in item)
    elif isinstance(item, (str, int, float, bool, type(None))):
        return item
    else:
        return str(item)


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    from typing import Any
    sanitized_details = _sanitize_error_item(exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation error",
            "details": sanitized_details,
        },
    )


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    logger.warning("ValueError on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"status": "error", "message": str(exc)},
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    content: dict = {"status": "error", "message": "Internal Server Error"}
    if settings.node_env == "development":
        content["detail"] = str(exc)
        content["stack"] = traceback.format_exc()
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=content,
    )
