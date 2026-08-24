import csv
import io

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from tests.factories import make_allocation, make_organization, make_person, make_project


def _create_person(
    client: TestClient, *, email: str = "alex.morgan@example.com"
) -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": email},
    ).json()


def _create_project(client: TestClient, *, name: str = "Website Redesign") -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_team(client: TestClient, *, name: str = "Design") -> dict[str, object]:
    return client.post("/api/v1/teams", json={"name": name}).json()


def _parse_csv(content: bytes) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(content.decode("utf-8"))))


# ---------------------------------------------------------------------------
# CSV export per entity
# ---------------------------------------------------------------------------


def test_export_person_csv(client: TestClient) -> None:
    _create_person(client, email="jane@example.com")
    response = client.get("/api/v1/exports/person", params={"format": "csv"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    rows = _parse_csv(response.content)
    assert len(rows) == 1
    assert rows[0]["email"] == "jane@example.com"


def test_export_person_json(client: TestClient) -> None:
    _create_person(client, email="jane@example.com")
    response = client.get("/api/v1/exports/person", params={"format": "json"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert len(body) == 1
    assert body[0]["email"] == "jane@example.com"


def test_export_team_csv(client: TestClient) -> None:
    _create_team(client, name="Platform")
    response = client.get("/api/v1/exports/team", params={"format": "csv"})
    rows = _parse_csv(response.content)
    assert rows[0]["name"] == "Platform"


def test_export_team_membership_scoped_by_team(client: TestClient) -> None:
    person = _create_person(client)
    team = _create_team(client)
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})

    response = client.get(
        "/api/v1/exports/team_membership", params={"format": "csv", "team_id": team["id"]}
    )
    rows = _parse_csv(response.content)
    assert len(rows) == 1
    assert rows[0]["person_email"] == person["email"]
    assert rows[0]["team_name"] == team["name"]


def test_export_team_membership_unscoped(client: TestClient) -> None:
    person = _create_person(client)
    team = _create_team(client)
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})

    response = client.get("/api/v1/exports/team_membership", params={"format": "csv"})
    rows = _parse_csv(response.content)
    assert len(rows) == 1
    assert rows[0]["person_email"] == person["email"]
    assert rows[0]["team_name"] == team["name"]


def test_export_project_csv(client: TestClient) -> None:
    client.post("/api/v1/projects", json={"name": "Website", "external_id": "PRJ-1"})
    response = client.get("/api/v1/exports/project", params={"format": "csv"})
    rows = _parse_csv(response.content)
    assert rows[0]["external_id"] == "PRJ-1"


def test_export_allocation_includes_human_readable_references(client: TestClient) -> None:
    person = _create_person(client)
    project = _create_project(client)
    client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"], "project_id": project["id"],
            "start_date": "2026-09-01", "end_date": "2026-09-05", "allocation_hours": "20",
        },
    )
    response = client.get("/api/v1/exports/allocation", params={"format": "csv"})
    rows = _parse_csv(response.content)
    assert rows[0]["person_email"] == person["email"]
    assert rows[0]["allocation_hours"] == "20.00"


def test_export_allocation_scoped_by_person_and_project(client: TestClient) -> None:
    person = _create_person(client)
    project = _create_project(client)
    other_project = _create_project(client, name="Other")
    client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"], "project_id": project["id"],
            "start_date": "2026-09-01", "end_date": "2026-09-05", "allocation_hours": "20",
        },
    )
    client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"], "project_id": other_project["id"],
            "start_date": "2026-09-01", "end_date": "2026-09-05", "allocation_hours": "10",
        },
    )
    response = client.get(
        "/api/v1/exports/allocation",
        params={"format": "csv", "project_id": project["id"]},
    )
    rows = _parse_csv(response.content)
    assert len(rows) == 1
    assert rows[0]["allocation_hours"] == "20.00"


def test_export_working_schedule_csv_packs_entries(client: TestClient) -> None:
    person = _create_person(client)
    client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person["id"],
            "entries": [{"weekday": w, "hours": "8"} for w in range(5)],
        },
    )
    response = client.get("/api/v1/exports/working_schedule", params={"format": "csv"})
    rows = _parse_csv(response.content)
    assert rows[0]["entries"] == "0:8.00,1:8.00,2:8.00,3:8.00,4:8.00"


def test_export_working_schedule_json_uses_native_entries_array(client: TestClient) -> None:
    person = _create_person(client)
    client.post(
        "/api/v1/working-schedules",
        json={"person_id": person["id"], "entries": [{"weekday": 0, "hours": "8"}]},
    )
    response = client.get("/api/v1/exports/working_schedule", params={"format": "json"})
    body = response.json()
    assert body[0]["entries"] == [{"weekday": 0, "hours": "8.00"}]


def test_export_availability_exception_csv(client: TestClient) -> None:
    person = _create_person(client)
    client.post(
        "/api/v1/availability-exceptions",
        json={
            "person_id": person["id"], "start_date": "2026-09-15", "end_date": "2026-09-19",
            "availability_type": "annual_leave",
        },
    )
    response = client.get("/api/v1/exports/availability_exception", params={"format": "csv"})
    rows = _parse_csv(response.content)
    assert rows[0]["availability_type"] == "annual_leave"
    assert rows[0]["hours"] == ""


# ---------------------------------------------------------------------------
# Round-trip: export then re-import is idempotent
# ---------------------------------------------------------------------------


def test_export_then_reimport_person_is_unchanged(client: TestClient) -> None:
    _create_person(client, email="jane@example.com")
    exported = client.get("/api/v1/exports/person", params={"format": "csv"}).content

    response = client.post(
        "/api/v1/imports/person/apply",
        files={"file": ("people.csv", exported, "text/csv")},
        params={"mode": "upsert"},
    )
    body = response.json()
    assert body["applied"] is True
    assert body["unchanged_count"] == 1
    assert body["created_count"] == 0


# ---------------------------------------------------------------------------
# Row cap
# ---------------------------------------------------------------------------


def test_export_exceeding_max_rows_returns_422(client: TestClient) -> None:
    _create_person(client, email="a@example.com")
    _create_person(client, email="b@example.com")

    app.dependency_overrides[get_settings] = lambda: Settings(export_max_rows=1)
    try:
        response = client.get("/api/v1/exports/person", params={"format": "csv"})
    finally:
        del app.dependency_overrides[get_settings]
    assert response.status_code == 422


def test_export_never_truncates_silently(client: TestClient) -> None:
    """The 422 above is the only allowed response when over the cap — this
    test documents that there is no alternate code path that would instead
    return a partial (silently truncated) 200."""
    _create_person(client, email="a@example.com")
    _create_person(client, email="b@example.com")

    app.dependency_overrides[get_settings] = lambda: Settings(export_max_rows=1)
    try:
        response = client.get("/api/v1/exports/person", params={"format": "csv"})
        assert response.status_code != 200
    finally:
        del app.dependency_overrides[get_settings]


# ---------------------------------------------------------------------------
# CSV formula-injection defense
# ---------------------------------------------------------------------------


def test_export_sanitizes_formula_injection_in_csv(client: TestClient) -> None:
    client.post(
        "/api/v1/projects", json={"name": "Safe", "description": "=1+1", "external_id": "PRJ-1"}
    )
    response = client.get("/api/v1/exports/project", params={"format": "csv"})
    raw = response.content.decode("utf-8")
    assert "'=1+1" in raw
    assert "\n=1+1" not in raw and ",=1+1" not in raw


def test_export_json_does_not_sanitize(client: TestClient) -> None:
    """JSON is never opened by a spreadsheet application, so there is no
    formula-execution risk — sanitizing it would just corrupt the data."""
    client.post(
        "/api/v1/projects", json={"name": "Safe", "description": "=1+1", "external_id": "PRJ-1"}
    )
    response = client.get("/api/v1/exports/project", params={"format": "json"})
    body = response.json()
    assert body[0]["description"] == "=1+1"


# ---------------------------------------------------------------------------
# Source facts only — never a derived capacity value
# ---------------------------------------------------------------------------


def test_export_never_includes_derived_capacity_columns(client: TestClient) -> None:
    forbidden = {
        "utilization", "remaining_capacity", "over_allocation",
        "effective_capacity", "gross_capacity", "allocated_hours",
    }
    for entity_type in (
        "person", "team", "team_membership", "project",
        "allocation", "working_schedule", "availability_exception",
    ):
        response = client.get(f"/api/v1/exports/{entity_type}", params={"format": "csv"})
        header = response.content.decode("utf-8").splitlines()[0]
        columns = set(header.split(","))
        assert not (columns & forbidden), f"{entity_type} export leaked a derived column"


# ---------------------------------------------------------------------------
# Empty results
# ---------------------------------------------------------------------------


def test_export_empty_result_set(client: TestClient) -> None:
    response = client.get("/api/v1/exports/person", params={"format": "csv"})
    rows = _parse_csv(response.content)
    assert rows == []


def test_export_empty_result_set_json(client: TestClient) -> None:
    response = client.get("/api/v1/exports/person", params={"format": "json"})
    assert response.json() == []


# ---------------------------------------------------------------------------
# Multi-tenancy — Phase 16 audit addition
# ---------------------------------------------------------------------------


def test_export_filtered_by_another_organizations_project_returns_nothing(
    client: TestClient, db_session: Session
) -> None:
    """ADR 0012 already hardened ExportService._collect_rows to resolve
    every optional scope filter (person_id/team_id/project_id) through an
    organization-scoped repository lookup — this proves it holds: filtering
    an export by another organization's real project_id must yield zero
    rows, never that project's actual allocations."""
    org_b = make_organization(db_session, slug="org-b-export")
    person_b = make_person(db_session, organization=org_b, email="org-b-export@example.com")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    make_allocation(db_session, organization=org_b, person=person_b, project=project_b)

    response = client.get(
        "/api/v1/exports/allocation",
        params={"format": "json", "project_id": str(project_b.id)},
    )
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Invalid requests
# ---------------------------------------------------------------------------


def test_export_unsupported_format_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/exports/person", params={"format": "yaml"})
    assert response.status_code == 422


def test_export_invalid_entity_type_returns_422(client: TestClient) -> None:
    response = client.get("/api/v1/exports/not_a_real_entity", params={"format": "csv"})
    assert response.status_code == 422
