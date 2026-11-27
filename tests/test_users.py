import uuid
from contextlib import closing

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.persistence.database import read_transaction
from app.persistence.repositories.user_repository import get_user_by_id


def test_create_user_succeeds_and_persists(app: FastAPI, client: TestClient) -> None:
    response = client.post(
        "/v1/users",
        json={"name": "  Alice  ", "email": "Alice@Example.COM"},
    )
    assert response.status_code == 201
    body = response.json()
    uuid.UUID(body["id"])
    assert body["name"] == "Alice"
    assert body["email"] == "alice@example.com"
    assert body["created_at"]

    with closing(app.state.db_provider.get_connection()) as conn, read_transaction(conn):
        stored = get_user_by_id(conn, body["id"])
    assert stored is not None
    assert stored.name == "Alice"
    assert stored.email == "alice@example.com"


def test_create_user_duplicate_email_returns_409(client: TestClient) -> None:
    first = client.post(
        "/v1/users",
        json={"name": "Alice", "email": "alice@example.com"},
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/v1/users",
        json={"name": "Alice Two", "email": "ALICE@example.com"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "CONFLICT"


def test_create_user_rejects_malformed_input(client: TestClient) -> None:
    bad_payloads = [
        {},
        {"name": "   ", "email": "alice@example.com"},
        {"name": "Alice", "email": "not-an-email"},
        {"name": 123, "email": "alice@example.com"},
    ]
    for payload in bad_payloads:
        res = client.post("/v1/users", json=payload)
        assert res.status_code == 400
        assert res.json()["code"] == "BAD_REQUEST"
