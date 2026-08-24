"""Phase 17 prioritization engine — framework CRUD, RICE seeding, score
CRUD, portfolio ranking, RBAC (PRIORITIZATION_MANAGE is Admin/Owner only,
unlike Skill's Manager-writable precedent), Phase 11 instance-level
project-grant enforcement for scoring, audit, and the explicit
multi-tenancy IDOR test every new resource requires. Mirrors
tests/api/test_risks.py's and tests/api/test_stakeholders.py's
conventions."""

from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import PrioritizationFrameworkType, UserRole
from tests.conftest import user_id_of
from tests.factories import (
    make_organization,
    make_prioritization_criterion,
    make_prioritization_framework,
    make_project,
    make_project_priority_score,
)


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_rice_framework(client: TestClient, name: str = "Feature RICE") -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={"name": name, "framework_type": "rice", "criteria": []},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_weighted_framework(
    client: TestClient, name: str = "Platform Weighted"
) -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={
            "name": name,
            "framework_type": "weighted",
            "criteria": [
                {"name": "Business Value", "weight": "3"},
                {"name": "Urgency", "weight": "2"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _grant_project_access(owner: TestClient, project_id: object, user_id: str) -> None:
    owner.activate()  # type: ignore[attr-defined]
    response = owner.post(
        f"/api/v1/projects/{project_id}/access-grants", json={"user_id": user_id}
    )
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------------------
# Framework CRUD
# ---------------------------------------------------------------------------


def test_create_rice_framework_seeds_four_fixed_criteria(client: TestClient) -> None:
    framework = _create_rice_framework(client)
    assert framework["framework_type"] == "rice"
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    assert {c["key"] for c in criteria} == {"reach", "impact", "confidence", "effort"}
    assert all(c["is_editable"] is False for c in criteria)
    assert all(c["weight"] is None for c in criteria)


def test_create_rice_framework_with_supplied_criteria_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={
            "name": "Bad RICE",
            "framework_type": "rice",
            "criteria": [{"name": "Custom", "weight": "1"}],
        },
    )
    assert response.status_code == 422


def test_create_weighted_framework_with_custom_criteria(client: TestClient) -> None:
    framework = _create_weighted_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    assert {c["name"] for c in criteria} == {"Business Value", "Urgency"}
    assert all(c["is_editable"] is True for c in criteria)
    weights = {c["name"]: c["weight"] for c in criteria}
    assert weights["Business Value"] == "3.000"
    assert weights["Urgency"] == "2.000"


def test_create_weighted_framework_with_no_criteria_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={"name": "Empty Weighted", "framework_type": "weighted", "criteria": []},
    )
    assert response.status_code == 422


def test_create_framework_with_duplicate_name_returns_409(client: TestClient) -> None:
    _create_rice_framework(client, name="Feature RICE")
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={"name": "Feature RICE", "framework_type": "rice", "criteria": []},
    )
    assert response.status_code == 409


def test_get_framework(client: TestClient) -> None:
    created = _create_rice_framework(client)
    response = client.get(f"/api/v1/prioritization/frameworks/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == created["name"]


def test_get_nonexistent_framework_returns_404(client: TestClient) -> None:
    response = client.get(
        "/api/v1/prioritization/frameworks/00000000-0000-0000-0000-000000000000"
    )
    assert response.status_code == 404


def test_list_frameworks_filters_by_is_active(client: TestClient) -> None:
    active = _create_rice_framework(client, name="Active One")
    inactive = _create_rice_framework(client, name="Will Deactivate")
    client.delete(f"/api/v1/prioritization/frameworks/{inactive['id']}")

    only_active = client.get(
        "/api/v1/prioritization/frameworks", params={"is_active": "true"}
    ).json()["items"]
    ids = {item["id"] for item in only_active}
    assert active["id"] in ids
    assert inactive["id"] not in ids


def test_rename_framework(client: TestClient) -> None:
    created = _create_rice_framework(client, name="Old Name")
    response = client.patch(
        f"/api/v1/prioritization/frameworks/{created['id']}", json={"name": "New Name"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"


def test_deactivate_framework_is_a_soft_delete(client: TestClient) -> None:
    created = _create_rice_framework(client)
    response = client.delete(f"/api/v1/prioritization/frameworks/{created['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    # Still readable directly by id.
    assert client.get(f"/api/v1/prioritization/frameworks/{created['id']}").status_code == 200


# ---------------------------------------------------------------------------
# Framework RBAC — PRIORITIZATION_MANAGE is Admin/Owner only, not Manager
# (deliberately stricter than Skill's Manager-writable catalog precedent)
# ---------------------------------------------------------------------------


def test_viewer_can_read_frameworks_but_not_create_one(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    _create_rice_framework(owner)
    viewer = client_as(UserRole.VIEWER)

    viewer.activate()  # type: ignore[attr-defined]
    assert viewer.get("/api/v1/prioritization/frameworks").status_code == 200
    response = viewer.post(
        "/api/v1/prioritization/frameworks",
        json={"name": "Viewer's framework", "framework_type": "rice", "criteria": []},
    )
    assert response.status_code == 403


def test_manager_cannot_create_a_framework(client_as: Callable[[UserRole], TestClient]) -> None:
    """Framework management is deliberately Admin/Owner only — a Manager
    holds every other *_WRITE permission but not PRIORITIZATION_MANAGE,
    since a framework change reshuffles the whole portfolio at once."""
    manager = client_as(UserRole.MANAGER)
    response = manager.post(
        "/api/v1/prioritization/frameworks",
        json={"name": "Manager's framework", "framework_type": "rice", "criteria": []},
    )
    assert response.status_code == 403


def test_manager_cannot_update_or_deactivate_a_framework(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    created = _create_rice_framework(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    assert (
        manager.patch(
            f"/api/v1/prioritization/frameworks/{created['id']}", json={"name": "Renamed"}
        ).status_code
        == 403
    )
    assert (
        manager.delete(f"/api/v1/prioritization/frameworks/{created['id']}").status_code == 403
    )


def test_admin_can_create_and_manage_a_framework(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    admin = client_as(UserRole.ADMIN)
    created = _create_rice_framework(admin)
    admin.activate()  # type: ignore[attr-defined]
    response = admin.patch(
        f"/api/v1/prioritization/frameworks/{created['id']}", json={"name": "Renamed by Admin"}
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Score CRUD and computation
# ---------------------------------------------------------------------------


def test_create_score_with_all_rice_inputs_computes_score(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.activate()  # type: ignore[attr-defined]

    response = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [
                {"criterion_key": "reach", "value": "1000"},
                {"criterion_key": "impact", "value": "2"},
                {"criterion_key": "confidence", "value": "0.8"},
                {"criterion_key": "effort", "value": "4"},
            ],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert Decimal(body["score"]) == Decimal(1000) * 2 * Decimal("0.8") / 4
    assert body["missing_criteria"] == []


def test_create_score_with_partial_inputs_has_null_score_and_lists_missing(
    client: TestClient,
) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.activate()  # type: ignore[attr-defined]

    response = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1000"}],
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["score"] is None
    assert set(body["missing_criteria"]) == {"impact", "confidence", "effort"}


def test_create_score_with_unknown_criterion_key_returns_422(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.activate()  # type: ignore[attr-defined]

    response = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [{"criterion_key": "not_a_real_criterion", "value": "1"}],
        },
    )
    assert response.status_code == 422


def test_creating_a_second_score_for_the_same_project_and_framework_returns_409(
    client: TestClient,
) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.activate()  # type: ignore[attr-defined]
    client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    )
    assert response.status_code == 409


def test_updating_a_score_fills_in_a_missing_criterion_incrementally(
    client: TestClient,
) -> None:
    """Values are an upsert per criterion_key, not a full replace — see
    ProjectPriorityScoreUpdate's docstring."""
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.activate()  # type: ignore[attr-defined]
    created = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [
                {"criterion_key": "reach", "value": "1000"},
                {"criterion_key": "impact", "value": "2"},
                {"criterion_key": "confidence", "value": "1"},
            ],
        },
    ).json()
    assert created["score"] is None

    response = client.patch(
        f"/api/v1/projects/{project['id']}/priority-scores/{created['id']}",
        json={"values": [{"criterion_key": "effort", "value": "2"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["missing_criteria"] == []
    assert Decimal(body["score"]) == Decimal(1000) * 2 * 1 / 2
    # And the previously-set "reach" value is still there, untouched.
    assert body["breakdown"]["reach"] == "1000.000"


def test_delete_score(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.activate()  # type: ignore[attr-defined]
    created = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    ).json()

    assert (
        client.delete(
            f"/api/v1/projects/{project['id']}/priority-scores/{created['id']}"
        ).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/projects/{project['id']}/priority-scores/{created['id']}").status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Phase 11 instance-level ProjectAccessGrant enforcement for scoring
# ---------------------------------------------------------------------------


def test_manager_without_grant_cannot_create_a_score(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    framework = _create_rice_framework(owner)
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    )
    assert response.status_code == 403


def test_manager_can_create_a_score_once_granted(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    framework = _create_rice_framework(owner)
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    )
    assert response.status_code == 201


def test_manager_granted_project_a_still_denied_scoring_project_b(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project_a = _create_project(owner, "Project A")
    project_b = _create_project(owner, "Project B")
    framework = _create_rice_framework(owner)
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project_a["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/projects/{project_b['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    )
    assert response.status_code == 403


def test_viewer_can_read_scores_but_not_create_one(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    framework = _create_rice_framework(owner)
    viewer = client_as(UserRole.VIEWER)

    viewer.activate()  # type: ignore[attr-defined]
    assert (
        viewer.get(f"/api/v1/projects/{project['id']}/priority-scores").status_code == 200
    )
    response = viewer.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    )
    assert response.status_code == 403


def test_owner_and_admin_bypass_instance_scoping_for_scores(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    framework = _create_rice_framework(owner)
    admin = client_as(UserRole.ADMIN)

    admin.activate()  # type: ignore[attr-defined]
    response = admin.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Portfolio ranking
# ---------------------------------------------------------------------------


def test_rank_portfolio_orders_by_score_descending(client: TestClient) -> None:
    framework = _create_rice_framework(client)
    project_low = _create_project(client, "Low Priority")
    project_high = _create_project(client, "High Priority")
    client.activate()  # type: ignore[attr-defined]

    def _score(project_id: str, reach: str) -> None:
        client.post(
            f"/api/v1/projects/{project_id}/priority-scores",
            json={
                "framework_id": framework["id"],
                "values": [
                    {"criterion_key": "reach", "value": reach},
                    {"criterion_key": "impact", "value": "1"},
                    {"criterion_key": "confidence", "value": "1"},
                    {"criterion_key": "effort", "value": "1"},
                ],
            },
        )

    _score(str(project_low["id"]), "10")
    _score(str(project_high["id"]), "1000")

    response = client.get(
        "/api/v1/prioritization/portfolio", params={"framework_id": framework["id"]}
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["project_name"] for item in items] == ["High Priority", "Low Priority"]
    assert items[0]["rank"] == 1
    assert items[1]["rank"] == 2


def test_rank_portfolio_lists_incomplete_scores_last_and_unranked(client: TestClient) -> None:
    framework = _create_rice_framework(client)
    complete = _create_project(client, "Complete")
    incomplete = _create_project(client, "Incomplete")
    client.activate()  # type: ignore[attr-defined]

    client.post(
        f"/api/v1/projects/{complete['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [
                {"criterion_key": "reach", "value": "1"},
                {"criterion_key": "impact", "value": "1"},
                {"criterion_key": "confidence", "value": "1"},
                {"criterion_key": "effort", "value": "1"},
            ],
        },
    )
    client.post(
        f"/api/v1/projects/{incomplete['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )

    items = client.get(
        "/api/v1/prioritization/portfolio", params={"framework_id": framework["id"]}
    ).json()["items"]
    assert [item["project_name"] for item in items] == ["Complete", "Incomplete"]
    assert items[0]["rank"] == 1
    assert items[1]["rank"] is None


def test_rank_portfolio_excludes_projects_never_scored_under_this_framework(
    client: TestClient,
) -> None:
    framework = _create_rice_framework(client)
    _create_project(client, "Never Scored")
    items = client.get(
        "/api/v1/prioritization/portfolio", params={"framework_id": framework["id"]}
    ).json()["items"]
    assert items == []


def test_weighted_framework_portfolio_ranking(client: TestClient) -> None:
    framework = _create_weighted_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    business_value_key = next(c["key"] for c in criteria if c["name"] == "Business Value")
    urgency_key = next(c["key"] for c in criteria if c["name"] == "Urgency")

    project = _create_project(client)
    client.activate()  # type: ignore[attr-defined]
    response = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [
                {"criterion_key": business_value_key, "value": "8"},
                {"criterion_key": urgency_key, "value": "5"},
            ],
        },
    )
    assert response.status_code == 201
    assert Decimal(response.json()["score"]) == Decimal(8) * 3 + Decimal(5) * 2


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_creating_a_framework_produces_an_audit_event_with_criteria_names_and_weights(
    client: TestClient,
) -> None:
    _create_weighted_framework(client, name="Audited Framework")
    events = client.get(
        "/api/v1/audit",
        params={
            "action": "prioritization_framework.create",
            "resource_type": "prioritization_framework",
        },
    ).json()["items"]
    matching = [e for e in events if e["event_metadata"]["framework_type"] == "weighted"]
    assert len(matching) == 1
    criteria_metadata = matching[0]["event_metadata"]["criteria"]
    assert {"name": "Business Value", "weight": "3.000"} in criteria_metadata
    assert {"name": "Urgency", "weight": "2.000"} in criteria_metadata


def test_deactivating_a_framework_produces_an_audit_event(client: TestClient) -> None:
    created = _create_rice_framework(client)
    client.delete(f"/api/v1/prioritization/frameworks/{created['id']}")

    events = client.get(
        "/api/v1/audit",
        params={
            "action": "prioritization_framework.deactivate",
            "resource_type": "prioritization_framework",
        },
    ).json()["items"]
    assert any(e["resource_id"] == created["id"] for e in events)


def test_creating_a_score_produces_an_audit_event(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.activate()  # type: ignore[attr-defined]
    created = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    ).json()

    events = client.get(
        "/api/v1/audit",
        params={
            "action": "project_priority_score.create",
            "resource_type": "project_priority_score",
        },
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1
    assert matching[0]["event_metadata"] == {"framework_id": framework["id"]}


def test_updating_a_score_audit_event_never_carries_criterion_values_or_notes(
    client: TestClient,
) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.activate()  # type: ignore[attr-defined]
    created = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "values": []},
    ).json()
    client.patch(
        f"/api/v1/projects/{project['id']}/priority-scores/{created['id']}",
        json={
            "values": [{"criterion_key": "reach", "value": "1000"}],
            "notes": "Confidential negotiation details",
        },
    )

    events = client.get(
        "/api/v1/audit",
        params={
            "action": "project_priority_score.update",
            "resource_type": "project_priority_score",
        },
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1
    assert matching[0]["event_metadata"] == {"fields": ["notes", "values"]}
    assert "Confidential negotiation details" not in str(matching[0])
    assert "1000" not in str(matching[0])


# ---------------------------------------------------------------------------
# Multi-tenancy — cross-organization access must 404, never 403
# ---------------------------------------------------------------------------


def test_framework_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-prioritization")
    framework_b = make_prioritization_framework(db_session, organization=org_b, name="Org B RICE")
    make_prioritization_criterion(
        db_session, organization=org_b, framework=framework_b, key="reach", name="Reach"
    )

    assert client.get(f"/api/v1/prioritization/frameworks/{framework_b.id}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/prioritization/frameworks/{framework_b.id}", json={"name": "Renamed"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/prioritization/frameworks/{framework_b.id}").status_code == 404
    listed = client.get("/api/v1/prioritization/frameworks").json()["items"]
    assert framework_b.id not in {item["id"] for item in listed}


def test_score_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-priority-score")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    framework_b = make_prioritization_framework(db_session, organization=org_b, name="Org B RICE")
    score_b = make_project_priority_score(
        db_session, organization=org_b, project=project_b, framework=framework_b
    )

    assert (
        client.get(f"/api/v1/projects/{project_b.id}/priority-scores").status_code == 404
    )
    assert (
        client.get(
            f"/api/v1/projects/{project_b.id}/priority-scores/{score_b.id}"
        ).status_code
        == 404
    )


def test_cannot_create_score_against_a_framework_from_another_organization(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-cross-framework")
    framework_b = make_prioritization_framework(db_session, organization=org_b, name="Org B RICE")

    project = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": str(framework_b.id), "values": []},
    )
    assert response.status_code == 404


def test_portfolio_ranking_never_includes_another_organizations_projects(
    client: TestClient, db_session: Session
) -> None:
    """Same framework NAME in two different organizations is fine (the
    uniqueness constraint is per-organization) — this proves ranking one
    organization's framework never leaks the other's scored projects."""
    org_b = make_organization(db_session, slug="org-b-portfolio")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    framework_b = make_prioritization_framework(
        db_session,
        organization=org_b,
        name="Shared Name",
        framework_type=PrioritizationFrameworkType.RICE,
    )
    make_project_priority_score(
        db_session, organization=org_b, project=project_b, framework=framework_b
    )

    framework_a = _create_rice_framework(client, name="Shared Name")
    items = client.get(
        "/api/v1/prioritization/portfolio", params={"framework_id": framework_a["id"]}
    ).json()["items"]
    assert items == []
    # And Org B's own framework_id is simply invisible to Org A's client.
    assert (
        client.get(
            "/api/v1/prioritization/portfolio", params={"framework_id": str(framework_b.id)}
        ).status_code
        == 404
    )
