from contextlib import closing
from pathlib import Path

import pytest

from app.errors import AppError
from app.persistence.database import SqliteConnectionProvider, read_transaction, write_transaction


def test_connection_provider_configures_pragmas_and_fresh_connections(tmp_path: Path) -> None:
    db_file = tmp_path / "nested" / "ledger.db"
    provider = SqliteConnectionProvider(str(db_file), busy_timeout_ms=5000)

    with closing(provider.get_connection()) as conn1, closing(provider.get_connection()) as conn2:
        assert conn1 is not conn2
        assert db_file.exists()
        assert conn1.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn1.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn1.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_write_transaction_commits_and_rolls_back(tmp_path: Path) -> None:
    db_file = tmp_path / "ledger.db"
    provider = SqliteConnectionProvider(str(db_file))

    with closing(provider.get_connection()) as conn:
        with write_transaction(conn):
            conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO items (id, name) VALUES (1, 'ok')")

        with pytest.raises(RuntimeError, match="boom"), write_transaction(conn):
            conn.execute("INSERT INTO items (id, name) VALUES (2, 'rollback')")
            raise RuntimeError("boom")

        with read_transaction(conn):
            rows = conn.execute("SELECT id, name FROM items ORDER BY id").fetchall()
            assert [(row["id"], row["name"]) for row in rows] == [(1, "ok")]


def test_read_transaction_sees_consistent_snapshot(tmp_path: Path) -> None:
    db_file = tmp_path / "ledger.db"
    provider = SqliteConnectionProvider(str(db_file), busy_timeout_ms=500)

    with closing(provider.get_connection()) as setup_conn, write_transaction(setup_conn):
        setup_conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, val INTEGER)")
        setup_conn.execute("INSERT INTO items (id, val) VALUES (1, 100)")

    with closing(provider.get_connection()) as reader, closing(provider.get_connection()) as writer:
        with read_transaction(reader):
            first_read = reader.execute("SELECT val FROM items WHERE id = 1").fetchone()["val"]
            assert first_read == 100

            with write_transaction(writer):
                writer.execute("UPDATE items SET val = 200 WHERE id = 1")

            # Reader keeps the snapshot from when its read transaction started
            second_read = reader.execute("SELECT val FROM items WHERE id = 1").fetchone()["val"]
            assert second_read == 100

        with read_transaction(reader):
            after_commit = reader.execute("SELECT val FROM items WHERE id = 1").fetchone()["val"]
            assert after_commit == 200


def test_write_transaction_raises_503_on_busy_timeout(tmp_path: Path) -> None:
    db_file = tmp_path / "ledger.db"
    provider = SqliteConnectionProvider(str(db_file), busy_timeout_ms=50)

    with (
        closing(provider.get_connection()) as conn1,
        closing(provider.get_connection()) as conn2,
        write_transaction(conn1),
        pytest.raises(AppError) as exc_info,
        write_transaction(conn2),
    ):
        pass

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "DATABASE_BUSY"
    assert exc_info.value.headers == {"Retry-After": "1"}
