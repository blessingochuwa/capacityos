"""RequestContextMiddleware (correlation id) and MaxBodySizeMiddleware
(request size cap) — Phase 9 spec §5/§8."""

from fastapi.testclient import TestClient


def test_response_carries_a_generated_request_id_when_client_sends_none(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/health")
    request_id = response.headers.get("X-Request-ID")
    assert request_id
    assert len(request_id) > 0


def test_response_echoes_back_a_client_supplied_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"X-Request-ID": "test-fixed-id-42"})
    assert response.headers.get("X-Request-ID") == "test-fixed-id-42"


def test_two_requests_get_two_different_generated_request_ids(client: TestClient) -> None:
    first = client.get("/api/v1/health").headers.get("X-Request-ID")
    second = client.get("/api/v1/health").headers.get("X-Request-ID")
    assert first != second


def test_oversized_request_body_is_rejected_with_413(client: TestClient) -> None:
    huge_description = "x" * (6 * 1024 * 1024)  # exceeds the default 5 MiB ceiling
    response = client.post(
        "/api/v1/projects",
        json={"name": "Big Project", "description": huge_description},
    )
    assert response.status_code == 413


def test_a_normal_sized_request_is_not_rejected_by_the_body_size_limit(
    client: TestClient,
) -> None:
    response = client.post("/api/v1/projects", json={"name": "Normal Size Project"})
    assert response.status_code != 413
