import sqlite3
from dataclasses import dataclass

from app.errors import AppError


@dataclass(frozen=True)
class UserRecord:
    id: str
    name: str
    email: str | None
    created_at: str


def create_user(
    conn: sqlite3.Connection,
    user_id: str,
    name: str,
    email: str,
    created_at: str,
) -> UserRecord:
    try:
        conn.execute(
            "INSERT INTO users (id, name, email, created_at) VALUES (?, ?, ?, ?)",
            (user_id, name, email, created_at),
        )
    except sqlite3.IntegrityError as exc:
        raise AppError(409, "CONFLICT", "A user with this email already exists.") from exc
    return UserRecord(id=user_id, name=name, email=email, created_at=created_at)


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> UserRecord | None:
    row = conn.execute(
        "SELECT id, name, email, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        return None
    return UserRecord(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        created_at=row["created_at"],
    )
