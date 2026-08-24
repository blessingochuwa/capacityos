"""Phase 20 — scenario-vs-baseline prioritization comparison
(docs/adr/0020-scenario-priority-comparison.md): override CRUD, the
deterministic comparison itself (every supported framework type, ranking
changes, incomplete criteria, no-op overrides reporting no change), RBAC
(SCENARIO_READ/WRITE/DELETE — role-only, no ProjectAccessGrant), audit,
and the explicit multi-tenancy/IDOR tests every new resource requires.
Mirrors tests/api/test_prioritization.py's and tests/api/test_ai.py's
conventions.
"""

from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from tests.factories import (
    make_organization,
    make_prioritization_framework,
    make_project,
    make_scenario,
)


def _create_project(client: TestClient, *, name: str = "Website Redesign") -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_scenario(client: TestClient, *, name: str = "Test scenario") -> dict[str, object]:
    return client.post(
        "/api/v1/scenarios",
        json={"name": name, "baseline_start_date": "2026-09-01", "baseline_end_date": "2026-09-05"},
    ).json()


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


# ---------------------------------------------------------------------------
# Override CRUD
# ---------------------------------------------------------------------------


def test_set_override_creates_with_criterion_values(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)

    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "5000"}],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project_id"] == project["id"]
    assert body["framework_id"] == framework["id"]
    assert body["values"] == {"reach": "5000"}
    assert body["category"] is None


def test_set_override_with_category_for_moscow(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_moscow_framework(client)

    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={"project_id": project["id"], "framework_id": framework["id"], "category": "must"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["category"] == "must"


def test_set_override_upserts_on_second_call(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)

    first = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1000"}],
        },
    ).json()
    second = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "9000"}],
        },
    ).json()

    assert second["id"] == first["id"]
    assert second["values"] == {"reach": "9000"}
    overrides = client.get(f"/api/v1/scenarios/{scenario['id']}/priority-overrides").json()
    assert len(overrides) == 1


def test_set_override_rejects_unknown_criterion_key(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)

    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "not_a_real_criterion", "value": "1"}],
        },
    )
    assert response.status_code == 422


def test_set_override_rejects_values_for_moscow_framework(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_moscow_framework(client)

    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )
    assert response.status_code == 422


def test_set_override_rejects_category_for_non_moscow_framework(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)

    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={"project_id": project["id"], "framework_id": framework["id"], "category": "must"},
    )
    assert response.status_code == 422


def test_set_override_rejects_completely_empty_override(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)

    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={"project_id": project["id"], "framework_id": framework["id"]},
    )
    assert response.status_code == 422


def test_set_override_404_for_unknown_scenario(client: TestClient) -> None:
    project = _create_project(client)
    framework = _create_rice_framework(client)
    response = client.post(
        "/api/v1/scenarios/00000000-0000-0000-0000-000000000000/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )
    assert response.status_code == 404


def test_delete_override(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    created = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    ).json()

    response = client.delete(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides/{created['id']}"
    )
    assert response.status_code == 204
    assert client.get(f"/api/v1/scenarios/{scenario['id']}/priority-overrides").json() == []


# ---------------------------------------------------------------------------
# Deterministic comparison
# ---------------------------------------------------------------------------


def test_comparison_with_no_overrides_and_no_baseline_scores_reports_no_change(
    client: TestClient,
) -> None:
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    response = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["has_changes"] is False


def test_comparison_with_no_override_equals_baseline_and_reports_no_change(
    client: TestClient,
) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    _score_project(client, project["id"], framework["id"])

    body = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    ).json()
    assert body["has_changes"] is False
    item = body["items"][0]
    assert item["has_override"] is False
    assert item["changed"] is False
    assert item["baseline_score"] == item["scenario_score"]
    assert item["baseline_rank"] == item["scenario_rank"] == 1


def test_comparison_override_changes_score_and_reports_change(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    _score_project(client, project["id"], framework["id"], reach="1000")
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "5000"}],
        },
    )

    body = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    ).json()
    assert body["has_changes"] is True
    item = body["items"][0]
    assert item["has_override"] is True
    assert item["changed"] is True
    assert Decimal(item["baseline_score"]) == Decimal(1000) * 2 * Decimal("0.8") / 4
    assert Decimal(item["scenario_score"]) == Decimal(5000) * 2 * Decimal("0.8") / 4
    # The baseline's own persisted score is never touched by comparing.
    persisted = client.get(f"/api/v1/projects/{project['id']}/priority-scores").json()
    assert Decimal(persisted[0]["score"]) == Decimal(1000) * 2 * Decimal("0.8") / 4


def test_comparison_no_op_override_reports_no_change(client: TestClient) -> None:
    """An override whose value happens to match the baseline exactly must
    never be reported as a change — `changed` is computed from the two
    computed results, not from "an override row exists"."""
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    _score_project(client, project["id"], framework["id"], reach="1000")
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1000"}],
        },
    )

    body = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    ).json()
    assert body["has_changes"] is False
    assert body["items"][0]["changed"] is False


def test_comparison_override_for_project_with_no_baseline_score(client: TestClient) -> None:
    """A scenario can explore a hypothetical score for a project that has
    never been scored at all — baseline is empty/incomplete, scenario is
    whatever the override supplies."""
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [
                {"criterion_key": "reach", "value": "1000"},
                {"criterion_key": "impact", "value": "2"},
                {"criterion_key": "confidence", "value": "0.8"},
                {"criterion_key": "effort", "value": "4"},
            ],
        },
    )

    body = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    ).json()
    item = body["items"][0]
    assert item["baseline_score"] is None
    assert set(item["baseline_missing_criteria"]) == {"reach", "impact", "confidence", "effort"}
    assert item["baseline_rank"] is None
    assert Decimal(item["scenario_score"]) == Decimal(1000) * 2 * Decimal("0.8") / 4
    assert item["scenario_rank"] == 1
    assert item["changed"] is True


def test_comparison_partial_override_keeps_other_baseline_values(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    _score_project(client, project["id"], framework["id"], reach="1000")
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "effort", "value": "2"}],
        },
    )

    body = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    ).json()
    item = body["items"][0]
    assert item["scenario_breakdown"]["reach"] == "1000.000"
    assert item["scenario_breakdown"]["effort"] == "2"
    assert Decimal(item["scenario_score"]) == Decimal(1000) * 2 * Decimal("0.8") / 2


def test_comparison_reflects_ranking_swap(client: TestClient) -> None:
    project_low = _create_project(client, name="Low Priority")
    project_high = _create_project(client, name="High Priority")
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    _score_project(client, project_low["id"], framework["id"], reach="10")
    _score_project(client, project_high["id"], framework["id"], reach="1000")

    # Baseline: High Priority ranks first. Override drops its reach so Low
    # Priority overtakes it in the scenario ranking.
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project_high["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )

    body = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    ).json()
    items_by_name = {item["project_name"]: item for item in body["items"]}
    assert items_by_name["High Priority"]["baseline_rank"] == 1
    assert items_by_name["Low Priority"]["baseline_rank"] == 2
    assert items_by_name["High Priority"]["scenario_rank"] == 2
    assert items_by_name["Low Priority"]["scenario_rank"] == 1
    assert items_by_name["High Priority"]["changed"] is True
    # Low Priority's own inputs never changed, but its rank did — still a
    # change worth reporting.
    assert items_by_name["Low Priority"]["changed"] is True
    assert body["has_changes"] is True


def test_comparison_moscow_category_override(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_moscow_framework(client)
    client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={"framework_id": framework["id"], "category": "could"},
    )
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={"project_id": project["id"], "framework_id": framework["id"], "category": "must"},
    )

    body = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    ).json()
    item = body["items"][0]
    assert item["baseline_category"] == "could"
    assert item["scenario_category"] == "must"
    assert item["baseline_score"] is None
    assert item["scenario_score"] is None
    assert item["changed"] is True


def test_comparison_ice_framework_override(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = client.post(
        "/api/v1/prioritization/frameworks",
        json={"name": "Feature ICE", "framework_type": "ice", "criteria": []},
    ).json()
    client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [
                {"criterion_key": "impact", "value": "6"},
                {"criterion_key": "confidence", "value": "6"},
                {"criterion_key": "ease", "value": "6"},
            ],
        },
    )
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "ease", "value": "9"}],
        },
    )

    body = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    ).json()
    item = body["items"][0]
    assert Decimal(item["baseline_score"]) == Decimal(18) / Decimal(3)
    assert Decimal(item["scenario_score"]) == Decimal(21) / Decimal(3)
    assert item["changed"] is True


def test_comparison_weighted_framework_override(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = client.post(
        "/api/v1/prioritization/frameworks",
        json={
            "name": "Platform Weighted",
            "framework_type": "weighted",
            "criteria": [
                {"name": "Business Value", "weight": "3"},
                {"name": "Urgency", "weight": "2"},
            ],
        },
    ).json()
    criteria = framework["criteria"]
    business_value_key = next(c["key"] for c in criteria if c["name"] == "Business Value")
    urgency_key = next(c["key"] for c in criteria if c["name"] == "Urgency")
    client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [
                {"criterion_key": business_value_key, "value": "8"},
                {"criterion_key": urgency_key, "value": "5"},
            ],
        },
    )
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": urgency_key, "value": "10"}],
        },
    )

    body = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": framework["id"]},
    ).json()
    item = body["items"][0]
    assert Decimal(item["baseline_score"]) == Decimal(8) * 3 + Decimal(5) * 2
    assert Decimal(item["scenario_score"]) == Decimal(8) * 3 + Decimal(10) * 2
    assert item["changed"] is True


def test_comparison_404_for_unknown_framework(client: TestClient) -> None:
    scenario = _create_scenario(client)
    response = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# RBAC — role-only (SCENARIO_READ/WRITE/DELETE), no ProjectAccessGrant
# ---------------------------------------------------------------------------


def test_viewer_can_read_overrides_and_comparison_but_not_create(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    scenario = _create_scenario(owner)
    framework = _create_rice_framework(owner)
    viewer = client_as(UserRole.VIEWER)

    assert (
        viewer.get(f"/api/v1/scenarios/{scenario['id']}/priority-overrides").status_code == 200
    )
    assert (
        viewer.get(
            f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
            params={"framework_id": framework["id"]},
        ).status_code
        == 200
    )
    response = viewer.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )
    assert response.status_code == 403


def test_manager_can_create_and_delete_override_without_any_project_grant(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    """Proves the deliberate authorization shape: Scenario permissions are
    role-only (Phase 16), so a Manager needs no ProjectAccessGrant on the
    referenced project — unlike creating a REAL ProjectPriorityScore,
    which does require one."""
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    scenario = _create_scenario(owner)
    framework = _create_rice_framework(owner)
    manager = client_as(UserRole.MANAGER)

    created = manager.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )
    assert created.status_code == 201, created.text
    deleted = manager.delete(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides/{created.json()['id']}"
    )
    assert deleted.status_code == 204


def test_member_cannot_create_an_override(client_as: Callable[[UserRole], TestClient]) -> None:
    owner = client_as(UserRole.OWNER)
    project = _create_project(owner)
    scenario = _create_scenario(owner)
    framework = _create_rice_framework(owner)
    member = client_as(UserRole.MEMBER)

    response = member.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def test_creating_an_override_produces_an_audit_event(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    created = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    ).json()

    events = client.get(
        "/api/v1/audit",
        params={
            "action": "scenario_priority_override.create",
            "resource_type": "scenario_priority_override",
        },
    ).json()["items"]
    matching = [e for e in events if e["resource_id"] == created["id"]]
    assert len(matching) == 1
    assert matching[0]["event_metadata"] == {
        "scenario_id": scenario["id"],
        "project_id": project["id"],
        "framework_id": framework["id"],
    }


def test_deleting_an_override_produces_an_audit_event(client: TestClient) -> None:
    project = _create_project(client)
    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    created = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    ).json()
    client.delete(f"/api/v1/scenarios/{scenario['id']}/priority-overrides/{created['id']}")

    events = client.get(
        "/api/v1/audit",
        params={
            "action": "scenario_priority_override.delete",
            "resource_type": "scenario_priority_override",
        },
    ).json()["items"]
    assert any(e["resource_id"] == created["id"] for e in events)


# ---------------------------------------------------------------------------
# Multi-tenancy — cross-organization access must 404, never 403
# ---------------------------------------------------------------------------


def test_cannot_create_override_against_a_project_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-scenario-priority")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")

    scenario = _create_scenario(client)
    framework = _create_rice_framework(client)
    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": str(project_b.id),
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )
    assert response.status_code == 404


def test_cannot_create_override_against_a_framework_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-scenario-priority-fw")
    framework_b = make_prioritization_framework(db_session, organization=org_b, name="Org B RICE")

    project = _create_project(client)
    scenario = _create_scenario(client)
    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": str(framework_b.id),
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )
    assert response.status_code == 404


def test_cannot_create_override_against_a_scenario_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-scenario-priority-sc")
    scenario_b = make_scenario(db_session, organization=org_b, name="Org B Scenario")

    project = _create_project(client)
    framework = _create_rice_framework(client)
    response = client.post(
        f"/api/v1/scenarios/{scenario_b.id}/priority-overrides",
        json={
            "project_id": project["id"],
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": "1"}],
        },
    )
    assert response.status_code == 404


def test_comparison_404_for_scenario_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-scenario-priority-cmp")
    scenario_b = make_scenario(db_session, organization=org_b, name="Org B Scenario")
    framework = _create_rice_framework(client)

    response = client.get(
        f"/api/v1/scenarios/{scenario_b.id}/priority-comparison",
        params={"framework_id": framework["id"]},
    )
    assert response.status_code == 404


def test_comparison_404_for_framework_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-scenario-priority-cmp-fw")
    framework_b = make_prioritization_framework(db_session, organization=org_b, name="Org B RICE")

    scenario = _create_scenario(client)
    response = client.get(
        f"/api/v1/scenarios/{scenario['id']}/priority-comparison",
        params={"framework_id": str(framework_b.id)},
    )
    assert response.status_code == 404


def test_override_in_another_organization_is_invisible(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-scenario-priority-del")
    scenario_b = make_scenario(db_session, organization=org_b, name="Org B Scenario")

    assert (
        client.get(f"/api/v1/scenarios/{scenario_b.id}/priority-overrides").status_code == 404
    )
    assert (
        client.delete(
            f"/api/v1/scenarios/{scenario_b.id}/priority-overrides/"
            "00000000-0000-0000-0000-000000000000"
        ).status_code
        == 404
    )
