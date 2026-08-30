"""Phase 37 import/export coverage for ProjectDependency — registered
into the EXISTING Phase 6 import/export system (same /api/v1/imports,
/api/v1/exports endpoints, same validate-then-apply flow), mirroring
tests/api/test_risk_stakeholder_prioritization_import_export.py's
structure. See docs/adr/0037-import-export-project-dependency.md.
"""

import json
from collections.abc import Callable, Mapping, Sequence

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import ProjectDependencyType, UserRole
from tests.factories import make_organization, make_project, make_project_dependency


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


def _create_project(client: TestClient, external_id: str) -> dict[str, object]:
    return client.post(
        "/api/v1/projects", json={"name": f"Project {external_id}", "external_id": external_id}
    ).json()


# ---------------------------------------------------------------------------
# Create / match / self-dependency / duplicate-in-file
# ---------------------------------------------------------------------------


def test_project_dependency_import_create_via_external_ids(client: TestClient) -> None:
    _create_project(client, "PRJ-A")
    _create_project(client, "PRJ-B")
    rows = [{
        "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-B",
        "dependency_type": "blocks",
    }]
    response = _json_upload(client, "project_dependency", rows, action="apply")
    assert response.json()["created_count"] == 1


def test_project_dependency_import_matches_existing_edge_as_unchanged(client: TestClient) -> None:
    """No update case exists for this entity — a matching edge is always
    'unchanged,' never 'update' (mirrors TeamMembership's own shape)."""
    project_a = _create_project(client, "PRJ-A")
    project_b = _create_project(client, "PRJ-B")
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    rows = [{
        "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-B",
        "dependency_type": "blocks",
    }]
    response = _json_upload(client, "project_dependency", rows, action="apply")
    body = response.json()
    assert body["unchanged_count"] == 1
    assert body["created_count"] == 0
    assert body["rows"][0]["status"] == "valid_unchanged"


def test_project_dependency_import_repeated_identical_file_is_deterministic_unchanged(
    client: TestClient,
) -> None:
    _create_project(client, "PRJ-A")
    _create_project(client, "PRJ-B")
    csv_text = (
        "from_project_external_id,to_project_external_id,dependency_type\nPRJ-A,PRJ-B,blocks\n"
    )
    _csv_upload(client, "project_dependency", csv_text, action="apply")
    response = _csv_upload(client, "project_dependency", csv_text, action="apply")
    body = response.json()
    assert body["unchanged_count"] == 1
    assert body["created_count"] == 0


def test_project_dependency_import_self_dependency_rejected(client: TestClient) -> None:
    _create_project(client, "PRJ-A")
    rows = [{
        "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-A",
        "dependency_type": "blocks",
    }]
    response = _json_upload(client, "project_dependency", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "domain_rule_violated"


def test_project_dependency_import_duplicate_pair_in_file_blocks(client: TestClient) -> None:
    _create_project(client, "PRJ-A")
    _create_project(client, "PRJ-B")
    rows = [
        {
            "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-B",
            "dependency_type": "blocks",
        },
        {
            "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-B",
            "dependency_type": "blocks",
        },
    ]
    response = _json_upload(client, "project_dependency", rows)
    body = response.json()
    assert body["invalid_count"] == 1
    assert body["rows"][1]["errors"][0]["code"] == "duplicate_in_file"


def test_project_dependency_import_different_types_between_same_projects_both_create(
    client: TestClient,
) -> None:
    """The unique key is the full (from, to, type) triple — two DIFFERENT
    edge types between the same pair of projects are both valid, matching
    the table's own UniqueConstraint exactly."""
    _create_project(client, "PRJ-A")
    _create_project(client, "PRJ-B")
    rows = [
        {
            "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-B",
            "dependency_type": "blocks",
        },
        {
            "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-B",
            "dependency_type": "related",
        },
    ]
    response = _json_upload(client, "project_dependency", rows, action="apply")
    assert response.json()["created_count"] == 2


# ---------------------------------------------------------------------------
# Reference resolution / validation
# ---------------------------------------------------------------------------


def test_project_dependency_import_unresolvable_from_project_blocks(client: TestClient) -> None:
    _create_project(client, "PRJ-B")
    rows = [{
        "from_project_external_id": "NO-SUCH-PROJECT", "to_project_external_id": "PRJ-B",
        "dependency_type": "blocks",
    }]
    response = _json_upload(client, "project_dependency", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["field"] == "from_project_external_id"
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_project_dependency_import_unresolvable_to_project_blocks(client: TestClient) -> None:
    _create_project(client, "PRJ-A")
    rows = [{
        "from_project_external_id": "PRJ-A", "to_project_external_id": "NO-SUCH-PROJECT",
        "dependency_type": "blocks",
    }]
    response = _json_upload(client, "project_dependency", rows)
    body = response.json()
    assert body["rows"][0]["errors"][0]["field"] == "to_project_external_id"
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_project_dependency_import_missing_required_dependency_type_blocks(
    client: TestClient,
) -> None:
    csv_text = "from_project_external_id,to_project_external_id\nPRJ-A,PRJ-B\n"
    response = _csv_upload(client, "project_dependency", csv_text)
    assert response.json()["file_error"]["code"] == "missing_required_column"


def test_project_dependency_import_invalid_dependency_type_rejected(client: TestClient) -> None:
    _create_project(client, "PRJ-A")
    _create_project(client, "PRJ-B")
    rows = [{
        "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-B",
        "dependency_type": "supersedes",
    }]
    response = _json_upload(client, "project_dependency", rows)
    assert response.json()["ready_to_apply"] is False


# ---------------------------------------------------------------------------
# Cycle detection (BLOCKS only)
# ---------------------------------------------------------------------------


def test_project_dependency_import_cycle_against_existing_graph_blocks(client: TestClient) -> None:
    project_a = _create_project(client, "PRJ-A")
    project_b = _create_project(client, "PRJ-B")
    project_c = _create_project(client, "PRJ-C")
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    client.post(
        f"/api/v1/projects/{project_b['id']}/dependencies",
        json={"to_project_id": project_c["id"], "dependency_type": "blocks"},
    )
    rows = [{
        "from_project_external_id": "PRJ-C", "to_project_external_id": "PRJ-A",
        "dependency_type": "blocks",
    }]
    response = _json_upload(client, "project_dependency", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "domain_rule_violated"


def test_project_dependency_import_cycle_within_the_same_file_blocks(client: TestClient) -> None:
    """Batch simulation (mirroring WorkingSchedule's overlap pre-check): a
    LATER row in the same file must see the cycle an EARLIER row in that
    same file would already have introduced — none of these edges exist
    in the database yet."""
    _create_project(client, "PRJ-A")
    _create_project(client, "PRJ-B")
    _create_project(client, "PRJ-C")
    rows = [
        {
            "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-B",
            "dependency_type": "blocks",
        },
        {
            "from_project_external_id": "PRJ-B", "to_project_external_id": "PRJ-C",
            "dependency_type": "blocks",
        },
        {
            "from_project_external_id": "PRJ-C", "to_project_external_id": "PRJ-A",
            "dependency_type": "blocks",
        },
    ]
    response = _json_upload(client, "project_dependency", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["status"] == "valid_create"
    assert body["rows"][1]["status"] == "valid_create"
    assert body["rows"][2]["errors"][0]["code"] == "domain_rule_violated"


def test_project_dependency_import_related_type_cycle_is_allowed(client: TestClient) -> None:
    """`related`/`enables` don't participate in cycle detection — matches
    the direct API's identical behavior (detects_cycle's own docstring)."""
    project_a = _create_project(client, "PRJ-A")
    project_b = _create_project(client, "PRJ-B")
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "related"},
    )
    rows = [{
        "from_project_external_id": "PRJ-B", "to_project_external_id": "PRJ-A",
        "dependency_type": "related",
    }]
    response = _json_upload(client, "project_dependency", rows, action="apply")
    assert response.json()["created_count"] == 1


# ---------------------------------------------------------------------------
# Templates / export
# ---------------------------------------------------------------------------


def test_project_dependency_template_round_trips_clean_through_validate(
    client: TestClient,
) -> None:
    _create_project(client, "PRJ-100")
    _create_project(client, "PRJ-200")
    template = client.get(
        "/api/v1/imports/project_dependency/template", params={"format": "csv"}
    ).text
    response = _csv_upload(client, "project_dependency", template)
    assert response.json()["ready_to_apply"] is True


def test_project_dependency_export_csv_includes_headers_and_row(client: TestClient) -> None:
    project_a = _create_project(client, "PRJ-A")
    project_b = _create_project(client, "PRJ-B")
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    response = client.get("/api/v1/exports/project_dependency", params={"format": "csv"})
    assert response.status_code == 200
    lines = response.text.splitlines()
    assert "dependency_type" in lines[0]
    assert "PRJ-A" in lines[1] and "PRJ-B" in lines[1]


def test_project_dependency_export_round_trips_through_reimport(client: TestClient) -> None:
    project_a = _create_project(client, "PRJ-A")
    project_b = _create_project(client, "PRJ-B")
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    exported = client.get(
        "/api/v1/exports/project_dependency", params={"format": "csv"}
    ).text
    response = _csv_upload(client, "project_dependency", exported, action="apply")
    body = response.json()
    assert body["applied"] is True
    assert body["unchanged_count"] == 1


def test_project_dependency_export_never_exposes_internal_fields(client: TestClient) -> None:
    project_a = _create_project(client, "PRJ-A")
    project_b = _create_project(client, "PRJ-B")
    client.post(
        f"/api/v1/projects/{project_a['id']}/dependencies",
        json={"to_project_id": project_b["id"], "dependency_type": "blocks"},
    )
    listing = client.get("/api/v1/exports/project_dependency", params={"format": "json"})
    (exported,) = listing.json()
    assert set(exported.keys()) == {
        "id", "from_project_id", "from_project_external_id", "to_project_id",
        "to_project_external_id", "dependency_type", "created_at",
    }


# ---------------------------------------------------------------------------
# Authorization / multi-tenancy
# ---------------------------------------------------------------------------


def test_member_cannot_import_project_dependency(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    member = client_as(UserRole.MEMBER)
    rows = [{
        "from_project_external_id": "PRJ-A", "to_project_external_id": "PRJ-B",
        "dependency_type": "blocks",
    }]
    response = member.post(
        "/api/v1/imports/project_dependency/apply",
        files={"file": ("d.json", json.dumps(rows).encode(), "application/json")},
        params={"mode": "upsert"},
    )
    assert response.status_code == 403


def test_member_can_export_project_dependency_but_not_import(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    member = client_as(UserRole.MEMBER)
    response = member.get(
        "/api/v1/exports/project_dependency", params={"format": "csv"}
    )
    assert response.status_code == 200


def test_project_dependency_import_cross_organization_reference_is_unresolvable(
    client: TestClient, db_session: Session
) -> None:
    """A project_external_id belonging to another organization must be
    unresolvable, exactly like a nonexistent one — mirrors ADR 0016's/ADR
    0036's identical cross-org import regression tests."""
    org_b = make_organization(db_session, slug="org-b")
    project_b = make_project(db_session, organization=org_b, external_id="ORG-B-PRJ")
    _create_project(client, "PRJ-A")
    db_session.commit()

    rows = [{
        "from_project_external_id": "PRJ-A", "to_project_external_id": project_b.external_id,
        "dependency_type": "blocks",
    }]
    response = _json_upload(client, "project_dependency", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_project_dependency_export_never_returns_another_organizations_edges(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b")
    project_b1 = make_project(db_session, organization=org_b, name="Org B Project 1")
    project_b2 = make_project(db_session, organization=org_b, name="Org B Project 2")
    make_project_dependency(
        db_session, organization=org_b, from_project=project_b1, to_project=project_b2,
        dependency_type=ProjectDependencyType.BLOCKS,
    )
    db_session.commit()

    exported = client.get(
        "/api/v1/exports/project_dependency", params={"format": "json"}
    ).json()
    assert exported == []
