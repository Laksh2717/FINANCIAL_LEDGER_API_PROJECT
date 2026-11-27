import os
from dataclasses import dataclass

MAX_AMOUNT_MINOR = 1_000_000_000_000
SUPPORTED_CURRENCIES = ("INR", "USD")
DEFAULT_DATABASE_PATH = "./ledger.db"
DEFAULT_SQLITE_BUSY_TIMEOUT_MS = 5000


@dataclass(frozen=True)
class Settings:
    database_path: str = DEFAULT_DATABASE_PATH
    admin_token: str | None = None
    sqlite_busy_timeout_ms: int = DEFAULT_SQLITE_BUSY_TIMEOUT_MS
    supported_currencies: tuple[str, ...] = SUPPORTED_CURRENCIES
    max_amount_minor: int = MAX_AMOUNT_MINOR

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=os.getenv("DATABASE_PATH", DEFAULT_DATABASE_PATH),
            admin_token=os.getenv("ADMIN_TOKEN"),
            sqlite_busy_timeout_ms=int(
                os.getenv("SQLITE_BUSY_TIMEOUT_MS", str(DEFAULT_SQLITE_BUSY_TIMEOUT_MS))
            ),
        )
