import uuid

from fastapi.testclient import TestClient


def _create_person(client: TestClient) -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex.morgan@example.com"},
    ).json()


def _entries(*, count: int = 5, hours: int = 8) -> list[dict[str, object]]:
    return [{"weekday": weekday, "hours": hours} for weekday in range(count)]


def test_create_working_schedule_returns_201(client: TestClient) -> None:
    person = _create_person(client)
    response = client.post(
        "/api/v1/working-schedules", json={"person_id": person["id"], "entries": _entries()}
    )
    assert response.status_code == 201
    body = response.json()
    assert len(body["entries"]) == 5


def test_create_schedule_for_nonexistent_person_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/working-schedules",
        json={"person_id": str(uuid.uuid4()), "entries": _entries()},
    )
    assert response.status_code == 404


def test_create_schedule_with_duplicate_weekday_returns_422(client: TestClient) -> None:
    person = _create_person(client)
    response = client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person["id"],
            "entries": [{"weekday": 0, "hours": 8}, {"weekday": 0, "hours": 4}],
        },
    )
    assert response.status_code == 422


def test_create_schedule_with_empty_entries_returns_422(client: TestClient) -> None:
    person = _create_person(client)
    response = client.post(
        "/api/v1/working-schedules", json={"person_id": person["id"], "entries": []}
    )
    assert response.status_code == 422


def test_list_schedules_requires_person_id(client: TestClient) -> None:
    response = client.get("/api/v1/working-schedules")
    assert response.status_code == 422


def test_list_schedules_for_person(client: TestClient) -> None:
    person = _create_person(client)
    client.post(
        "/api/v1/working-schedules", json={"person_id": person["id"], "entries": _entries()}
    )

    response = client.get("/api/v1/working-schedules", params={"person_id": person["id"]})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_update_schedule_replaces_entries(client: TestClient) -> None:
    person = _create_person(client)
    created = client.post(
        "/api/v1/working-schedules", json={"person_id": person["id"], "entries": _entries()}
    ).json()

    response = client.patch(
        f"/api/v1/working-schedules/{created['id']}",
        json={"entries": [{"weekday": 0, "hours": 4}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["entries"]) == 1
    assert body["entries"][0]["hours"] == "4"


def test_create_overlapping_schedule_for_same_person_returns_422(client: TestClient) -> None:
    """Two unbounded (effective_start/end_date=None) schedules for the same
    person always overlap — the capacity engine needs at most one schedule
    matching any given date (docs/adr/0003-phase-2-capacity-engine.md)."""
    person = _create_person(client)
    client.post(
        "/api/v1/working-schedules", json={"person_id": person["id"], "entries": _entries()}
    )

    response = client.post(
        "/api/v1/working-schedules",
        json={"person_id": person["id"], "entries": _entries(hours=4)},
    )
    assert response.status_code == 422


def test_create_non_overlapping_schedule_for_same_person_returns_201(client: TestClient) -> None:
    person = _create_person(client)
    client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person["id"],
            "entries": _entries(),
            "effective_end_date": "2026-06-30",
        },
    )

    response = client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person["id"],
            "entries": _entries(hours=4),
            "effective_start_date": "2026-07-01",
        },
    )
    assert response.status_code == 201


def test_update_schedule_into_overlap_returns_422(client: TestClient) -> None:
    person = _create_person(client)
    client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person["id"],
            "entries": _entries(),
            "effective_end_date": "2026-06-30",
        },
    )
    second = client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person["id"],
            "entries": _entries(hours=4),
            "effective_start_date": "2026-07-01",
        },
    ).json()

    response = client.patch(
        f"/api/v1/working-schedules/{second['id']}", json={"effective_start_date": "2026-01-01"}
    )
    assert response.status_code == 422


def test_delete_schedule(client: TestClient) -> None:
    person = _create_person(client)
    created = client.post(
        "/api/v1/working-schedules", json={"person_id": person["id"], "entries": _entries()}
    ).json()

    assert client.delete(f"/api/v1/working-schedules/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/working-schedules/{created['id']}").status_code == 404
