import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class IdempotencyRecord:
    key: str
    request_hash: str
    response_status: int
    response_body: str
    created_at: str


def _row_to_record(row: sqlite3.Row) -> IdempotencyRecord:
    return IdempotencyRecord(
        key=row["key"],
        request_hash=row["request_hash"],
        response_status=row["response_status"],
        response_body=row["response_body"],
        created_at=row["created_at"],
    )


def get_idempotency_record(
    conn: sqlite3.Connection,
    key: str,
) -> IdempotencyRecord | None:
    row = conn.execute(
        "SELECT key, request_hash, response_status, response_body, created_at "
        "FROM idempotency_keys WHERE key = ?",
        (key,),
    ).fetchone()
    return None if row is None else _row_to_record(row)


def create_idempotency_record(
    conn: sqlite3.Connection,
    key: str,
    request_hash: str,
    response_status: int,
    response_body: str,
    created_at: str,
) -> IdempotencyRecord:
    conn.execute(
        "INSERT INTO idempotency_keys "
        "(key, request_hash, response_status, response_body, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (key, request_hash, response_status, response_body, created_at),
    )
    return IdempotencyRecord(
        key=key,
        request_hash=request_hash,
        response_status=response_status,
        response_body=response_body,
        created_at=created_at,
    )
