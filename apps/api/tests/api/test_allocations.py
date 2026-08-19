import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole
from tests.conftest import user_id_of


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


# ---------------------------------------------------------------------------
# Phase 11: Allocation is Project-scoped, resolved from the request body on
# create and from the existing row on update/delete (AllocationUpdate has no
# project_id field — an allocation can't be re-pointed to a different
# project). See docs/adr/0011-instance-level-resource-authorization.md.
# ---------------------------------------------------------------------------


def _grant_project_access(owner: TestClient, project_id: object, user_id: str) -> None:
    owner.activate()  # type: ignore[attr-defined]
    response = owner.post(
        f"/api/v1/projects/{project_id}/access-grants", json={"user_id": user_id}
    )
    assert response.status_code == 201, response.text


def test_manager_cannot_create_allocation_without_project_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    person = _create_person(owner)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"],
            "project_id": project["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": 20,
        },
    )
    assert response.status_code == 403


def test_manager_can_create_update_delete_allocation_once_granted(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    person = _create_person(owner)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    create_response = manager.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"],
            "project_id": project["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": 20,
        },
    )
    assert create_response.status_code == 201
    allocation_id = create_response.json()["id"]

    update_response = manager.patch(
        f"/api/v1/allocations/{allocation_id}", json={"allocation_hours": 30}
    )
    assert update_response.status_code == 200

    delete_response = manager.delete(f"/api/v1/allocations/{allocation_id}")
    assert delete_response.status_code == 204


def test_manager_granted_project_q_cannot_touch_allocation_under_project_p(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """Cross-project IDOR: an existing allocation under Project P must stay
    protected even for a Manager who has been granted access to a
    different, unrelated Project Q."""
    owner = client_as(UserRole.OWNER)
    person = _create_person(owner)
    project_p = _create_project(owner)
    project_q = owner.post("/api/v1/projects", json={"name": "Unrelated Project Q"}).json()
    allocation = owner.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"],
            "project_id": project_p["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "allocation_hours": 20,
        },
    ).json()

    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project_q["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    update_response = manager.patch(
        f"/api/v1/allocations/{allocation['id']}", json={"allocation_hours": 99}
    )
    assert update_response.status_code == 403

    delete_response = manager.delete(f"/api/v1/allocations/{allocation['id']}")
    assert delete_response.status_code == 403


def test_owner_can_create_allocation_without_any_grant(client: TestClient) -> None:
    """Regression guard: Owner (the `client` fixture's role) must never
    need a ProjectAccessGrant — this is the existing
    test_create_allocation_returns_201 behavior re-asserted explicitly
    under the Phase 11 scoping change."""
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
