import sqlite3
from contextlib import closing

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.persistence.database import read_transaction, write_transaction
from app.persistence.repositories.idempotency_repository import (
    IdempotencyRecord,
    create_idempotency_record,
    get_idempotency_record,
)

NOW = "2026-11-27T15:00:00+00:00"


def test_idempotency_repository_stores_and_retrieves_record(
    app: FastAPI, client: TestClient
) -> None:
    response_body = '{"id":"transfer-1","amount_minor":125}'

    with closing(app.state.db_provider.get_connection()) as conn:
        with write_transaction(conn):
            stored = create_idempotency_record(
                conn,
                key="request-1",
                request_hash="a" * 64,
                response_status=201,
                response_body=response_body,
                created_at=NOW,
            )

        with read_transaction(conn):
            fetched = get_idempotency_record(conn, "request-1")
            missing = get_idempotency_record(conn, "missing")

    expected = IdempotencyRecord(
        key="request-1",
        request_hash="a" * 64,
        response_status=201,
        response_body=response_body,
        created_at=NOW,
    )
    assert stored == expected
    assert fetched == expected
    assert missing is None


def test_idempotency_repository_leaves_duplicate_key_to_unique_constraint(
    app: FastAPI, client: TestClient
) -> None:
    with closing(app.state.db_provider.get_connection()) as conn:
        with write_transaction(conn):
            create_idempotency_record(conn, "request-1", "a" * 64, 201, "{}", NOW)

        with pytest.raises(sqlite3.IntegrityError), write_transaction(conn):
            create_idempotency_record(conn, "request-1", "b" * 64, 201, "{}", NOW)

        with read_transaction(conn):
            stored = get_idempotency_record(conn, "request-1")

    assert stored is not None
    assert stored.request_hash == "a" * 64
