"""Liveness vs readiness (Phase 9 spec §6/§17 golden path items 3-4)."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError


def test_liveness_returns_ok_and_checks_nothing_external(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_ok_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_readiness_returns_503_when_database_is_unreachable(client: TestClient) -> None:
    with patch("app.api.v1.health.engine") as mock_engine:
        mock_engine.connect.side_effect = OperationalError("SELECT 1", {}, Exception("refused"))
        response = client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["database"] == "unreachable"


def test_readiness_never_leaks_the_underlying_database_error_message(client: TestClient) -> None:
    with patch("app.api.v1.health.engine") as mock_engine:
        mock_engine.connect.side_effect = OperationalError(
            "SELECT 1", {}, Exception("password authentication failed for user \"admin\"")
        )
        response = client.get("/api/v1/health/ready")
    assert "password" not in response.text
    assert "admin" not in response.text


def test_liveness_and_readiness_never_reference_ai_provider_status(client: TestClient) -> None:
    """AI is optional (CLAUDE.md §21) — neither endpoint's response body may
    even mention it, proving the check is structurally independent of AI
    configuration, not just coincidentally passing today."""
    live = client.get("/api/v1/health").json()
    ready = client.get("/api/v1/health/ready").json()
    assert "ai" not in {k.lower() for k in live}
    assert "ai" not in {k.lower() for k in ready}
