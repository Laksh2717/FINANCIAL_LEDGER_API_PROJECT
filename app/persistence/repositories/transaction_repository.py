import sqlite3
from dataclasses import dataclass

from app.errors import AppError


@dataclass(frozen=True)
class TransactionRecord:
    id: str
    type: str
    amount_minor: int
    currency: str
    reverses_transaction_id: str | None
    created_at: str


def _row_to_transaction(row: sqlite3.Row) -> TransactionRecord:
    return TransactionRecord(
        id=row["id"],
        type=row["type"],
        amount_minor=row["amount_minor"],
        currency=row["currency"],
        reverses_transaction_id=row["reverses_transaction_id"],
        created_at=row["created_at"],
    )


def create_transaction(
    conn: sqlite3.Connection,
    transaction_id: str,
    tx_type: str,
    amount_minor: int,
    currency: str,
    created_at: str,
    *,
    reverses_transaction_id: str | None = None,
) -> TransactionRecord:
    try:
        conn.execute(
            "INSERT INTO ledger_transactions "
            "(id, type, amount_minor, currency, reverses_transaction_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (transaction_id, tx_type, amount_minor, currency, reverses_transaction_id, created_at),
        )
    except sqlite3.IntegrityError as exc:
        if reverses_transaction_id is not None:
            raise AppError(409, "CONFLICT", "Transfer has already been reversed.") from exc
        raise
    return TransactionRecord(
        id=transaction_id,
        type=tx_type,
        amount_minor=amount_minor,
        currency=currency,
        reverses_transaction_id=reverses_transaction_id,
        created_at=created_at,
    )


def get_transaction_by_id(
    conn: sqlite3.Connection,
    transaction_id: str,
) -> TransactionRecord | None:
    row = conn.execute(
        "SELECT id, type, amount_minor, currency, reverses_transaction_id, created_at "
        "FROM ledger_transactions WHERE id = ?",
        (transaction_id,),
    ).fetchone()
    return None if row is None else _row_to_transaction(row)


def has_reversal(conn: sqlite3.Connection, transaction_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM ledger_transactions WHERE reverses_transaction_id = ? LIMIT 1",
        (transaction_id,),
    ).fetchone()
    return row is not None
