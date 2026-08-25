"""Phase 21 — portfolio snapshots (docs/adr/0021-portfolio-snapshots.md):
snapshot creation freezes the live ranking, immutability (a later re-score
does not change an already-taken snapshot), RBAC (PRIORITIZATION_MANAGE
gates creation, Admin/Owner only — matching framework CRUD's precedent;
PRIORITIZATION_READ gates listing), audit, and the explicit
multi-tenancy/IDOR tests every new resource requires. Mirrors
tests/api/test_prioritization.py's and tests/api/test_scenario_priority.py's
conventions.
"""

from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from tests.factories import (
    make_organization,
    make_portfolio_snapshot,
    make_prioritization_framework,
)


def _create_project(client: TestClient, *, name: str = "Website Redesign") -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_rice_framework(client: TestClient, name: str = "Feature RICE") -> dict[str, object]:
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={"name": name, "framework_type": "rice", "criteria": []},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_moscow_framework(client: TestClient, name: str = "Release MoSCoW") -> dict[str, object]:
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={"name": name, "framework_type": "moscow", "criteria": []},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _score_project(
    client: TestClient, project_id: object, framework_id: object, *, reach: str = "1000"
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/projects/{project_id}/priority-scores",
        json={
            "framework_id": framework_id,
            "values": [
                {"criterion_key": "reach", "value": reach},
                {"criterion_key": "impact", "value": "2"},
                {"criterion_key": "confidence", "value": "0.8"},
                {"criterion_key": "effort", "value": "4"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _take_snapshot(client: TestClient, framework_id: object) -> Any:
    """Return type is deliberately Any, not dict[str, object] — every call
    site nested-indexes the result (e.g. snapshot["entries"][0]["score"]),
    matching how every other test file in this suite reads a nested JSON
    body straight off response.json() rather than through a narrowly-typed
    helper."""
    response = client.post("/api/v1/prioritization/snapshots", json={"framework_id": framework_id})
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Creation freezes the live ranking
# ---------------------------------------------------------------------------


def test_snapshot_freezes_current_ranking(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    _score_project(client, project["id"], framework["id"])

    snapshot = _take_snapshot(client, framework["id"])
    assert snapshot["framework_id"] == framework["id"]
    assert snapshot["framework_name"] == framework["name"]
    assert snapshot["framework_type"] == "rice"
    assert len(snapshot["entries"]) == 1
    entry = snapshot["entries"][0]
    assert entry["project_id"] == project["id"]
    assert entry["project_name"] == project["name"]
    assert entry["rank"] == 1
    assert entry["score"] is not None


def test_snapshot_with_no_scored_projects_has_empty_entries(client: TestClient) -> None:
    framework = _create_rice_framework(client)
    snapshot = _take_snapshot(client, framework["id"])
    assert snapshot["entries"] == []


def test_snapshot_lists_incomplete_score_unranked(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1000"}],
        },
    )

    snapshot = _take_snapshot(client, framework["id"])
    entry = snapshot["entries"][0]
    assert entry["rank"] is None
    assert entry["score"] is None
    assert "impact" in entry["missing_criteria"]


def test_moscow_snapshot_captures_category_never_a_score(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_moscow_framework(client)
    client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "category": "must"},
    )

    snapshot = _take_snapshot(client, framework["id"])
    entry = snapshot["entries"][0]
    assert entry["category"] == "must"
    assert entry["score"] is None
    assert entry["rank"] is None


def test_snapshot_of_unknown_framework_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/prioritization/snapshots",
        json={"framework_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Immutability — a later re-score or rename never changes an already-taken
# snapshot
# ---------------------------------------------------------------------------


def test_rescoring_a_project_does_not_change_an_earlier_snapshot(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    score = _score_project(client, project["id"], framework["id"], reach="1000")

    first_snapshot = _take_snapshot(client, framework["id"])
    first_score = first_snapshot["entries"][0]["score"]

    client.patch(
        f"/api/v1/projects/{project['id']}/priority-scores/{score['id']}",
        json={"values": [{"criterion_key": "reach", "value": "9000"}]},
    )

    # Re-reading the SAME (already-taken) snapshot must still show the
    # frozen, original score.
    snapshots = client.get(
        "/api/v1/prioritization/snapshots", params={"framework_id": framework["id"]}
    ).json()["items"]
    refetched = next(s for s in snapshots if s["id"] == first_snapshot["id"])
    assert refetched["entries"][0]["score"] == first_score

    # A NEW snapshot taken after the re-score reflects the updated value.
    second_snapshot = _take_snapshot(client, framework["id"])
    assert second_snapshot["entries"][0]["score"] != first_score


def test_renaming_a_framework_does_not_change_an_earlier_snapshots_frozen_name(
    client: TestClient,
) -> None:
    framework = _create_rice_framework(client, name="Original Name")
    snapshot = _take_snapshot(client, framework["id"])

    client.patch(f"/api/v1/prioritization/frameworks/{framework['id']}", json={"name": "Renamed"})

    snapshots = client.get(
        "/api/v1/prioritization/snapshots", params={"framework_id": framework["id"]}
    ).json()["items"]
    refetched = next(s for s in snapshots if s["id"] == snapshot["id"])
    assert refetched["framework_name"] == "Original Name"


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def test_list_snapshots_orders_most_recent_first(client: TestClient) -> None:
    framework = _create_rice_framework(client)
    first = _take_snapshot(client, framework["id"])
    second = _take_snapshot(client, framework["id"])

    items = client.get("/api/v1/prioritization/snapshots").json()["items"]
    ids = [item["id"] for item in items]
    assert ids.index(second["id"]) < ids.index(first["id"])


def test_list_snapshots_filters_by_framework(client: TestClient) -> None:
    framework_a = _create_rice_framework(client, name="Framework A")
    framework_b = _create_moscow_framework(client, name="Framework B")
    snapshot_a = _take_snapshot(client, framework_a["id"])
    _take_snapshot(client, framework_b["id"])

    items = client.get(
        "/api/v1/prioritization/snapshots", params={"framework_id": framework_a["id"]}
    ).json()["items"]
    assert [item["id"] for item in items] == [snapshot_a["id"]]


# ---------------------------------------------------------------------------
# RBAC — PRIORITIZATION_MANAGE (Admin/Owner only) gates creation, matching
# framework CRUD's precedent; PRIORITIZATION_READ (every role) gates
# listing.
# ---------------------------------------------------------------------------


def test_manager_cannot_take_a_snapshot(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    framework = _create_rice_framework(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        "/api/v1/prioritization/snapshots", json={"framework_id": framework["id"]}
    )
    assert response.status_code == 403


def test_admin_can_take_a_snapshot(client_as: Callable[[UserRole], TestClient]) -> None:
    admin = client_as(UserRole.ADMIN)
    framework = _create_rice_framework(admin)

    response = admin.post(
        "/api/v1/prioritization/snapshots", json={"framework_id": framework["id"]}
    )
    assert response.status_code == 201, response.text


def test_viewer_can_list_snapshots_but_not_create_one(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    framework = _create_rice_framework(owner)
    _take_snapshot(owner, framework["id"])

    viewer = client_as(UserRole.VIEWER)
    viewer.activate()  # type: ignore[attr-defined]
    assert viewer.get("/api/v1/prioritization/snapshots").status_code == 200
    response = viewer.post(
        "/api/v1/prioritization/snapshots", json={"framework_id": framework["id"]}
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_taking_a_snapshot_is_audited(client: TestClient) -> None:
    framework = _create_rice_framework(client)
    snapshot = _take_snapshot(client, framework["id"])

    events = client.get(
        "/api/v1/audit",
        params={"action": "portfolio_snapshot.create", "resource_type": "portfolio_snapshot"},
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == snapshot["id"]]
    assert len(matching) == 1
    assert matching[0]["event_metadata"] == {
        "framework_id": framework["id"],
        "entry_count": len(snapshot["entries"]),
    }


# ---------------------------------------------------------------------------
# Multi-tenancy — cross-organization access must 404, never 403; another
# organization's snapshots must never appear in this organization's list.
# ---------------------------------------------------------------------------


def test_cannot_take_a_snapshot_of_a_framework_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-portfolio-snapshot")
    framework_b = make_prioritization_framework(db_session, organization=org_b, name="Org B RICE")

    response = client.post(
        "/api/v1/prioritization/snapshots", json={"framework_id": str(framework_b.id)}
    )
    assert response.status_code == 404


def test_list_snapshots_never_includes_another_organizations_snapshots(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-portfolio-snapshot-list")
    framework_b = make_prioritization_framework(db_session, organization=org_b, name="Org B RICE")
    make_portfolio_snapshot(db_session, organization=org_b, framework=framework_b)

    items = client.get("/api/v1/prioritization/snapshots").json()["items"]
    assert items == []
