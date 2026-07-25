import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from rich.logging import RichHandler

from src.config import settings, connect_db, disconnect_db
from src.middleware import (
    AppError,
    app_error_handler,
    validation_error_handler,
    general_exception_handler,
    value_error_handler,
)
from src.routers import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)],
)

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds security response headers to every HTTP response.

    HSTS is only set in production (NODE_ENV=production) or when the
    incoming request is already over HTTPS, so local HTTP development
    is never broken by a browser downgrade-to-HTTPS enforcement.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Always set — safe for HTTP and HTTPS alike
        response.headers["X-Frame-Options"]           = "DENY"
        response.headers["X-Content-Type-Options"]    = "nosniff"
        response.headers["Referrer-Policy"]           = "strict-origin-when-cross-origin"

        # HSTS — only over HTTPS or in production (where TLS is assumed)
        is_https       = request.url.scheme == "https"
        is_production  = settings.node_env.lower() == "production"
        if is_https or is_production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    logger.info("Connected to database")
    logger.info("Server running on port %s (%s)", settings.port, settings.node_env)

    # Start ARQ Redis pool for background job enqueueing
    try:
        from src.worker.redis_client import get_redis_pool
        await get_redis_pool()
        logger.info("ARQ Redis pool connected")
    except Exception as exc:
        logger.warning("ARQ Redis unavailable — async job queue disabled: %s", exc)

    yield

    from src.worker.redis_client import close_redis_pool
    await close_redis_pool()
    await disconnect_db()
    logger.info("Disconnected from database")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cognitest API",
        description="AI-powered API test generation and execution platform",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.node_env != "production" else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.node_env != "production" else settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    app.add_middleware(SecurityHeadersMiddleware)

    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.node_env != "production",
    )
