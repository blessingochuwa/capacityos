import uuid

from fastapi.testclient import TestClient


def test_create_project_defaults_to_planned(client: TestClient) -> None:
    response = client.post("/api/v1/projects", json={"name": "Website Redesign"})
    assert response.status_code == 201
    assert response.json()["status"] == "planned"


def test_create_project_with_bad_date_range_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/projects",
        json={"name": "Website Redesign", "start_date": "2026-10-01", "end_date": "2026-09-01"},
    )
    assert response.status_code == 422


def test_get_nonexistent_project_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/v1/projects/{uuid.uuid4()}").status_code == 404


def test_update_project_status(client: TestClient) -> None:
    created = client.post("/api/v1/projects", json={"name": "Website Redesign"}).json()
    response = client.patch(f"/api/v1/projects/{created['id']}", json={"status": "active"})
    assert response.status_code == 200
    assert response.json()["status"] == "active"


def test_update_project_into_invalid_date_range_returns_422(client: TestClient) -> None:
    created = client.post(
        "/api/v1/projects",
        json={"name": "Website Redesign", "start_date": "2026-09-01", "end_date": "2026-10-31"},
    ).json()

    response = client.patch(f"/api/v1/projects/{created['id']}", json={"end_date": "2026-08-01"})
    assert response.status_code == 422


def test_delete_project(client: TestClient) -> None:
    created = client.post("/api/v1/projects", json={"name": "Website Redesign"}).json()
    assert client.delete(f"/api/v1/projects/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/projects/{created['id']}").status_code == 404
