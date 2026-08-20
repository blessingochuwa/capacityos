"""Phase 13 risk management — CRUD, permissions, audit, and the explicit
multi-tenancy IDOR test every new Phase 13 resource requires (a client
bound to one organization must never reach another organization's Risk or
Project, even by guessing/reusing a valid id)."""

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from tests.factories import make_organization, make_person, make_project, make_risk


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_person(client: TestClient, email: str = "alex.morgan@example.com") -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": email},
    ).json()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_create_risk_with_defaults(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/risks",
        json={"description": "Key vendor may miss the delivery deadline"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["description"] == "Key vendor may miss the delivery deadline"
    assert body["probability"] == "medium"
    assert body["impact"] == "medium"
    assert body["exposure"] == "medium"
    assert body["status"] == "open"
    assert body["owner_person_id"] is None


def test_create_risk_computes_high_exposure(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/risks",
        json={"description": "Vendor delay", "probability": "high", "impact": "high"},
    )
    assert response.json()["exposure"] == "high"


def test_create_risk_with_owner(client: TestClient) -> None:
    project = _create_project(client)
    person = _create_person(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/risks",
        json={"description": "Vendor delay", "owner_person_id": person["id"]},
    )
    assert response.status_code == 201
    assert response.json()["owner_person_id"] == person["id"]


def test_create_risk_for_nonexistent_project_returns_404(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/projects/{uuid.uuid4()}/risks", json={"description": "Vendor delay"}
    )
    assert response.status_code == 404


def test_create_risk_with_nonexistent_owner_returns_404(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/risks",
        json={"description": "Vendor delay", "owner_person_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_create_risk_with_empty_description_returns_422(client: TestClient) -> None:
    project = _create_project(client)
    response = client.post(f"/api/v1/projects/{project['id']}/risks", json={"description": ""})
    assert response.status_code == 422


def test_list_risks_for_project(client: TestClient) -> None:
    project = _create_project(client)
    client.post(f"/api/v1/projects/{project['id']}/risks", json={"description": "Risk one"})
    client.post(f"/api/v1/projects/{project['id']}/risks", json={"description": "Risk two"})
    response = client.get(f"/api/v1/projects/{project['id']}/risks")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_risks_for_nonexistent_project_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/v1/projects/{uuid.uuid4()}/risks").status_code == 404


def test_update_risk(client: TestClient) -> None:
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/risks", json={"description": "Vendor delay"}
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}/risks/{created['id']}",
        json={"status": "mitigating", "response": "Weekly vendor check-ins"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "mitigating"
    assert body["response"] == "Weekly vendor check-ins"


def test_update_risk_can_clear_owner(client: TestClient) -> None:
    project = _create_project(client)
    person = _create_person(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/risks",
        json={"description": "Vendor delay", "owner_person_id": person["id"]},
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}/risks/{created['id']}",
        json={"owner_person_id": None},
    )
    assert response.status_code == 200
    assert response.json()["owner_person_id"] is None


def test_update_risk_scoped_to_wrong_project_returns_404(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    created = client.post(
        f"/api/v1/projects/{project_a['id']}/risks", json={"description": "Vendor delay"}
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project_b['id']}/risks/{created['id']}", json={"status": "closed"}
    )
    assert response.status_code == 404


def test_delete_risk(client: TestClient) -> None:
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/risks", json={"description": "Vendor delay"}
    ).json()

    assert (
        client.delete(f"/api/v1/projects/{project['id']}/risks/{created['id']}").status_code
        == 204
    )
    assert client.get(f"/api/v1/projects/{project['id']}/risks").json() == []


def test_deleting_project_deletes_its_risks(client: TestClient) -> None:
    project = _create_project(client)
    client.post(f"/api/v1/projects/{project['id']}/risks", json={"description": "Vendor delay"})
    assert client.delete(f"/api/v1/projects/{project['id']}").status_code == 204


# ---------------------------------------------------------------------------
# Authentication / authorization
# ---------------------------------------------------------------------------


def test_list_risks_without_authentication_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    response = unauthenticated_client.get(f"/api/v1/projects/{uuid.uuid4()}/risks")
    assert response.status_code == 401


def test_viewer_can_read_risks_but_not_create_one(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    viewer = client_as(UserRole.VIEWER)

    assert viewer.get(f"/api/v1/projects/{project['id']}/risks").status_code == 200
    response = viewer.post(
        f"/api/v1/projects/{project['id']}/risks", json={"description": "Vendor delay"}
    )
    assert response.status_code == 403


def test_member_cannot_delete_a_risk(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    created = owner.post(
        f"/api/v1/projects/{project['id']}/risks", json={"description": "Vendor delay"}
    ).json()

    member = client_as(UserRole.MEMBER)
    response = member.delete(f"/api/v1/projects/{project['id']}/risks/{created['id']}")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_creating_a_risk_produces_an_audit_event(client: TestClient) -> None:
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/risks", json={"description": "Vendor delay"}
    ).json()

    events = client.get(
        "/api/v1/audit", params={"action": "risk.create", "resource_type": "risk"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1
    assert matching[0]["outcome"] == "success"


def test_updating_a_risk_audit_event_never_carries_free_text_values(client: TestClient) -> None:
    """Only changed field NAMES are logged, never the free-text content
    itself — matches PROJECT_UPDATE's existing convention (see
    app/api/v1/projects.py) and the audit rules against unnecessary
    payload content."""
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/risks", json={"description": "Vendor delay"}
    ).json()
    client.patch(
        f"/api/v1/projects/{project['id']}/risks/{created['id']}",
        json={"description": "Confidential vendor negotiation details"},
    )

    events = client.get(
        "/api/v1/audit", params={"action": "risk.update", "resource_type": "risk"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1
    assert matching[0]["event_metadata"] == {"fields": ["description"]}
    assert "Confidential vendor negotiation details" not in str(matching[0])


def test_deleting_a_risk_produces_an_audit_event(client: TestClient) -> None:
    project = _create_project(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/risks", json={"description": "Vendor delay"}
    ).json()
    client.delete(f"/api/v1/projects/{project['id']}/risks/{created['id']}")

    events = client.get(
        "/api/v1/audit", params={"action": "risk.delete", "resource_type": "risk"}
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1


# ---------------------------------------------------------------------------
# Multi-tenancy — cross-organization access must 404, never 403
# ---------------------------------------------------------------------------


def test_risk_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    """User authorized in Organization A attempts to access an equivalent
    resource in Organization B — must not succeed, and must 404 rather
    than 403 (a cross-organization resource must look exactly like a
    nonexistent one — see docs/adr/0012-organizations-multi-tenancy.md).
    `client` is bound to the test's default organization (Org A);
    Org B and its Project/Risk are built directly via factories, bypassing
    the API entirely, so this proves the SERVER-side boundary, not just
    that the test client never asked for the wrong org."""
    org_b = make_organization(db_session, slug="org-b")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    owner_b = make_person(db_session, organization=org_b, email="owner-b@example.com")
    risk_b = make_risk(
        db_session, organization=org_b, project=project_b, owner=owner_b, description="Org B risk"
    )

    # Listing Org B's project's risks from Org A's client 404s on the project itself.
    assert client.get(f"/api/v1/projects/{project_b.id}/risks").status_code == 404

    # Reading/writing the risk directly (guessing the id) also 404s — the
    # project-scope check in RiskService._get_owned is not the only guard;
    # the risk's own organization_id is checked independently too.
    assert (
        client.patch(
            f"/api/v1/projects/{project_b.id}/risks/{risk_b.id}", json={"status": "closed"}
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/projects/{project_b.id}/risks/{risk_b.id}").status_code == 404
    )


def test_cannot_create_risk_owned_by_a_person_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    """A same-organization project paired with a cross-organization
    owner_person_id must fail exactly like a nonexistent person would —
    never silently link across the tenant boundary."""
    project = _create_project(client)
    org_b = make_organization(db_session, slug="org-b-owner")
    person_b = make_person(db_session, organization=org_b, email="person-b@example.com")

    response = client.post(
        f"/api/v1/projects/{project['id']}/risks",
        json={"description": "Vendor delay", "owner_person_id": str(person_b.id)},
    )
    assert response.status_code == 404
