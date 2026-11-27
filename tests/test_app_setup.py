import uuid
from datetime import UTC

from fastapi.testclient import TestClient

from app.config import MAX_AMOUNT_MINOR, SUPPORTED_CURRENCIES, Settings
from app.errors import AppError
from app.main import create_app
from app.providers import SystemClockProvider, UuidIdentifierProvider


def test_settings_defaults_and_env(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_PATH", "/tmp/test_ledger.db")
    monkeypatch.setenv("ADMIN_TOKEN", "secret-token")
    monkeypatch.setenv("SQLITE_BUSY_TIMEOUT_MS", "3000")

    settings = Settings.from_env()
    assert settings.database_path == "/tmp/test_ledger.db"
    assert settings.admin_token == "secret-token"
    assert settings.sqlite_busy_timeout_ms == 3000
    assert settings.supported_currencies == SUPPORTED_CURRENCIES
    assert settings.max_amount_minor == MAX_AMOUNT_MINOR


def test_providers() -> None:
    clock = SystemClockProvider()
    now = clock.now_utc()
    assert now.tzinfo == UTC

    ids = UuidIdentifierProvider()
    generated = ids.new_id()
    parsed = uuid.UUID(generated)
    assert str(parsed) == generated


def test_error_responses_format() -> None:
    app = create_app(Settings())

    @app.get("/test-app-error")
    def trigger_app_error() -> None:
        raise AppError(
            status_code=503,
            code="DATABASE_BUSY",
            message="Database is busy, please retry.",
            headers={"Retry-After": "1"},
        )

    @app.get("/test-crash")
    def trigger_crash() -> None:
        raise RuntimeError("SELECT * FROM secret_table at /app/secret.py")

    client = TestClient(app, raise_server_exceptions=False)

    res_busy = client.get("/test-app-error")
    assert res_busy.status_code == 503
    assert res_busy.headers.get("retry-after") == "1"
    assert res_busy.json() == {
        "code": "DATABASE_BUSY",
        "message": "Database is busy, please retry.",
    }

    res_crash = client.get("/test-crash")
    assert res_crash.status_code == 500
    assert res_crash.json() == {
        "code": "INTERNAL_ERROR",
        "message": "Internal server error.",
    }
