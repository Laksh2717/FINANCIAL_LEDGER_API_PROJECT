import sqlite3
from contextlib import closing

from app.config import SUPPORTED_CURRENCIES
from app.persistence.database import write_transaction
from app.providers import ClockProvider, DatabaseConnectionProvider, IdentifierProvider

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"
SYSTEM_USER_NAME = "SYSTEM"

SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS wallets (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id),
        currency TEXT NOT NULL CHECK (currency IN ('INR', 'USD')),
        balance_minor INTEGER NOT NULL,
        is_system INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0, 1)),
        created_at TEXT NOT NULL,
        UNIQUE (user_id, currency),
        CHECK (is_system = 1 OR balance_minor >= 0)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ledger_transactions (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL CHECK (type IN ('opening', 'transfer', 'reversal')),
        amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
        currency TEXT NOT NULL CHECK (currency IN ('INR', 'USD')),
        reverses_transaction_id TEXT UNIQUE REFERENCES ledger_transactions(id),
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ledger_entries (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT NOT NULL REFERENCES ledger_transactions(id),
        wallet_id TEXT NOT NULL REFERENCES wallets(id),
        direction TEXT NOT NULL CHECK (direction IN ('DEBIT', 'CREDIT')),
        amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
        currency TEXT NOT NULL CHECK (currency IN ('INR', 'USD')),
        created_at TEXT NOT NULL,
        prev_hash TEXT NOT NULL,
        entry_hash TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS idempotency_keys (
        key TEXT PRIMARY KEY,
        request_hash TEXT NOT NULL,
        response_status INTEGER NOT NULL,
        response_body TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_ledger_transactions_no_update
    BEFORE UPDATE ON ledger_transactions
    BEGIN
        SELECT RAISE(ABORT, 'ledger_transactions records are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_ledger_transactions_no_delete
    BEFORE DELETE ON ledger_transactions
    BEGIN
        SELECT RAISE(ABORT, 'ledger_transactions records are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_ledger_entries_no_update
    BEFORE UPDATE ON ledger_entries
    BEGIN
        SELECT RAISE(ABORT, 'ledger_entries records are immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_ledger_entries_no_delete
    BEFORE DELETE ON ledger_entries
    BEGIN
        SELECT RAISE(ABORT, 'ledger_entries records are immutable');
    END
    """,
)


def apply_schema(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)


def seed_system_accounts(
    conn: sqlite3.Connection,
    now_iso: str,
    id_provider: IdentifierProvider,
    supported_currencies: tuple[str, ...] = SUPPORTED_CURRENCIES,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO users (id, name, email, created_at) VALUES (?, ?, NULL, ?)",
        (SYSTEM_USER_ID, SYSTEM_USER_NAME, now_iso),
    )
    for currency in supported_currencies:
        conn.execute(
            "INSERT OR IGNORE INTO wallets "
            "(id, user_id, currency, balance_minor, is_system, created_at) "
            "VALUES (?, ?, ?, 0, 1, ?)",
            (id_provider.new_id(), SYSTEM_USER_ID, currency, now_iso),
        )


def initialize_database(
    db_provider: DatabaseConnectionProvider,
    clock_provider: ClockProvider,
    id_provider: IdentifierProvider,
    supported_currencies: tuple[str, ...] = SUPPORTED_CURRENCIES,
) -> None:
    now_iso = clock_provider.now_utc().isoformat()
    with closing(db_provider.get_connection()) as conn, write_transaction(conn):
        apply_schema(conn)
        seed_system_accounts(conn, now_iso, id_provider, supported_currencies)
