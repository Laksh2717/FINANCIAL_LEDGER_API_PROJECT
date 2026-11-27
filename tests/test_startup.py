import uuid
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.persistence.database import read_transaction
from app.persistence.schema import SYSTEM_USER_ID, SYSTEM_USER_NAME, initialize_database


def test_startup_seeds_system_user_and_wallets_idempotently(
    app: FastAPI, client: TestClient, test_settings: Settings
) -> None:
    assert client.get("/health").status_code == 200
    assert Path(test_settings.database_path).exists()

    with closing(app.state.db_provider.get_connection()) as conn, read_transaction(conn):
        sys_user = conn.execute(
            "SELECT id, name, email FROM users WHERE id = ?",
            (SYSTEM_USER_ID,),
        ).fetchone()
        assert sys_user is not None
        assert sys_user["name"] == SYSTEM_USER_NAME
        assert sys_user["email"] is None

        wallets = conn.execute(
            "SELECT id, currency, balance_minor, is_system FROM wallets "
            "WHERE user_id = ? ORDER BY currency",
            (SYSTEM_USER_ID,),
        ).fetchall()

    assert [(w["currency"], w["balance_minor"], w["is_system"]) for w in wallets] == [
        ("INR", 0, 1),
        ("USD", 0, 1),
    ]
    for wallet in wallets:
        uuid.UUID(wallet["id"])

    initial_ids = [w["id"] for w in wallets]

    # Running initialize_database again must not duplicate or change system wallet IDs
    initialize_database(
        app.state.db_provider,
        app.state.clock_provider,
        app.state.id_provider,
        app.state.settings.supported_currencies,
    )

    with closing(app.state.db_provider.get_connection()) as conn, read_transaction(conn):
        wallets_after = conn.execute(
            "SELECT id, currency FROM wallets WHERE user_id = ? ORDER BY currency",
            (SYSTEM_USER_ID,),
        ).fetchall()

    assert [w["id"] for w in wallets_after] == initial_ids
