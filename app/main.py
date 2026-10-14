from contextlib import asynccontextmanager
import logging
import re
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.errors import APIError
from app.core.rate_limit import LoginRateLimiter
from app.database import engine, get_db
from app.documents.router import router as documents_router
from app.health.router import router as health_router
from app.user.router import router as user_router

logger = logging.getLogger("niramaya.api")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Schema changes are managed by Alembic, never implicitly applied here.
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Niramaya-AI API",
        version="1.0.0",
        description="Account registration, login, and protected profile APIs.",
        lifespan=lifespan,
    )
    app.state.login_rate_limiter = LoginRateLimiter(max_attempts=10, window_seconds=60)
    app.state.health_rate_limiter = LoginRateLimiter(max_attempts=30, window_seconds=60)

    if settings.FRONTEND_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.FRONTEND_ORIGINS,
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
        )

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        proposed_id = request.headers.get("X-Request-ID", "")
        request_id = proposed_id if _REQUEST_ID_PATTERN.fullmatch(proposed_id) else str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "request_id": request.state.request_id}},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        safe_errors = [
            {"location": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "The request contains invalid fields.",
                    "fields": safe_errors,
                    "request_id": request.state.request_id,
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code, message = {
            401: ("authentication_required", "A valid bearer token is required."),
            404: ("not_found", "The requested resource was not found."),
            405: ("method_not_allowed", "This method is not allowed for the requested resource."),
        }.get(exc.status_code, ("request_failed", "The request could not be completed."))
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": message, "request_id": request.state.request_id}},
            headers=exc.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        unavailable = isinstance(exc, (OperationalError, InterfaceError)) or bool(
            getattr(exc, "connection_invalidated", False)
        )
        status_code = 503 if unavailable else 500
        code = "database_unavailable" if unavailable else "database_error"
        message = "The database is temporarily unavailable." if unavailable else "A database operation failed."
        logger.error(
            "Database request failed request_id=%s error_type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": code, "message": message, "request_id": request.state.request_id}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "Unhandled request failure request_id=%s error_type=%s",
            request.state.request_id,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected server error occurred.",
                    "request_id": request.state.request_id,
                }
            },
        )

    app.include_router(user_router)
    app.include_router(health_router)
    app.include_router(documents_router)

    @app.get("/health", tags=["health"])
    async def health(db=Depends(get_db)) -> dict[str, str]:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}

    return app


app = create_app()
