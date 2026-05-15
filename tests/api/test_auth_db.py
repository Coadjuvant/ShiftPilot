from __future__ import annotations

import importlib


class FakeCursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple | None]] = []

    def execute(self, statement: str, params: tuple | None = None) -> None:
        self.statements.append((statement, params))

    def fetchone(self):
        return ("test",)


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


def test_reset_invite_returns_generated_token(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_BACKEND", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql://example")
    auth_db = importlib.import_module("backend.auth_db")
    auth_db = importlib.reload(auth_db)

    store = auth_db.PostgresAuth("postgresql://example")
    conn = FakeConnection()
    monkeypatch.setattr(store, "_conn", lambda: conn)

    token = store.reset_invite(123, created_by=1)

    assert token
    assert len(token) == 32
    assert conn.committed
    assert conn.closed
    update_params = conn.cursor_obj.statements[-1][1]
    assert update_params is not None
    assert update_params[0] == token
