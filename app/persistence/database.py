import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config import DEFAULT_SQLITE_BUSY_TIMEOUT_MS
from app.errors import AppError


def _is_busy_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message


class SqliteConnectionProvider:
    def __init__(
        self,
        database_path: str,
        busy_timeout_ms: int = DEFAULT_SQLITE_BUSY_TIMEOUT_MS,
    ) -> None:
        self.database_path = database_path
        self.busy_timeout_ms = busy_timeout_ms

    def get_connection(self) -> sqlite3.Connection:
        if self.database_path != ":memory:" and not self.database_path.startswith("file:"):
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(
            self.database_path,
            timeout=self.busy_timeout_ms / 1000.0,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        try:
            conn.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.OperationalError as exc:
            conn.close()
            if _is_busy_error(exc):
                raise _busy_error() from exc
            raise
        except Exception:
            conn.close()
            raise
        return conn


def _busy_error() -> AppError:
    return AppError(
        status_code=503,
        code="DATABASE_BUSY",
        message="Database is busy, please retry.",
        headers={"Retry-After": "1"},
    )


@contextmanager
def _transaction(conn: sqlite3.Connection, begin_sql: str) -> Iterator[sqlite3.Connection]:
    try:
        conn.execute(begin_sql)
        yield conn
        conn.execute("COMMIT")
    except sqlite3.OperationalError as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        if _is_busy_error(exc):
            raise _busy_error() from exc
        raise
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


@contextmanager
def write_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    with _transaction(conn, "BEGIN IMMEDIATE") as tx_conn:
        yield tx_conn


@contextmanager
def read_transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    with _transaction(conn, "BEGIN") as tx_conn:
        yield tx_conn
