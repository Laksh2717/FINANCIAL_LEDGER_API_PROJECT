import uuid
from contextlib import closing

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import MAX_AMOUNT_MINOR
from app.domain.accounting import build_transfer_entries
from app.domain.ledger import chain_entries
from app.persistence.database import read_transaction, write_transaction
from app.persistence.repositories.ledger_entry_repository import (
    get_last_entry_hash,
    insert_ledger_entries,
)
from app.persistence.repositories.transaction_repository import create_transaction
from app.persistence.repositories.wallet_repository import get_system_wallet
from app.persistence.schema import SYSTEM_USER_ID


def _create_user(client: TestClient, name: str = "Alice", email: str = "alice@example.com") -> str:
    res = client.post("/v1/users", json={"name": name, "email": email})
    assert res.status_code == 201
    return res.json()["id"]


def test_create_wallet_zero_and_positive_opening_balance(
    app: FastAPI, client: TestClient
) -> None:
    user_id = _create_user(client)

    usd_res = client.post("/v1/wallets", json={"user_id": user_id, "currency": "USD"})
    assert usd_res.status_code == 201
    usd_wallet = usd_res.json()
    uuid.UUID(usd_wallet["id"])
    assert usd_wallet["balance_minor"] == 0
    assert usd_wallet["currency"] == "USD"

    inr_res = client.post(
        "/v1/wallets",
        json={"user_id": user_id, "currency": "INR", "opening_balance_minor": 50_000},
    )
    assert inr_res.status_code == 201
    inr_wallet = inr_res.json()
    assert inr_wallet["balance_minor"] == 50_000

    with closing(app.state.db_provider.get_connection()) as conn, read_transaction(conn):
        sys_inr = get_system_wallet(conn, "INR")
        assert sys_inr is not None
        assert sys_inr.balance_minor == -50_000

        entries = conn.execute(
            "SELECT wallet_id, direction, amount_minor, currency "
            "FROM ledger_entries ORDER BY seq ASC"
        ).fetchall()

    assert len(entries) == 2
    assert [(e["wallet_id"], e["direction"], e["amount_minor"]) for e in entries] == [
        (sys_inr.id, "DEBIT", 50_000),
        (inr_wallet["id"], "CREDIT", 50_000),
    ]


def test_create_wallet_duplicate_returns_409_and_unknown_user_404(
    client: TestClient,
) -> None:
    user_id = _create_user(client)
    first = client.post("/v1/wallets", json={"user_id": user_id, "currency": "INR"})
    assert first.status_code == 201

    dup = client.post("/v1/wallets", json={"user_id": user_id, "currency": "INR"})
    assert dup.status_code == 409
    assert dup.json()["code"] == "CONFLICT"

    missing_user = client.post(
        "/v1/wallets",
        json={"user_id": str(uuid.uuid4()), "currency": "INR"},
    )
    assert missing_user.status_code == 404
    assert missing_user.json()["code"] == "NOT_FOUND"

    sys_user = client.post(
        "/v1/wallets",
        json={"user_id": SYSTEM_USER_ID, "currency": "INR"},
    )
    assert sys_user.status_code == 422


def test_create_wallet_rejects_invalid_inputs_without_writing(
    app: FastAPI, client: TestClient
) -> None:
    user_id = _create_user(client)

    bad_400_payloads = [
        {"user_id": "not-a-uuid", "currency": "INR"},
        {"user_id": user_id, "currency": "INR", "opening_balance_minor": -10},
        {"user_id": user_id, "currency": "INR", "opening_balance_minor": 10.5},
        {"user_id": user_id, "currency": "INR", "opening_balance_minor": "100"},
        {"user_id": user_id, "currency": "INR", "opening_balance_minor": True},
    ]
    for payload in bad_400_payloads:
        res = client.post("/v1/wallets", json=payload)
        assert res.status_code == 400
        assert res.json()["code"] == "BAD_REQUEST"

    unsupported = client.post("/v1/wallets", json={"user_id": user_id, "currency": "EUR"})
    assert unsupported.status_code == 422
    assert unsupported.json()["code"] == "UNSUPPORTED_CURRENCY"

    too_large = client.post(
        "/v1/wallets",
        json={
            "user_id": user_id,
            "currency": "INR",
            "opening_balance_minor": MAX_AMOUNT_MINOR + 1,
        },
    )
    assert too_large.status_code == 422

    with closing(app.state.db_provider.get_connection()) as conn, read_transaction(conn):
        user_wallet_count = conn.execute(
            "SELECT COUNT(*) FROM wallets WHERE is_system = 0"
        ).fetchone()[0]
    assert user_wallet_count == 0


def test_get_wallet_and_entries_newest_first_with_pagination(
    app: FastAPI, client: TestClient
) -> None:
    alice_id = _create_user(client, "Alice", "alice@example.com")
    bob_id = _create_user(client, "Bob", "bob@example.com")

    w1_id = client.post(
        "/v1/wallets",
        json={"user_id": alice_id, "currency": "INR", "opening_balance_minor": 1000},
    ).json()["id"]
    w2_id = client.post(
        "/v1/wallets",
        json={"user_id": bob_id, "currency": "INR", "opening_balance_minor": 0},
    ).json()["id"]

    # Add two more ledger entries affecting w1 so we can verify newest-first pagination
    with closing(app.state.db_provider.get_connection()) as conn, write_transaction(conn):
        for idx, amount in enumerate((100, 200), start=1):
            tx_id = f"00000000-0000-0000-0000-00000000000{idx}"
            now = f"2026-11-27T15:0{idx}:00+00:00"
            create_transaction(conn, tx_id, "transfer", amount, "INR", now)
            chained = chain_entries(
                build_transfer_entries(w1_id, w2_id, amount, "INR"),
                transaction_id=tx_id,
                created_at=now,
                initial_prev_hash=get_last_entry_hash(conn),
            )
            insert_ledger_entries(conn, chained)

    get_res = client.get(f"/v1/wallets/{w1_id}")
    assert get_res.status_code == 200
    assert get_res.json()["balance_minor"] == 1000

    page1 = client.get(f"/v1/wallets/{w1_id}/entries?limit=2&offset=0")
    assert page1.status_code == 200
    entries1 = page1.json()["entries"]
    assert len(entries1) == 2
    assert entries1[0]["seq"] > entries1[1]["seq"]
    assert [e["amount_minor"] for e in entries1] == [200, 100]

    page2 = client.get(f"/v1/wallets/{w1_id}/entries?limit=2&offset=2")
    assert page2.status_code == 200
    entries2 = page2.json()["entries"]
    assert len(entries2) == 1
    assert entries2[0]["amount_minor"] == 1000
    assert entries2[0]["direction"] == "CREDIT"


def test_get_wallet_and_entries_validation_and_not_found(client: TestClient) -> None:
    user_id = _create_user(client)
    wallet_id = client.post("/v1/wallets", json={"user_id": user_id, "currency": "USD"}).json()[
        "id"
    ]
    missing_id = str(uuid.uuid4())

    assert client.get("/v1/wallets/bad-id").status_code == 400
    assert client.get(f"/v1/wallets/{missing_id}").status_code == 404

    assert client.get("/v1/wallets/bad-id/entries").status_code == 400
    assert client.get(f"/v1/wallets/{missing_id}/entries").status_code == 404
    assert client.get(f"/v1/wallets/{wallet_id}/entries?limit=0").status_code == 400
    assert client.get(f"/v1/wallets/{wallet_id}/entries?limit=101").status_code == 400
    assert client.get(f"/v1/wallets/{wallet_id}/entries?offset=-1").status_code == 400
    assert client.get(f"/v1/wallets/{wallet_id}/entries?limit=abc").status_code == 400
