from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routers.users import router as users_router
from app.api.routers.wallets import router as wallets_router
from app.config import Settings
from app.errors import AppError
from app.persistence.database import SqliteConnectionProvider
from app.persistence.schema import initialize_database
from app.providers import (
    ClockProvider,
    DatabaseConnectionProvider,
    IdentifierProvider,
    SystemClockProvider,
    UuidIdentifierProvider,
)


def error_response(
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message},
        headers=headers,
    )


def create_app(
    settings: Settings | None = None,
    *,
    clock_provider: ClockProvider | None = None,
    id_provider: IdentifierProvider | None = None,
    db_provider: DatabaseConnectionProvider | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    resolved_clock = clock_provider or SystemClockProvider()
    resolved_ids = id_provider or UuidIdentifierProvider()
    resolved_db = db_provider or SqliteConnectionProvider(
        resolved_settings.database_path,
        busy_timeout_ms=resolved_settings.sqlite_busy_timeout_ms,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        initialize_database(
            app.state.db_provider,
            app.state.clock_provider,
            app.state.id_provider,
            app.state.settings.supported_currencies,
        )
        yield

    app = FastAPI(
        title="Financial Ledger & Digital Wallet API",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.clock_provider = resolved_clock
    app.state.id_provider = resolved_ids
    app.state.db_provider = resolved_db

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(400, "BAD_REQUEST", "Invalid request input.")

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return error_response(exc.status_code, code, message, headers=exc.headers)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
        return error_response(500, "INTERNAL_ERROR", "Internal server error.")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(users_router, prefix="/v1")
    app.include_router(wallets_router, prefix="/v1")

    return app


app = create_app()
