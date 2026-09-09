"""Phase 47 — the org-wide Risk register (GET /api/v1/risks): every Risk
across every Project in the caller's active organization, with the same
multi-tenancy IDOR discipline every other org-wide route already proves
(tests/api/test_audit.py, tests/api/test_cross_organization_boundaries.py)."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from tests.factories import make_organization, make_person, make_project, make_risk


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_risk(
    client: TestClient, project_id: object, **overrides: object
) -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    payload: dict[str, object] = {"description": "Vendor delay"}
    payload.update(overrides)
    return client.post(f"/api/v1/projects/{project_id}/risks", json=payload).json()


# ---------------------------------------------------------------------------
# Cross-project aggregation
# ---------------------------------------------------------------------------


def test_list_organization_risks_spans_multiple_projects(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    risk_a = _create_risk(client, project_a["id"], description="Risk on A")
    risk_b = _create_risk(client, project_b["id"], description="Risk on B")

    body = client.get("/api/v1/risks").json()
    ids = {item["id"] for item in body["items"]}
    assert risk_a["id"] in ids
    assert risk_b["id"] in ids


def test_list_organization_risks_deterministic_ordering(client: TestClient) -> None:
    project = _create_project(client)
    first = _create_risk(client, project["id"], description="First")
    second = _create_risk(client, project["id"], description="Second")

    body_1 = client.get("/api/v1/risks").json()
    body_2 = client.get("/api/v1/risks").json()
    ids_1 = [item["id"] for item in body_1["items"]]
    ids_2 = [item["id"] for item in body_2["items"]]
    assert ids_1 == ids_2
    assert ids_1.index(first["id"]) < ids_1.index(second["id"])


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_list_organization_risks_filters_by_project(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    risk_a = _create_risk(client, project_a["id"], description="Risk on A")
    _create_risk(client, project_b["id"], description="Risk on B")

    body = client.get("/api/v1/risks", params={"project_id": project_a["id"]}).json()
    assert [item["id"] for item in body["items"]] == [risk_a["id"]]


def test_list_organization_risks_filters_by_status(client: TestClient) -> None:
    project = _create_project(client)
    open_risk = _create_risk(client, project["id"], description="Open", status="open")
    _create_risk(client, project["id"], description="Closed", status="closed")

    body = client.get("/api/v1/risks", params={"status": "open"}).json()
    ids = [item["id"] for item in body["items"]]
    assert open_risk["id"] in ids
    assert all(item["status"] == "open" for item in body["items"])


def test_list_organization_risks_filters_by_exposure(client: TestClient) -> None:
    project = _create_project(client)
    high = _create_risk(
        client, project["id"], description="High", probability="high", impact="high"
    )
    _create_risk(client, project["id"], description="Low", probability="low", impact="low")
    assert high["exposure"] == "high"

    body = client.get("/api/v1/risks", params={"exposure": "high"}).json()
    ids = [item["id"] for item in body["items"]]
    assert high["id"] in ids
    assert all(item["exposure"] == "high" for item in body["items"])


def test_list_organization_risks_combines_all_three_filters(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    match = _create_risk(
        client,
        project_a["id"],
        description="Matches every filter",
        status="open",
        probability="high",
        impact="high",
    )
    # Same project, wrong status.
    _create_risk(
        client,
        project_a["id"],
        description="Wrong status",
        status="closed",
        probability="high",
        impact="high",
    )
    # Wrong project entirely.
    _create_risk(
        client,
        project_b["id"],
        description="Wrong project",
        status="open",
        probability="high",
        impact="high",
    )

    body = client.get(
        "/api/v1/risks",
        params={"project_id": project_a["id"], "status": "open", "exposure": "high"},
    ).json()
    assert [item["id"] for item in body["items"]] == [match["id"]]


def test_list_organization_risks_no_match_returns_empty_not_an_error(
    client: TestClient,
) -> None:
    project = _create_project(client)
    _create_risk(client, project["id"])

    body = client.get("/api/v1/risks", params={"exposure": "high", "status": "closed"}).json()
    assert body["items"] == []
    assert body["total"] == 0


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_list_organization_risks_pagination(client: TestClient) -> None:
    project = _create_project(client)
    created = [
        _create_risk(client, project["id"], description=f"Risk {i}") for i in range(5)
    ]

    first_page = client.get("/api/v1/risks", params={"limit": 2, "offset": 0}).json()
    second_page = client.get("/api/v1/risks", params={"limit": 2, "offset": 2}).json()

    assert len(first_page["items"]) == 2
    assert first_page["total"] == 5
    assert second_page["total"] == 5
    first_ids = {item["id"] for item in first_page["items"]}
    second_ids = {item["id"] for item in second_page["items"]}
    assert first_ids.isdisjoint(second_ids)
    assert all(risk["id"] in {c["id"] for c in created} for risk in first_page["items"])


def test_list_organization_risks_total_reflects_exposure_filter_after_pagination(
    client: TestClient,
) -> None:
    """`total` must count the POST-exposure-filter set, not the raw
    project/status-filtered set — exposure is applied in Python, after the
    SQL query, so this is the one place an off-by-implementation-detail
    bug (returning the pre-filter count) would silently slip through."""
    project = _create_project(client)
    for _ in range(3):
        _create_risk(client, project["id"], probability="high", impact="high")
    for _ in range(2):
        _create_risk(client, project["id"], probability="low", impact="low")

    body = client.get("/api/v1/risks", params={"exposure": "high", "limit": 2}).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def test_list_organization_risks_without_authentication_returns_401(
    unauthenticated_client: TestClient,
) -> None:
    assert unauthenticated_client.get("/api/v1/risks").status_code == 401


def test_viewer_can_read_organization_risks(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    _create_risk(owner, project["id"])

    viewer = client_as(UserRole.VIEWER)
    response = viewer.get("/api/v1/risks")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


# ---------------------------------------------------------------------------
# Multi-tenancy — cross-organization access must never leak, and must
# never confirm another organization's data exists (404-shaped silence,
# not 403 — see docs/adr/0012-organizations-multi-tenancy.md).
# ---------------------------------------------------------------------------


def test_organization_risks_excludes_another_organizations_risks(
    client: TestClient, db_session: Session
) -> None:
    """`client` is bound to the test's default organization (Org A);
    Org B and its Project/Risk are built directly via factories, bypassing
    the API entirely, so this proves the SERVER-side boundary, not just
    that the test client never asked for the wrong org."""
    org_b = make_organization(db_session, slug="org-b")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    owner_b = make_person(db_session, organization=org_b, email="owner-b@example.com")
    make_risk(
        db_session,
        organization=org_b,
        project=project_b,
        owner=owner_b,
        description="Org B risk — must never appear in Org A's register",
    )

    project_a = _create_project(client, "Org A Project")
    risk_a = _create_risk(client, project_a["id"], description="Org A risk")

    body = client.get("/api/v1/risks").json()
    ids = [item["id"] for item in body["items"]]
    descriptions = [item["description"] for item in body["items"]]
    assert risk_a["id"] in ids
    assert "Org B risk — must never appear in Org A's register" not in descriptions


def test_organization_risks_project_filter_from_another_organization_returns_empty(
    client: TestClient, db_session: Session
) -> None:
    """A `project_id` filter naming a REAL project in another organization
    must behave exactly like a nonexistent id — an empty result, never an
    error, and never any of that project's risks. Filters must not become
    a second way to probe cross-organization data (CLAUDE.md §27)."""
    org_b = make_organization(db_session, slug="org-b-project-filter")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    owner_b = make_person(db_session, organization=org_b, email="owner-b2@example.com")
    make_risk(db_session, organization=org_b, project=project_b, owner=owner_b)

    response = client.get("/api/v1/risks", params={"project_id": str(project_b.id)})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_organization_risks_status_and_exposure_filters_cannot_bypass_org_scoping(
    client: TestClient, db_session: Session
) -> None:
    """Sweeping status/exposure filters (no project filter at all) must
    still never surface another organization's risk, regardless of how
    permissive the filter combination is."""
    org_b = make_organization(db_session, slug="org-b-sweep")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    owner_b = make_person(db_session, organization=org_b, email="owner-b3@example.com")
    make_risk(
        db_session,
        organization=org_b,
        project=project_b,
        owner=owner_b,
        description="Org B sweep risk",
        status="open",
        probability="high",
        impact="high",
    )

    body = client.get("/api/v1/risks", params={"status": "open", "exposure": "high"}).json()
    descriptions = [item["description"] for item in body["items"]]
    assert "Org B sweep risk" not in descriptions


def test_organization_risks_response_exposes_only_the_established_risk_fields(
    client: TestClient,
) -> None:
    """Guards against the response accidentally growing a field beyond
    RiskRead's existing, already-audited shape (CLAUDE.md §13/§27) — this
    endpoint reuses risk_to_read verbatim, so it should never diverge."""
    project = _create_project(client)
    _create_risk(client, project["id"])

    body = client.get("/api/v1/risks").json()
    expected_fields = {
        "id",
        "project_id",
        "description",
        "cause",
        "potential_effect",
        "probability",
        "impact",
        "exposure",
        "response",
        "owner_person_id",
        "status",
        "review_date",
        "external_id",
        "created_at",
        "updated_at",
    }
    assert set(body["items"][0].keys()) == expected_fields


def test_list_organization_risks_invalid_uuid_project_id_returns_422(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/risks", params={"project_id": "not-a-uuid"})
    assert response.status_code == 422


def test_list_organization_risks_invalid_status_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/risks", params={"status": "not-a-real-status"})
    assert response.status_code == 422


def test_list_organization_risks_invalid_exposure_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/risks", params={"exposure": "critical"})
    assert response.status_code == 422
