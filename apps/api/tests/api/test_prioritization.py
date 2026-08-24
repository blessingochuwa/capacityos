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

from app.models.enums import PrioritizationFrameworkType, ProjectDependencyType, UserRole
from tests.conftest import user_id_of
from tests.factories import (
    make_organization,
    make_prioritization_criterion,
    make_prioritization_framework,
    make_project,
    make_project_dependency,
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


def _create_framework(
    client: TestClient, framework_type: str, name: str
) -> dict[str, object]:
    client.activate()  # type: ignore[attr-defined]
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={"name": name, "framework_type": framework_type, "criteria": []},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_ice_framework(client: TestClient, name: str = "Feature ICE") -> dict[str, object]:
    return _create_framework(client, "ice", name)


def _create_wsjf_framework(client: TestClient, name: str = "Feature WSJF") -> dict[str, object]:
    return _create_framework(client, "wsjf", name)


def _create_moscow_framework(client: TestClient, name: str = "Release MoSCoW") -> dict[str, object]:
    return _create_framework(client, "moscow", name)


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


# ---------------------------------------------------------------------------
# Phase 18 — ICE/WSJF/MoSCoW framework creation and seeding
# ---------------------------------------------------------------------------


def test_create_ice_framework_seeds_three_fixed_criteria(client: TestClient) -> None:
    framework = _create_ice_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    assert {c["key"] for c in criteria} == {"impact", "confidence", "ease"}
    assert all(c["is_editable"] is False for c in criteria)


def test_create_wsjf_framework_seeds_four_fixed_criteria(client: TestClient) -> None:
    framework = _create_wsjf_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    assert {c["key"] for c in criteria} == {
        "business_value",
        "time_criticality",
        "risk_reduction_opportunity_enablement",
        "job_size",
    }
    assert all(c["is_editable"] is False for c in criteria)


def test_create_moscow_framework_has_no_criteria_at_all(client: TestClient) -> None:
    framework = _create_moscow_framework(client)
    assert framework["criteria"] == []


def test_create_ice_framework_with_supplied_criteria_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={
            "name": "Bad ICE",
            "framework_type": "ice",
            "criteria": [{"name": "X", "weight": "1"}],
        },
    )
    assert response.status_code == 422


def test_create_moscow_framework_with_supplied_criteria_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/prioritization/frameworks",
        json={
            "name": "Bad MoSCoW",
            "framework_type": "moscow",
            "criteria": [{"name": "X", "weight": "1"}],
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Phase 18 — criterion editing (Weighted Scoring only)
# ---------------------------------------------------------------------------


def test_add_criterion_to_weighted_framework(client: TestClient) -> None:
    framework = _create_weighted_framework(client)
    response = client.post(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria",
        json={"name": "Risk", "weight": "1.5"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Risk"
    assert body["key"] == "risk"
    assert body["is_editable"] is True


def test_add_criterion_to_rice_framework_returns_403(client: TestClient) -> None:
    framework = _create_rice_framework(client)
    response = client.post(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria",
        json={"name": "Extra", "weight": "1"},
    )
    assert response.status_code == 403


def test_add_criterion_to_moscow_framework_returns_403(client: TestClient) -> None:
    framework = _create_moscow_framework(client)
    response = client.post(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria",
        json={"name": "Extra", "weight": "1"},
    )
    assert response.status_code == 403


def test_add_criterion_with_duplicate_key_returns_409(client: TestClient) -> None:
    framework = _create_weighted_framework(client)
    response = client.post(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria",
        json={"name": "Business Value", "weight": "1"},
    )
    assert response.status_code == 409


def test_update_editable_criterion_renames_and_reweights(client: TestClient) -> None:
    framework = _create_weighted_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    criterion_id = next(c["id"] for c in criteria if c["name"] == "Urgency")

    response = client.patch(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria/{criterion_id}",
        json={"name": "Time Pressure", "weight": "4"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Time Pressure"
    assert body["weight"] == "4.000"
    # Key stays stable across a rename.
    assert body["key"] == "urgency"


def test_update_fixed_criterion_returns_403(client: TestClient) -> None:
    framework = _create_rice_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    criterion_id = next(c["id"] for c in criteria if c["key"] == "reach")

    response = client.patch(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria/{criterion_id}",
        json={"name": "Renamed Reach"},
    )
    assert response.status_code == 403


def test_remove_editable_criterion(client: TestClient) -> None:
    framework = _create_weighted_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    criterion_id = next(c["id"] for c in criteria if c["name"] == "Urgency")

    response = client.delete(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria/{criterion_id}"
    )
    assert response.status_code == 204


def test_remove_last_remaining_criterion_returns_422(client: TestClient) -> None:
    framework = _create_weighted_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    for criterion in criteria[:-1]:
        client.delete(
            f"/api/v1/prioritization/frameworks/{framework['id']}/criteria/{criterion['id']}"
        )
    last = criteria[-1]
    response = client.delete(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria/{last['id']}"
    )
    assert response.status_code == 422


def test_remove_fixed_criterion_returns_403(client: TestClient) -> None:
    framework = _create_wsjf_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    criterion_id = next(c["id"] for c in criteria if c["key"] == "job_size")
    response = client.delete(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria/{criterion_id}"
    )
    assert response.status_code == 403


def test_manager_cannot_add_a_criterion(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    framework = _create_weighted_framework(owner)
    manager = client_as(UserRole.MANAGER)
    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria",
        json={"name": "Extra", "weight": "1"},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Phase 18 — MoSCoW category scoring
# ---------------------------------------------------------------------------


def test_create_moscow_score_with_category(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_moscow_framework(client)
    client.activate()  # type: ignore[attr-defined]

    response = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "category": "must"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["category"] == "must"
    assert body["score"] is None


def test_category_rejected_for_non_moscow_framework(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    client.activate()  # type: ignore[attr-defined]

    response = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "category": "must", "values": []},
    )
    assert response.status_code == 422


def test_update_moscow_score_category(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_moscow_framework(client)
    client.activate()  # type: ignore[attr-defined]
    created = client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "category": "could"},
    ).json()

    response = client.patch(
        f"/api/v1/projects/{project['id']}/priority-scores/{created['id']}",
        json={"category": "must"},
    )
    assert response.status_code == 200
    assert response.json()["category"] == "must"


# ---------------------------------------------------------------------------
# Phase 18 — project dependencies
# ---------------------------------------------------------------------------


def test_create_dependency_edge(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    client.activate()  # type: ignore[attr-defined]

    response = client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["from_project_id"] == project_a["id"]
    assert body["to_project_id"] == project_b["id"]
    assert body["dependency_type"] == "blocks"


def test_create_dependency_self_loop_returns_422(client: TestClient) -> None:
    project = _create_project(client)
    client.activate()  # type: ignore[attr-defined]
    response = client.post(
        f"/api/v1/projects/{project['id']}/dependencies",
        json={"to_project_id": project["id"], "dependency_type": "blocks"},
    )
    assert response.status_code == 422


def test_create_duplicate_dependency_edge_returns_409(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    client.activate()  # type: ignore[attr-defined]
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    response = client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    assert response.status_code == 409


def test_create_dependency_that_would_close_a_cycle_returns_422(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    project_c = _create_project(client, "Project C")
    client.activate()  # type: ignore[attr-defined]
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    client.post(
        f"/api/v1/projects/{project_b['id']}/dependencies",
        json={"to_project_id": project_c["id"], "dependency_type": "blocks"},
    )
    response = client.post(
        f"/api/v1/projects/{project_c['id']}/dependencies",
        json={"to_project_id": project_a["id"], "dependency_type": "blocks"},
    )
    assert response.status_code == 422


def test_related_edges_do_not_participate_in_cycle_detection(client: TestClient) -> None:
    """`related`/`enables` don't imply a strict ordering — see
    detects_cycle's docstring — so a `related` cycle is allowed even
    though the equivalent `blocks` cycle would be rejected."""
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    client.activate()  # type: ignore[attr-defined]
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "related"},
    )
    response = client.post(
        f"/api/v1/projects/{project_b['id']}/dependencies",
        json={"to_project_id": project_a["id"], "dependency_type": "related"},
    )
    assert response.status_code == 201


def test_list_dependencies_for_project_includes_both_directions(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    client.activate()  # type: ignore[attr-defined]
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )

    items_a = client.get(f"/api/v1/projects/{project_a['id']}/dependencies").json()
    items_b = client.get(f"/api/v1/projects/{project_b['id']}/dependencies").json()
    assert len(items_a) == 1
    assert len(items_b) == 1
    assert items_a[0]["id"] == items_b[0]["id"]


def test_delete_dependency_edge(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    client.activate()  # type: ignore[attr-defined]
    created = client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    ).json()

    response = client.delete(f"/api/v1/projects/{project_a['id']}/dependencies/{created['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/v1/projects/{project_a['id']}/dependencies").json() == []


def test_delete_dependency_from_the_non_owning_project_returns_404(client: TestClient) -> None:
    """Only the `from_project`'s URL can delete the edge — see
    ProjectDependencyCreate's docstring on "the URL names the owning
    project"."""
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    client.activate()  # type: ignore[attr-defined]
    created = client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    ).json()

    response = client.delete(f"/api/v1/projects/{project_b['id']}/dependencies/{created['id']}")
    assert response.status_code == 404


def test_dependency_graph_returns_nodes_and_edges(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    client.activate()  # type: ignore[attr-defined]
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )

    graph = client.get("/api/v1/prioritization/dependency-graph").json()
    node_ids = {n["project_id"] for n in graph["nodes"]}
    assert {project_a["id"], project_b["id"]} <= node_ids
    assert len(graph["edges"]) == 1


def test_manager_without_grant_cannot_create_a_dependency(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project_a = _create_project(owner, "Project A")
    project_b = _create_project(owner, "Project B")
    manager = client_as(UserRole.MANAGER)

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    assert response.status_code == 403


def test_manager_can_create_a_dependency_once_granted(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project_a = _create_project(owner, "Project A")
    project_b = _create_project(owner, "Project B")
    manager = client_as(UserRole.MANAGER)
    _grant_project_access(owner, project_a["id"], user_id_of(manager))

    manager.activate()  # type: ignore[attr-defined]
    response = manager.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# Phase 18 — audit
# ---------------------------------------------------------------------------


def test_adding_a_criterion_produces_an_audit_event(client: TestClient) -> None:
    framework = _create_weighted_framework(client)
    created = client.post(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria",
        json={"name": "Risk", "weight": "1"},
    ).json()

    events = client.get(
        "/api/v1/audit",
        params={
            "action": "prioritization_criterion.create",
            "resource_type": "prioritization_criterion",
        },
    ).json()["items"]
    assert any(e["resource_id"] == created["id"] for e in events)


def test_removing_a_criterion_produces_an_audit_event(client: TestClient) -> None:
    framework = _create_weighted_framework(client)
    criteria = framework["criteria"]
    assert isinstance(criteria, list)
    criterion_id = next(c["id"] for c in criteria if c["name"] == "Urgency")
    client.delete(
        f"/api/v1/prioritization/frameworks/{framework['id']}/criteria/{criterion_id}"
    )

    events = client.get(
        "/api/v1/audit",
        params={
            "action": "prioritization_criterion.delete",
            "resource_type": "prioritization_criterion",
        },
    ).json()["items"]
    assert any(e["resource_id"] == criterion_id for e in events)


def test_creating_a_dependency_produces_an_audit_event(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    client.activate()  # type: ignore[attr-defined]
    created = client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    ).json()

    events = client.get(
        "/api/v1/audit",
        params={
            "action": "project_dependency.create",
            "resource_type": "project_dependency",
        },
    ).json()["items"]
    assert any(e["resource_id"] == created["id"] for e in events)


def test_deleting_a_dependency_produces_an_audit_event(client: TestClient) -> None:
    project_a = _create_project(client, "Project A")
    project_b = _create_project(client, "Project B")
    client.activate()  # type: ignore[attr-defined]
    created = client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    ).json()
    client.delete(f"/api/v1/projects/{project_a['id']}/dependencies/{created['id']}")

    events = client.get(
        "/api/v1/audit",
        params={
            "action": "project_dependency.delete",
            "resource_type": "project_dependency",
        },
    ).json()["items"]
    assert any(e["resource_id"] == created["id"] for e in events)


# ---------------------------------------------------------------------------
# Phase 18 — multi-tenancy IDOR for dependencies
# ---------------------------------------------------------------------------


def test_dependency_across_organizations_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-dependency")
    project_b1 = make_project(db_session, organization=org_b, name="Org B Project 1")
    project_b2 = make_project(db_session, organization=org_b, name="Org B Project 2")
    dependency_b = make_project_dependency(
        db_session,
        organization=org_b,
        from_project=project_b1,
        to_project=project_b2,
        dependency_type=ProjectDependencyType.BLOCKS,
    )

    assert client.get(f"/api/v1/projects/{project_b1.id}/dependencies").status_code == 404
    assert (
        client.delete(
            f"/api/v1/projects/{project_b1.id}/dependencies/{dependency_b.id}"
        ).status_code
        == 404
    )


def test_cannot_create_dependency_to_a_project_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-cross-dependency")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")

    project_a = _create_project(client)
    response = client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": str(project_b.id), "dependency_type": "blocks"},
    )
    assert response.status_code == 404


def test_dependency_graph_never_includes_another_organizations_edges(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-graph")
    project_b1 = make_project(db_session, organization=org_b, name="Org B Project 1")
    project_b2 = make_project(db_session, organization=org_b, name="Org B Project 2")
    make_project_dependency(
        db_session, organization=org_b, from_project=project_b1, to_project=project_b2
    )

    graph = client.get("/api/v1/prioritization/dependency-graph").json()
    assert graph["nodes"] == []
    assert graph["edges"] == []
