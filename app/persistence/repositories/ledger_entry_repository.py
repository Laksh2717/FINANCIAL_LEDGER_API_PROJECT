import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.ledger import GENESIS_PREV_HASH, ChainedEntry


@dataclass(frozen=True)
class LedgerEntryRecord:
    seq: int
    transaction_id: str
    wallet_id: str
    direction: str
    amount_minor: int
    currency: str
    created_at: str
    prev_hash: str
    entry_hash: str


def _row_to_entry(row: sqlite3.Row) -> LedgerEntryRecord:
    return LedgerEntryRecord(
        seq=row["seq"],
        transaction_id=row["transaction_id"],
        wallet_id=row["wallet_id"],
        direction=row["direction"],
        amount_minor=row["amount_minor"],
        currency=row["currency"],
        created_at=row["created_at"],
        prev_hash=row["prev_hash"],
        entry_hash=row["entry_hash"],
    )


def get_last_entry_hash(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT entry_hash FROM ledger_entries ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    return GENESIS_PREV_HASH if row is None else row["entry_hash"]


def insert_ledger_entries(
    conn: sqlite3.Connection,
    entries: Sequence[ChainedEntry],
) -> list[LedgerEntryRecord]:
    inserted: list[LedgerEntryRecord] = []
    for entry in entries:
        cursor = conn.execute(
            "INSERT INTO ledger_entries "
            "(transaction_id, wallet_id, direction, amount_minor, currency, "
            "created_at, prev_hash, entry_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.transaction_id,
                entry.wallet_id,
                entry.direction,
                entry.amount_minor,
                entry.currency,
                entry.created_at,
                entry.prev_hash,
                entry.entry_hash,
            ),
        )
        assert cursor.lastrowid is not None
        inserted.append(
            LedgerEntryRecord(
                seq=cursor.lastrowid,
                transaction_id=entry.transaction_id,
                wallet_id=entry.wallet_id,
                direction=entry.direction,
                amount_minor=entry.amount_minor,
                currency=entry.currency,
                created_at=entry.created_at,
                prev_hash=entry.prev_hash,
                entry_hash=entry.entry_hash,
            )
        )
    return inserted


def list_entries_by_transaction(
    conn: sqlite3.Connection,
    transaction_id: str,
) -> list[LedgerEntryRecord]:
    rows = conn.execute(
        "SELECT seq, transaction_id, wallet_id, direction, amount_minor, currency, "
        "created_at, prev_hash, entry_hash "
        "FROM ledger_entries WHERE transaction_id = ? ORDER BY seq ASC",
        (transaction_id,),
    ).fetchall()
    return [_row_to_entry(row) for row in rows]


def list_entries_by_wallet(
    conn: sqlite3.Connection,
    wallet_id: str,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[LedgerEntryRecord]:
    rows = conn.execute(
        "SELECT seq, transaction_id, wallet_id, direction, amount_minor, currency, "
        "created_at, prev_hash, entry_hash "
        "FROM ledger_entries WHERE wallet_id = ? ORDER BY seq DESC LIMIT ? OFFSET ?",
        (wallet_id, limit, offset),
    ).fetchall()
    return [_row_to_entry(row) for row in rows]
