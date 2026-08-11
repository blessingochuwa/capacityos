import uuid

from fastapi.testclient import TestClient


def _create_person(client: TestClient) -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex.morgan@example.com"},
    ).json()


def _create_project(client: TestClient) -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": "Website Redesign"}).json()


def test_create_allocation_returns_201(client: TestClient) -> None:
    person = _create_person(client)
    project = _create_project(client)

    response = client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"],
            "project_id": project["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": 20,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["allocation_hours"] == "20"
    assert body["allocation_unit"] == "total_hours"


def test_create_allocation_for_nonexistent_person_returns_404(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        "/api/v1/allocations",
        json={
            "person_id": str(uuid.uuid4()),
            "project_id": project["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": 20,
        },
    )
    assert response.status_code == 404


def test_create_allocation_for_nonexistent_project_returns_404(client: TestClient) -> None:
    person = _create_person(client)
    response = client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"],
            "project_id": str(uuid.uuid4()),
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": 20,
        },
    )
    assert response.status_code == 404


def test_create_allocation_with_negative_hours_returns_422(client: TestClient) -> None:
    person = _create_person(client)
    project = _create_project(client)
    response = client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"],
            "project_id": project["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": -5,
        },
    )
    assert response.status_code == 422


def test_list_allocations_filtered_by_person(client: TestClient) -> None:
    person = _create_person(client)
    other_person = client.post(
        "/api/v1/people",
        json={"first_name": "Sam", "last_name": "Ade", "email": "sam.ade@example.com"},
    ).json()
    project = _create_project(client)

    for p in (person, other_person):
        client.post(
            "/api/v1/allocations",
            json={
                "person_id": p["id"],
                "project_id": project["id"],
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                "allocation_hours": 10,
            },
        )

    response = client.get("/api/v1/allocations", params={"person_id": person["id"]})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["person_id"] == person["id"]


def test_update_allocation_hours(client: TestClient) -> None:
    person = _create_person(client)
    project = _create_project(client)
    created = client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"],
            "project_id": project["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": 20,
        },
    ).json()

    response = client.patch(f"/api/v1/allocations/{created['id']}", json={"allocation_hours": 30})
    assert response.status_code == 200
    assert response.json()["allocation_hours"] == "30"


def test_delete_allocation(client: TestClient) -> None:
    person = _create_person(client)
    project = _create_project(client)
    created = client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"],
            "project_id": project["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": 20,
        },
    ).json()

    assert client.delete(f"/api/v1/allocations/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/allocations/{created['id']}").status_code == 404
