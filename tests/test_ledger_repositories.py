from contextlib import closing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domain.accounting import build_opening_entries, build_transfer_entries
from app.domain.ledger import GENESIS_PREV_HASH, chain_entries
from app.errors import AppError
from app.persistence.database import read_transaction, write_transaction
from app.persistence.repositories.ledger_entry_repository import (
    get_last_entry_hash,
    insert_ledger_entries,
    list_entries_by_transaction,
    list_entries_by_wallet,
)
from app.persistence.repositories.transaction_repository import (
    create_transaction,
    get_transaction_by_id,
    has_reversal,
)
from app.persistence.repositories.user_repository import create_user
from app.persistence.repositories.wallet_repository import (
    create_wallet,
    get_system_wallet,
    get_wallet_by_id,
    update_wallet_balance,
)

NOW = "2026-11-27T15:00:00+00:00"


def test_wallet_repository_crud_and_duplicate_conflict(
    app: FastAPI, client: TestClient
) -> None:
    db = app.state.db_provider
    with closing(db.get_connection()) as conn:
        with write_transaction(conn):
            create_user(conn, "u1", "Alice", "alice@example.com", NOW)
            wallet = create_wallet(conn, "w1", "u1", "INR", 500, NOW)
            update_wallet_balance(conn, "w1", 750)

        with pytest.raises(AppError) as exc, write_transaction(conn):
            create_wallet(conn, "w2", "u1", "INR", 0, NOW)
        assert exc.value.status_code == 409

        with read_transaction(conn):
            fetched = get_wallet_by_id(conn, wallet.id)
            sys_inr = get_system_wallet(conn, "INR")

    assert fetched is not None
    assert fetched.balance_minor == 750
    assert fetched.is_system is False
    assert sys_inr is not None
    assert sys_inr.is_system is True
    assert sys_inr.currency == "INR"


def test_transaction_and_ledger_entry_repositories(
    app: FastAPI, client: TestClient
) -> None:
    db = app.state.db_provider
    with closing(db.get_connection()) as conn:
        with write_transaction(conn):
            create_user(conn, "u1", "Alice", "alice@example.com", NOW)
            create_user(conn, "u2", "Bob", "bob@example.com", NOW)
            create_wallet(conn, "w1", "u1", "INR", 1000, NOW)
            create_wallet(conn, "w2", "u2", "INR", 0, NOW)
            sys_inr = get_system_wallet(conn, "INR")
            assert sys_inr is not None

            assert get_last_entry_hash(conn) == GENESIS_PREV_HASH

            tx1 = create_transaction(conn, "tx1", "opening", 1000, "INR", NOW)
            chained1 = chain_entries(
                build_opening_entries("w1", sys_inr.id, 1000, "INR"),
                transaction_id=tx1.id,
                created_at=NOW,
                initial_prev_hash=get_last_entry_hash(conn),
            )
            inserted1 = insert_ledger_entries(conn, chained1)
            assert [e.seq for e in inserted1] == [1, 2]

            tx2 = create_transaction(conn, "tx2", "transfer", 250, "INR", NOW)
            chained2 = chain_entries(
                build_transfer_entries("w1", "w2", 250, "INR"),
                transaction_id=tx2.id,
                created_at=NOW,
                initial_prev_hash=get_last_entry_hash(conn),
            )
            inserted2 = insert_ledger_entries(conn, chained2)
            assert [e.seq for e in inserted2] == [3, 4]
            assert inserted2[0].prev_hash == inserted1[-1].entry_hash

            create_transaction(
                conn,
                "tx3",
                "reversal",
                250,
                "INR",
                NOW,
                reverses_transaction_id="tx2",
            )

        with pytest.raises(AppError) as dup_rev, write_transaction(conn):
            create_transaction(
                conn,
                "tx4",
                "reversal",
                250,
                "INR",
                NOW,
                reverses_transaction_id="tx2",
            )
        assert dup_rev.value.status_code == 409

        with read_transaction(conn):
            assert get_transaction_by_id(conn, "tx2") is not None
            assert has_reversal(conn, "tx2") is True
            assert has_reversal(conn, "tx1") is False

            tx2_entries = list_entries_by_transaction(conn, "tx2")
            assert [e.direction for e in tx2_entries] == ["DEBIT", "CREDIT"]

            w1_entries = list_entries_by_wallet(conn, "w1", limit=1, offset=0)
            assert len(w1_entries) == 1
            assert w1_entries[0].seq == 3  # newest first
            w1_older = list_entries_by_wallet(conn, "w1", limit=1, offset=1)
            assert w1_older[0].seq == 2
