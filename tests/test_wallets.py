import uuid
from contextlib import closing

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import MAX_AMOUNT_MINOR
from app.persistence.database import read_transaction
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
