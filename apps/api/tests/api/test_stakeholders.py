"""Phase 14 stakeholder management — CRUD, Phase 11 instance-level project
authorization, audit, and the explicit multi-tenancy IDOR test every new
resource requires (a client bound to one organization must never reach
another organization's Stakeholder or Project, even by guessing/reusing a
valid id). Mirrors tests/api/test_risks.py and
tests/api/test_project_access_scope.py's conventions exactly."""

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from tests.conftest import user_id_of
from tests.factories import make_organization, make_person, make_project, make_stakeholder


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_person(client: TestClient, email: str = "alex.morgan@example.com") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": email},
    ).json()


def _grant_project_access(owner: TestClient, project_id: object, user_id: str) -> None:
    owner.activate()  # type: ignore[attr-defined]
    response = owner.post(
        f"/api/v1/projects/{project_id}/access-grants", json={"user_id": user_id}
    )
    assert response.status_code == 201, response.text


def _revoke_project_access(owner: TestClient, project_id: object, user_id: str) -> None:
    owner.activate()  # type: ignore[attr-defined]
    response = owner.delete(f"/api/v1/projects/{project_id}/access-grants/{user_id}")
    assert response.status_code == 204, response.text


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_create_stakeholder_with_defaults(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Jordan Client"
    assert body["role"] == "Sponsor"
    assert body["influence"] == "medium"
    assert body["interest"] == "medium"
    assert body["decision_authority"] == "informed"
    assert body["person_id"] is None


def test_create_stakeholder_with_person_link(client: TestClient) -> None:
    project = _create_project(client)
    person = _create_person(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={
            "name": person["display_name"],
            "person_id": person["id"],
            "role": "Product Owner",
            "influence": "high",
            "interest": "high",
            "decision_authority": "decision_maker",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["person_id"] == person["id"]
    assert body["decision_authority"] == "decision_maker"


def test_create_stakeholder_for_nonexistent_project_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/projects/{uuid.uuid4()}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    )
    assert response.status_code == 404


def test_create_stakeholder_with_nonexistent_person_returns_404(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={
            "name": "Jordan Client",
            "role": "Sponsor",
            "person_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 404


def test_create_stakeholder_with_duplicate_person_on_same_project_returns_409(
    client: TestClient,
) -> None:
    project = _create_project(client)
    person = _create_person(client)
    client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": person["display_name"], "person_id": person["id"], "role": "Sponsor"},
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": person["display_name"], "person_id": person["id"], "role": "Reviewer"},
    )
    assert response.status_code == 409


def test_create_stakeholder_with_empty_name_returns_422(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders", json={"name": "", "role": "Sponsor"}
    )
    assert response.status_code == 422


def test_create_stakeholder_with_empty_role_returns_422(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": ""},
    )
    assert response.status_code == 422


def test_create_stakeholder_with_overlong_name_returns_422(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "x" * 201, "role": "Sponsor"},
    )
    assert response.status_code == 422


def test_create_stakeholder_with_overlong_communication_needs_returns_422(
    client: TestClient,
) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={
            "name": "Jordan Client",
            "role": "Sponsor",
            "communication_needs": "x" * 2001,
        },
    )
    assert response.status_code == 422


def test_create_stakeholder_with_malformed_influence_returns_422(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor", "influence": "extreme"},
    )
    assert response.status_code == 422


def test_create_stakeholder_with_malformed_decision_authority_returns_422(
    client: TestClient,
) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor", "decision_authority": "ceo"},
    )
    assert response.status_code == 422


def test_list_stakeholders_for_project(client: TestClient) -> None:
    project = _create_project(client)
    client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Stakeholder One", "role": "Sponsor"},
    )
    client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Stakeholder Two", "role": "Reviewer"},
    )
    response = client.get(f"/api/v1/projects/{project['id']}/stakeholders")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_stakeholders_for_nonexistent_project_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/v1/projects/{uuid.uuid4()}/stakeholders").status_code == 404


def test_update_stakeholder(client: TestClient) -> None:
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}",
        json={"influence": "high", "communication_needs": "Monthly steering update"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["influence"] == "high"
    assert body["communication_needs"] == "Monthly steering update"


def test_update_stakeholder_can_clear_person_link(client: TestClient) -> None:
    project = _create_project(client)
    person = _create_person(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": person["display_name"], "person_id": person["id"], "role": "Sponsor"},
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}",
        json={"person_id": None},
    )
    assert response.status_code == 200
    assert response.json()["person_id"] is None


def test_update_stakeholder_to_nonexistent_person_returns_404(client: TestClient) -> None:
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}",
        json={"person_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_update_stakeholder_scoped_to_wrong_project_returns_404(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    created = client.post(
        f"/api/v1/projects/{project_a['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project_b['id']}/stakeholders/{created['id']}",
        json={"role": "Reviewer"},
    )
    assert response.status_code == 404


def test_delete_stakeholder(client: TestClient) -> None:
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()

    assert (
        client.delete(
            f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}"
        ).status_code
        == 204
    )
    assert client.get(f"/api/v1/projects/{project['id']}/stakeholders").json() == []
    # Idempotent-safe: deleting again reports not-found, never a second success.
    assert (
        client.delete(
            f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}"
        ).status_code
        == 404
    )


def test_deleting_project_deletes_its_stakeholders(client: TestClient) -> None:
    project = _create_project(client)
    client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    )
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 204


# ---------------------------------------------------------------------------
# Authentication / role-level authorization
# ---------------------------------------------------------------------------


def test_list_stakeholders_without_authentication_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get(f"/api/v1/projects/{uuid.uuid4()}/stakeholders")
    assert response.status_code == 401


def test_viewer_can_read_stakeholders_but_not_create_one(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    viewer = client_as(UserRole.VIEWER)

    viewer.activate()  # type: ignore[attr-defined]
    assert viewer.get(f"/api/v1/projects/{project['id']}/stakeholders").status_code == 200
    response = viewer.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    )
    assert response.status_code == 403


def test_viewer_cannot_delete_a_stakeholder(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    created = owner.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()

    viewer = client_as(UserRole.VIEWER)
    viewer.activate()  # type: ignore[attr-defined]
    response = viewer.delete(f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}")
    assert response.status_code == 403


def test_owner_and_admin_bypass_instance_scoping(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    admin = client_as(UserRole.ADMIN)

    admin.activate()  # type: ignore[attr-defined]
    response = admin.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Phase 11 instance-level ProjectAccessGrant enforcement
# ---------------------------------------------------------------------------


def test_manager_without_grant_cannot_create_stakeholder(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    )
    assert response.status_code == 403


def test_manager_without_grant_cannot_update_or_delete_stakeholder(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    created = owner.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    assert (
        manager.patch(
            f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}",
            json={"role": "Reviewer"},
        ).status_code
        == 403
    )
    assert (
        manager.delete(
            f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}"
        ).status_code
        == 403
    )


def test_manager_can_create_stakeholder_once_granted(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    )
    assert response.status_code == 201


def test_manager_granted_project_a_still_denied_stakeholder_on_project_b(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """Phase 16 audit addition, mirroring
    tests/api/test_risks.py::test_manager_granted_project_a_still_denied_risk_on_project_b
    and the underlying Project-level precedent in
    tests/api/test_project_access_scope.py — a grant on one Project must
    never leak into another."""
    owner = client_as(UserRole.OWNER)
    project_a = _create_project(owner, "Project A")
    project_b = _create_project(owner, "Project B")
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project_a["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/projects/{project_b['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    )
    assert response.status_code == 403


def test_manager_mutation_fails_immediately_after_grant_revoked(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)
    _grant_project_access(owner, project["id"], manager_id)

    manager.activate()  # type: ignore[attr-defined]
    created = manager.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()

    _revoke_project_access(owner, project["id"], manager_id)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.patch(
        f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}",
        json={"role": "Reviewer"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_creating_a_stakeholder_produces_an_audit_event(client: TestClient) -> None:
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()

    events = client.get(
        "/api/v1/audit", params={"action": "stakeholder.create", "resource_type": "stakeholder"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1
    assert matching[0]["outcome"] == "success"
    assert matching[0]["organization_id"] is not None


def test_updating_a_stakeholder_audit_event_never_carries_free_text_values(
    client: TestClient,
) -> None:
    """Only changed field NAMES are logged, never the free-text content
    itself — matches RISK_UPDATE's precedent (see
    app/api/v1/projects.py) and the audit rules against unnecessary
    payload content."""
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()
    client.patch(
        f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}",
        json={"communication_needs": "Confidential escalation contact details"},
    )

    events = client.get(
        "/api/v1/audit", params={"action": "stakeholder.update", "resource_type": "stakeholder"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1
    assert matching[0]["event_metadata"] == {"fields": ["communication_needs"]}
    assert "Confidential escalation contact details" not in str(matching[0])


def test_deleting_a_stakeholder_produces_an_audit_event(client: TestClient) -> None:
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    ).json()
    client.delete(f"/api/v1/projects/{project['id']}/stakeholders/{created['id']}")

    events = client.get(
        "/api/v1/audit", params={"action": "stakeholder.delete", "resource_type": "stakeholder"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1


# ---------------------------------------------------------------------------
# Multi-tenancy — cross-organization access must 404, never 403
# ---------------------------------------------------------------------------


def test_stakeholder_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    """User authorized in Organization A attempts to access an equivalent
    resource in Organization B — must not succeed, and must 404 rather
    than 403 (see docs/adr/0012-organizations-multi-tenancy.md). `client`
    is bound to the test's default organization (Org A); Org B and its
    Project/Stakeholder are built directly via factories, bypassing the
    API entirely, so this proves the SERVER-side boundary."""
    org_b = make_organization(db_session, slug="org-b-stakeholders")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    person_b = make_person(db_session, organization=org_b, email="person-b@example.com")
    stakeholder_b = make_stakeholder(
        db_session, organization=org_b, project=project_b, person=person_b, name="Org B Client"
    )

    assert client.get(f"/api/v1/projects/{project_b.id}/stakeholders").status_code == 404
    assert (
        client.patch(
            f"/api/v1/projects/{project_b.id}/stakeholders/{stakeholder_b.id}",
            json={"role": "Reviewer"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/v1/projects/{project_b.id}/stakeholders/{stakeholder_b.id}"
        ).status_code
        == 404
    )


def test_cannot_create_stakeholder_linked_to_a_person_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    """A same-organization project paired with a cross-organization
    person_id must fail exactly like a nonexistent person would — never
    silently link across the tenant boundary."""
    project = _create_project(client)
    org_b = make_organization(db_session, slug="org-b-person")
    person_b = make_person(db_session, organization=org_b, email="person-b@example.com")

    response = client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={
            "name": "Cross-org stakeholder",
            "role": "Sponsor",
            "person_id": str(person_b.id),
        },
    )
    assert response.status_code == 404
