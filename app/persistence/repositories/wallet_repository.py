import sqlite3
from dataclasses import dataclass

from app.domain.rules import WalletState
from app.errors import AppError


@dataclass(frozen=True)
class WalletRecord:
    id: str
    user_id: str
    currency: str
    balance_minor: int
    is_system: bool
    created_at: str

    def to_state(self) -> WalletState:
        return WalletState(
            id=self.id,
            currency=self.currency,
            balance_minor=self.balance_minor,
            is_system=self.is_system,
        )


def _row_to_wallet(row: sqlite3.Row) -> WalletRecord:
    return WalletRecord(
        id=row["id"],
        user_id=row["user_id"],
        currency=row["currency"],
        balance_minor=row["balance_minor"],
        is_system=bool(row["is_system"]),
        created_at=row["created_at"],
    )


def create_wallet(
    conn: sqlite3.Connection,
    wallet_id: str,
    user_id: str,
    currency: str,
    balance_minor: int,
    created_at: str,
    *,
    is_system: bool = False,
) -> WalletRecord:
    try:
        conn.execute(
            "INSERT INTO wallets "
            "(id, user_id, currency, balance_minor, is_system, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (wallet_id, user_id, currency, balance_minor, int(is_system), created_at),
        )
    except sqlite3.IntegrityError as exc:
        raise AppError(
            409,
            "CONFLICT",
            "Wallet already exists for this user and currency.",
        ) from exc
    return WalletRecord(
        id=wallet_id,
        user_id=user_id,
        currency=currency,
        balance_minor=balance_minor,
        is_system=is_system,
        created_at=created_at,
    )


def get_wallet_by_id(conn: sqlite3.Connection, wallet_id: str) -> WalletRecord | None:
    row = conn.execute(
        "SELECT id, user_id, currency, balance_minor, is_system, created_at "
        "FROM wallets WHERE id = ?",
        (wallet_id,),
    ).fetchone()
    return None if row is None else _row_to_wallet(row)


def get_system_wallet(conn: sqlite3.Connection, currency: str) -> WalletRecord | None:
    row = conn.execute(
        "SELECT id, user_id, currency, balance_minor, is_system, created_at "
        "FROM wallets WHERE is_system = 1 AND currency = ?",
        (currency,),
    ).fetchone()
    return None if row is None else _row_to_wallet(row)


def update_wallet_balance(
    conn: sqlite3.Connection,
    wallet_id: str,
    new_balance_minor: int,
) -> None:
    conn.execute(
        "UPDATE wallets SET balance_minor = ? WHERE id = ?",
        (new_balance_minor, wallet_id),
    )
