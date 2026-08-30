"""Phase 36 import/export coverage for Risk, Stakeholder, and
ProjectPriorityScore — registered into the EXISTING Phase 6 import/export
system (same /api/v1/imports, /api/v1/exports endpoints, same
validate-then-apply flow), mirroring tests/api/test_skill_import_export.py's
structure exactly. See
docs/adr/0036-import-export-risk-stakeholder-prioritization.md.
"""

import json
from collections.abc import Callable, Mapping, Sequence

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import UserRole
from tests.factories import make_organization, make_person, make_project, make_risk


def _csv_upload(
    client: TestClient,
    entity_type: str,
    csv_text: str,
    *,
    action: str = "validate",
    mode: str = "upsert",
) -> httpx.Response:
    return client.post(
        f"/api/v1/imports/{entity_type}/{action}",
        files={"file": ("data.csv", csv_text.encode("utf-8"), "text/csv")},
        params={"mode": mode},
    )


def _json_upload(
    client: TestClient,
    entity_type: str,
    rows: Sequence[Mapping[str, object]],
    *,
    action: str = "validate",
    mode: str = "upsert",
) -> httpx.Response:
    content = json.dumps(rows).encode("utf-8")
    return client.post(
        f"/api/v1/imports/{entity_type}/{action}",
        files={"file": ("data.json", content, "application/json")},
        params={"mode": mode},
    )


def _create_project(client: TestClient, external_id: str = "PRJ-1") -> dict[str, object]:
    return client.post(
        "/api/v1/projects", json={"name": "Website", "external_id": external_id}
    ).json()


def _create_person(client: TestClient, email: str = "jane@example.com") -> dict[str, object]:
    return client.post(
        "/api/v1/people", json={"first_name": "Jane", "last_name": "Doe", "email": email}
    ).json()


def _create_rice_framework(client: TestClient, name: str = "RICE") -> dict[str, object]:
    return client.post(
        "/api/v1/prioritization/frameworks", json={"name": name, "framework_type": "rice"}
    ).json()


def _create_moscow_framework(client: TestClient, name: str = "MoSCoW") -> dict[str, object]:
    return client.post(
        "/api/v1/prioritization/frameworks", json={"name": name, "framework_type": "moscow"}
    ).json()


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


def test_risk_import_create_via_project_external_id(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    rows = [{
        "external_id": "RISK-1", "project_external_id": "PRJ-1",
        "description": "Vendor may slip", "probability": "high", "impact": "medium",
    }]
    response = _json_upload(client, "risk", rows, action="apply")
    body = response.json()
    assert body["created_count"] == 1


def test_risk_import_matches_by_external_id_on_reimport(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    rows = [{
        "external_id": "RISK-1", "project_external_id": "PRJ-1",
        "description": "Vendor may slip", "status": "open",
    }]
    _json_upload(client, "risk", rows, action="apply")
    rows[0]["status"] = "mitigating"
    response = _json_upload(client, "risk", rows, action="apply")
    assert response.json()["updated_count"] == 1


def test_risk_import_repeated_identical_file_is_deterministic_unchanged(
    client: TestClient,
) -> None:
    _create_project(client, external_id="PRJ-1")
    csv_text = "external_id,project_external_id,description\nRISK-1,PRJ-1,Vendor may slip\n"
    _csv_upload(client, "risk", csv_text, action="apply")
    response = _csv_upload(client, "risk", csv_text, action="apply")
    body = response.json()
    assert body["unchanged_count"] == 1
    assert body["created_count"] == 0


def test_risk_import_without_external_id_always_creates_on_reimport(client: TestClient) -> None:
    """Matches Project/Allocation's exact Phase 6 precedent: a row with no
    external_id has no identity at all and always creates."""
    _create_project(client, external_id="PRJ-1")
    csv_text = "project_external_id,description\nPRJ-1,Vendor may slip\n"
    _csv_upload(client, "risk", csv_text, action="apply")
    response = _csv_upload(client, "risk", csv_text, action="apply")
    assert response.json()["created_count"] == 1


def test_risk_import_resolves_owner_by_email(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    _create_person(client, "owner@example.com")
    rows = [{
        "project_external_id": "PRJ-1", "description": "Vendor may slip",
        "owner_person_email": "owner@example.com",
    }]
    response = _json_upload(client, "risk", rows, action="apply")
    assert response.json()["created_count"] == 1
    listing = client.get(
        f"/api/v1/projects/{_create_project(client, external_id='PRJ-2')['id']}/risks"
    ).json()
    assert listing == []  # sanity: PRJ-2's risks are unaffected


def test_risk_import_unresolvable_owner_email_blocks(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    rows = [{
        "project_external_id": "PRJ-1", "description": "Vendor may slip",
        "owner_person_email": "nobody@example.com",
    }]
    response = _json_upload(client, "risk", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_risk_import_unresolvable_project_reference_blocks(client: TestClient) -> None:
    rows = [{"project_external_id": "NO-SUCH-PROJECT", "description": "Vendor may slip"}]
    response = _json_upload(client, "risk", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_risk_import_missing_required_description_blocks(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    csv_text = "project_external_id\nPRJ-1\n"
    response = _csv_upload(client, "risk", csv_text)
    assert response.json()["file_error"]["code"] == "missing_required_column"


def test_risk_import_invalid_probability_rejected(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    rows = [{
        "project_external_id": "PRJ-1", "description": "Vendor may slip",
        "probability": "extreme",
    }]
    response = _json_upload(client, "risk", rows)
    assert response.json()["ready_to_apply"] is False


def test_risk_import_never_exposes_internal_fields(client: TestClient) -> None:
    """Only the documented Risk columns ever come back — nothing from a
    joined Person/Project row beyond what ENTITY_COLUMNS declares."""
    _create_project(client, external_id="PRJ-1")
    rows = [{"project_external_id": "PRJ-1", "description": "Vendor may slip"}]
    _json_upload(client, "risk", rows, action="apply")
    listing = client.get("/api/v1/exports/risk", params={"format": "json"})
    (exported,) = listing.json()
    assert set(exported.keys()) <= {
        "id", "external_id", "project_id", "project_external_id", "description", "cause",
        "potential_effect", "probability", "impact", "response", "owner_person_id", "status",
        "review_date", "created_at", "updated_at",
    }


# ---------------------------------------------------------------------------
# Stakeholder
# ---------------------------------------------------------------------------


def test_stakeholder_import_create_without_person_reference_always_creates(
    client: TestClient,
) -> None:
    """No person reference -> no natural key at all, matching Project/
    Allocation's own "no external_id -> always creates" precedent."""
    _create_project(client, external_id="PRJ-1")
    rows = [{"project_external_id": "PRJ-1", "name": "Jordan Client", "role": "Sponsor"}]
    _json_upload(client, "stakeholder", rows, action="apply")
    response = _json_upload(client, "stakeholder", rows, action="apply")
    assert response.json()["created_count"] == 1


def test_stakeholder_import_two_person_less_rows_both_create_in_one_file(
    client: TestClient,
) -> None:
    """Two stakeholders on the same project, neither linked to a Person,
    must NOT be flagged as duplicate-in-file — each has identity=None,
    not a colliding compound key."""
    _create_project(client, external_id="PRJ-1")
    rows = [
        {"project_external_id": "PRJ-1", "name": "Jordan Client", "role": "Sponsor"},
        {"project_external_id": "PRJ-1", "name": "Alex Regulator", "role": "Compliance"},
    ]
    response = _json_upload(client, "stakeholder", rows, action="apply")
    body = response.json()
    assert body["created_count"] == 2
    assert body["invalid_count"] == 0


def test_stakeholder_import_create_and_update_via_person_email(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    _create_person(client, "jane@example.com")
    rows = [{
        "project_external_id": "PRJ-1", "person_email": "jane@example.com",
        "name": "Jane Doe", "role": "Sponsor",
    }]
    create_response = _json_upload(client, "stakeholder", rows, action="apply")
    assert create_response.json()["created_count"] == 1

    rows[0]["role"] = "Steering committee"
    update_response = _json_upload(client, "stakeholder", rows, action="apply")
    assert update_response.json()["updated_count"] == 1


def test_stakeholder_import_unresolvable_person_email_blocks(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    rows = [{
        "project_external_id": "PRJ-1", "person_email": "nobody@example.com",
        "name": "Jane Doe", "role": "Sponsor",
    }]
    response = _json_upload(client, "stakeholder", rows)
    assert response.json()["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_stakeholder_export_round_trips_through_reimport(client: TestClient) -> None:
    project = _create_project(client, external_id="PRJ-1")
    client.post(
        f"/api/v1/projects/{project['id']}/stakeholders",
        json={"name": "Jordan Client", "role": "Sponsor"},
    )
    exported = client.get("/api/v1/exports/stakeholder", params={"format": "csv"}).text
    response = _csv_upload(client, "stakeholder", exported, action="apply")
    body = response.json()
    assert body["applied"] is True
    # No person reference on export either -> re-import always creates,
    # matching the "no natural key" contract, never a false "unchanged".
    assert body["created_count"] == 1


# ---------------------------------------------------------------------------
# ProjectPriorityScore
# ---------------------------------------------------------------------------


def test_project_priority_score_import_create_via_framework_name(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    _create_rice_framework(client, "RICE")
    rows = [{
        "project_external_id": "PRJ-1", "framework_name": "RICE",
        "values": "reach:8000,impact:2,confidence:80,effort:5",
    }]
    response = _json_upload(client, "project_priority_score", rows, action="apply")
    assert response.json()["created_count"] == 1


def test_project_priority_score_import_updates_values(client: TestClient) -> None:
    project = _create_project(client, external_id="PRJ-1")
    framework = _create_rice_framework(client, "RICE")
    client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [{"criterion_key": "reach", "value": 100}],
        },
    )
    rows = [{
        "project_external_id": "PRJ-1", "framework_name": "RICE",
        "values": "reach:9000",
    }]
    response = _json_upload(client, "project_priority_score", rows, action="apply")
    assert response.json()["updated_count"] == 1


def test_project_priority_score_import_repeated_identical_file_is_unchanged(
    client: TestClient,
) -> None:
    # Values are written at the column's own Numeric(12, 3) precision —
    # matching _values_key's documented "compared as strings, so
    # formatting differences count as a change" convention (the same
    # convention WorkingSchedule's _entries_key already established) —
    # so a byte-identical reimport is guaranteed to compare unchanged.
    _create_project(client, external_id="PRJ-1")
    _create_rice_framework(client, "RICE")
    csv_text = (
        "project_external_id,framework_name,values\n"
        'PRJ-1,RICE,"reach:8000.000,impact:2.000,confidence:80.000,effort:5.000"\n'
    )
    _csv_upload(client, "project_priority_score", csv_text, action="apply")
    response = _csv_upload(client, "project_priority_score", csv_text, action="apply")
    body = response.json()
    assert body["unchanged_count"] == 1
    assert body["created_count"] == 0


def test_project_priority_score_import_unknown_criterion_key_blocks(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    _create_rice_framework(client, "RICE")
    rows = [{
        "project_external_id": "PRJ-1", "framework_name": "RICE",
        "values": [{"criterion_key": "not_a_real_criterion", "value": 5}],
    }]
    response = _json_upload(client, "project_priority_score", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "domain_rule_violated"


def test_project_priority_score_import_moscow_category(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    _create_moscow_framework(client, "MoSCoW")
    rows = [{"project_external_id": "PRJ-1", "framework_name": "MoSCoW", "category": "must"}]
    response = _json_upload(client, "project_priority_score", rows, action="apply")
    assert response.json()["created_count"] == 1


def test_project_priority_score_import_category_rejected_for_non_moscow_framework(
    client: TestClient,
) -> None:
    _create_project(client, external_id="PRJ-1")
    _create_rice_framework(client, "RICE")
    rows = [{"project_external_id": "PRJ-1", "framework_name": "RICE", "category": "must"}]
    response = _json_upload(client, "project_priority_score", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "domain_rule_violated"


def test_project_priority_score_import_unresolvable_framework_blocks(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    rows = [{"project_external_id": "PRJ-1", "framework_name": "No Such Framework"}]
    response = _json_upload(client, "project_priority_score", rows)
    assert response.json()["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_project_priority_score_export_round_trips_through_reimport(client: TestClient) -> None:
    project = _create_project(client, external_id="PRJ-1")
    framework = _create_rice_framework(client, "RICE")
    client.post(
        f"/api/v1/projects/{project['id']}/priority-scores",
        json={
            "framework_id": framework["id"],
            "values": [
                {"criterion_key": "reach", "value": 8000},
                {"criterion_key": "impact", "value": 2},
                {"criterion_key": "confidence", "value": 80},
                {"criterion_key": "effort", "value": 5},
            ],
        },
    )
    exported = client.get(
        "/api/v1/exports/project_priority_score", params={"format": "csv"}
    ).text
    response = _csv_upload(client, "project_priority_score", exported, action="apply")
    body = response.json()
    assert body["applied"] is True
    assert body["unchanged_count"] == 1


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def test_risk_template_round_trips_clean_through_validate(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-100")
    template = client.get("/api/v1/imports/risk/template", params={"format": "csv"}).text
    response = _csv_upload(client, "risk", template)
    assert response.json()["ready_to_apply"] is True


def test_stakeholder_template_round_trips_clean_through_validate(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-100")
    template = client.get(
        "/api/v1/imports/stakeholder/template", params={"format": "csv"}
    ).text
    response = _csv_upload(client, "stakeholder", template)
    assert response.json()["ready_to_apply"] is True


def test_project_priority_score_template_round_trips_clean_through_validate(
    client: TestClient,
) -> None:
    _create_project(client, external_id="PRJ-100")
    _create_rice_framework(client, "RICE")
    template = client.get(
        "/api/v1/imports/project_priority_score/template", params={"format": "csv"}
    ).text
    response = _csv_upload(client, "project_priority_score", template)
    assert response.json()["ready_to_apply"] is True


# ---------------------------------------------------------------------------
# Authorization / multi-tenancy
# ---------------------------------------------------------------------------


def test_member_cannot_import_risk(client_as: Callable[[UserRole], TestClient]) -> None:
    member = client_as(UserRole.MEMBER)
    rows = [{"project_external_id": "PRJ-1", "description": "Vendor may slip"}]
    response = member.post(
        "/api/v1/imports/risk/apply",
        files={"file": ("d.json", json.dumps(rows).encode(), "application/json")},
        params={"mode": "upsert"},
    )
    assert response.status_code == 403


def test_member_can_export_risk_but_not_import(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    member = client_as(UserRole.MEMBER)
    assert member.get("/api/v1/exports/risk", params={"format": "csv"}).status_code == 200


def test_risk_import_cross_organization_project_reference_is_unresolvable(
    client: TestClient, db_session: Session
) -> None:
    """A project_external_id belonging to another organization must be
    unresolvable, exactly like a nonexistent one — proving the identity-
    resolution lookup is organization-scoped (mirrors ADR 0016's identical
    Allocation-import regression test)."""
    org_b = make_organization(db_session, slug="org-b")
    project_b = make_project(db_session, organization=org_b, external_id="ORG-B-PRJ")
    db_session.commit()

    rows = [{"project_external_id": project_b.external_id, "description": "Vendor may slip"}]
    response = _json_upload(client, "risk", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_risk_export_never_returns_another_organizations_rows(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    owner_b = make_person(db_session, organization=org_b, email="owner-b@example.com")
    make_risk(
        db_session, organization=org_b, project=project_b, owner=owner_b,
        description="Org B risk", external_id="ORG-B-RISK",
    )
    db_session.commit()

    exported = client.get("/api/v1/exports/risk", params={"format": "json"}).json()
    assert exported == []
