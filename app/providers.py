import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Protocol


class ClockProvider(Protocol):
    def now_utc(self) -> datetime: ...


class IdentifierProvider(Protocol):
    def new_id(self) -> str: ...


class DatabaseConnectionProvider(Protocol):
    def get_connection(self) -> sqlite3.Connection: ...


class SystemClockProvider:
    def now_utc(self) -> datetime:
        return datetime.now(UTC)


class UuidIdentifierProvider:
    def new_id(self) -> str:
        return str(uuid.uuid4())
