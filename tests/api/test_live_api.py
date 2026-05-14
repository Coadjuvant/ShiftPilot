from __future__ import annotations

import os

import httpx
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("SHIFT_TEST_LIVE_API") != "1",
    reason="Set SHIFT_TEST_LIVE_API=1 with docker compose running to exercise live API endpoints.",
)


def test_live_health_and_login() -> None:
    base_url = os.getenv("SHIFT_TEST_BASE_URL", "http://localhost:8080/api")
    username = os.getenv("SHIFT_TEST_ADMIN_USER", "admin")
    password = os.getenv("SHIFT_TEST_ADMIN_PASS", "admin")

    with httpx.Client(base_url=base_url, timeout=5.0) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}

        login = client.post("/auth/login", json={"username": username, "password": password})
        assert login.status_code == 200
        assert login.json().get("token")
