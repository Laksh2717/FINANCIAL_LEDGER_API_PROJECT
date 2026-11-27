import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.persistence.database import SqliteConnectionProvider, write_transaction
from app.persistence.schema import apply_schema

NOW = "2026-11-27T14:00:00+00:00"


def _setup_conn(tmp_path: Path) -> sqlite3.Connection:
    provider = SqliteConnectionProvider(str(tmp_path / "ledger.db"))
    conn = provider.get_connection()
    with write_transaction(conn):
        apply_schema(conn)
    return conn


def test_schema_creates_expected_tables_and_triggers(tmp_path: Path) -> None:
    with closing(_setup_conn(tmp_path)) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert {
            "users",
            "wallets",
            "ledger_transactions",
            "ledger_entries",
            "idempotency_keys",
        }.issubset(tables)

        triggers = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'trigger'"
            ).fetchall()
        }
        assert triggers == {
            "trg_ledger_transactions_no_update",
            "trg_ledger_transactions_no_delete",
            "trg_ledger_entries_no_update",
            "trg_ledger_entries_no_delete",
        }


def test_wallet_constraints_reject_negative_user_balance_and_duplicate_currency(
    tmp_path: Path,
) -> None:
    with closing(_setup_conn(tmp_path)) as conn:
        with write_transaction(conn):
            conn.execute(
                "INSERT INTO users (id, name, email, created_at) VALUES (?, ?, ?, ?)",
                ("u1", "Alice", "alice@example.com", NOW),
            )
            conn.execute(
                "INSERT INTO users (id, name, email, created_at) VALUES (?, ?, ?, ?)",
                ("sys", "System", None, NOW),
            )
            # System wallet is allowed to have negative balance
            conn.execute(
                "INSERT INTO wallets (id, user_id, currency, balance_minor, is_system, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("w_sys", "sys", "INR", -500, 1, NOW),
            )
            conn.execute(
                "INSERT INTO wallets (id, user_id, currency, balance_minor, is_system, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("w1", "u1", "INR", 100, 0, NOW),
            )

        # Duplicate (user_id, currency) must fail
        with pytest.raises(sqlite3.IntegrityError), write_transaction(conn):
            conn.execute(
                "INSERT INTO wallets (id, user_id, currency, balance_minor, is_system, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("w1_dup", "u1", "INR", 0, 0, NOW),
            )

        # Negative user wallet balance must fail
        with pytest.raises(sqlite3.IntegrityError), write_transaction(conn):
            conn.execute(
                "INSERT INTO wallets (id, user_id, currency, balance_minor, is_system, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("w_neg", "u1", "USD", -1, 0, NOW),
            )


def test_reversal_uniqueness_and_positive_entry_amounts(tmp_path: Path) -> None:
    with closing(_setup_conn(tmp_path)) as conn:
        with write_transaction(conn):
            conn.execute(
                "INSERT INTO users (id, name, email, created_at) VALUES (?, ?, ?, ?)",
                ("u1", "Alice", "alice@example.com", NOW),
            )
            conn.execute(
                "INSERT INTO wallets (id, user_id, currency, balance_minor, is_system, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("w1", "u1", "INR", 1000, 0, NOW),
            )
            conn.execute(
                "INSERT INTO ledger_transactions "
                "(id, type, amount_minor, currency, reverses_transaction_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("tx1", "transfer", 100, "INR", None, NOW),
            )
            conn.execute(
                "INSERT INTO ledger_transactions "
                "(id, type, amount_minor, currency, reverses_transaction_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("tx_rev1", "reversal", 100, "INR", "tx1", NOW),
            )

        # Second reversal referencing tx1 must fail
        with pytest.raises(sqlite3.IntegrityError), write_transaction(conn):
            conn.execute(
                "INSERT INTO ledger_transactions "
                "(id, type, amount_minor, currency, reverses_transaction_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("tx_rev2", "reversal", 100, "INR", "tx1", NOW),
            )

        # Zero entry amount must fail
        with pytest.raises(sqlite3.IntegrityError), write_transaction(conn):
            conn.execute(
                "INSERT INTO ledger_entries "
                "(transaction_id, wallet_id, direction, amount_minor, currency, "
                "created_at, prev_hash, entry_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("tx1", "w1", "DEBIT", 0, "INR", NOW, "0" * 64, "a" * 64),
            )


def test_immutability_triggers_block_update_and_delete(tmp_path: Path) -> None:
    with closing(_setup_conn(tmp_path)) as conn:
        with write_transaction(conn):
            conn.execute(
                "INSERT INTO users (id, name, email, created_at) VALUES (?, ?, ?, ?)",
                ("u1", "Alice", "alice@example.com", NOW),
            )
            conn.execute(
                "INSERT INTO wallets (id, user_id, currency, balance_minor, is_system, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("w1", "u1", "INR", 100, 0, NOW),
            )
            conn.execute(
                "INSERT INTO ledger_transactions "
                "(id, type, amount_minor, currency, reverses_transaction_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("tx1", "opening", 100, "INR", None, NOW),
            )
            conn.execute(
                "INSERT INTO ledger_entries "
                "(transaction_id, wallet_id, direction, amount_minor, currency, "
                "created_at, prev_hash, entry_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("tx1", "w1", "CREDIT", 100, "INR", NOW, "0" * 64, "b" * 64),
            )

        with pytest.raises(sqlite3.IntegrityError, match="immutable"), write_transaction(conn):
            conn.execute("UPDATE ledger_entries SET amount_minor = 999 WHERE seq = 1")

        with pytest.raises(sqlite3.IntegrityError, match="immutable"), write_transaction(conn):
            conn.execute("DELETE FROM ledger_entries WHERE seq = 1")

        with pytest.raises(sqlite3.IntegrityError, match="immutable"), write_transaction(conn):
            conn.execute("UPDATE ledger_transactions SET amount_minor = 999 WHERE id = 'tx1'")

        with pytest.raises(sqlite3.IntegrityError, match="immutable"), write_transaction(conn):
            conn.execute("DELETE FROM ledger_transactions WHERE id = 'tx1'")
