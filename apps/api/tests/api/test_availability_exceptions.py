import uuid

from fastapi.testclient import TestClient


def _create_person(client: TestClient) -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex.morgan@example.com"},
    ).json()


def test_create_fully_unavailable_exception(client: TestClient) -> None:
    person = _create_person(client)
    response = client.post(
        "/api/v1/availability-exceptions",
        json={
            "person_id": person["id"],
            "start_date": "2026-09-15",
            "end_date": "2026-09-19",
            "availability_type": "annual_leave",
        },
    )
    assert response.status_code == 201
    assert response.json()["hours"] is None


def test_create_partially_available_exception(client: TestClient) -> None:
    person = _create_person(client)
    response = client.post(
        "/api/v1/availability-exceptions",
        json={
            "person_id": person["id"],
            "start_date": "2026-09-15",
            "end_date": "2026-09-19",
            "availability_type": "reduced_availability",
            "hours": 4,
        },
    )
    assert response.status_code == 201
    assert response.json()["hours"] == "4"


def test_create_with_invalid_availability_type_returns_422(client: TestClient) -> None:
    person = _create_person(client)
    response = client.post(
        "/api/v1/availability-exceptions",
        json={
            "person_id": person["id"],
            "start_date": "2026-09-15",
            "end_date": "2026-09-19",
            "availability_type": "not_a_real_reason",
        },
    )
    assert response.status_code == 422


def test_create_for_nonexistent_person_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/availability-exceptions",
        json={
            "person_id": str(uuid.uuid4()),
            "start_date": "2026-09-15",
            "end_date": "2026-09-19",
            "availability_type": "annual_leave",
        },
    )
    assert response.status_code == 404


def test_list_filtered_by_person(client: TestClient) -> None:
    person = _create_person(client)
    client.post(
        "/api/v1/availability-exceptions",
        json={
            "person_id": person["id"],
            "start_date": "2026-09-15",
            "end_date": "2026-09-19",
            "availability_type": "annual_leave",
        },
    )

    response = client.get("/api/v1/availability-exceptions", params={"person_id": person["id"]})
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_and_delete(client: TestClient) -> None:
    person = _create_person(client)
    created = client.post(
        "/api/v1/availability-exceptions",
        json={
            "person_id": person["id"],
            "start_date": "2026-09-15",
            "end_date": "2026-09-19",
            "availability_type": "annual_leave",
        },
    ).json()

    response = client.patch(
        f"/api/v1/availability-exceptions/{created['id']}", json={"hours": 4}
    )
    assert response.status_code == 200
    assert response.json()["hours"] == "4"

    assert client.delete(f"/api/v1/availability-exceptions/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/availability-exceptions/{created['id']}").status_code == 404
