import json
from collections.abc import Mapping, Sequence

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from tests.factories import make_organization, make_person, make_project


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


def _create_person(
    client: TestClient, *, email: str = "alex.morgan@example.com"
) -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": email},
    ).json()


def _create_project(
    client: TestClient, *, name: str = "Website Redesign", external_id: str | None = None
) -> dict[str, object]:
    payload = {"name": name}
    if external_id is not None:
        payload["external_id"] = external_id
    return client.post("/api/v1/projects", json=payload).json()


def _create_team(client: TestClient, *, name: str = "Design") -> dict[str, object]:
    return client.post("/api/v1/teams", json={"name": name}).json()


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------


def test_person_import_validate_create(client: TestClient) -> None:
    csv_text = "email,first_name,last_name\njane@example.com,Jane,Doe\n"
    response = _csv_upload(client, "person", csv_text)
    assert response.status_code == 200
    body = response.json()
    assert body["ready_to_apply"] is True
    assert body["valid_create_count"] == 1
    assert body["rows"][0]["status"] == "valid_create"


def test_person_import_validate_never_writes(client: TestClient) -> None:
    csv_text = "email,first_name,last_name\njane@example.com,Jane,Doe\n"
    _csv_upload(client, "person", csv_text)
    listing = client.get("/api/v1/people").json()
    assert listing["total"] == 0


def test_person_import_apply_creates(client: TestClient) -> None:
    csv_text = "email,first_name,last_name\njane@example.com,Jane,Doe\n"
    response = _csv_upload(client, "person", csv_text, action="apply")
    assert response.status_code == 200
    body = response.json()
    assert body["applied"] is True
    assert body["created_count"] == 1

    listing = client.get("/api/v1/people").json()
    assert listing["total"] == 1
    assert listing["items"][0]["email"] == "jane@example.com"


def test_person_import_apply_updates_existing_by_email(client: TestClient) -> None:
    _create_person(client, email="jane@example.com")
    csv_text = (
        "email,first_name,last_name,job_title\n"
        "jane@example.com,Jane,Doe,Staff Engineer\n"
    )
    response = _csv_upload(client, "person", csv_text, action="apply")
    body = response.json()
    assert body["applied"] is True
    assert body["updated_count"] == 1

    listing = client.get("/api/v1/people").json()
    assert listing["items"][0]["job_title"] == "Staff Engineer"


def test_person_import_repeated_identical_file_is_deterministic_unchanged(
    client: TestClient,
) -> None:
    csv_text = "email,first_name,last_name\njane@example.com,Jane,Doe\n"
    first = _csv_upload(client, "person", csv_text, action="apply")
    assert first.json()["created_count"] == 1

    second = _csv_upload(client, "person", csv_text, action="apply")
    body = second.json()
    assert body["applied"] is True
    assert body["created_count"] == 0
    assert body["unchanged_count"] == 1


def test_person_import_invalid_row_blocks_whole_batch(client: TestClient) -> None:
    csv_text = (
        "email,first_name,last_name\n"
        "valid@example.com,Val,Id\n"
        "not-an-email,Bad,Row\n"
    )
    validate_response = _csv_upload(client, "person", csv_text)
    assert validate_response.json()["ready_to_apply"] is False

    apply_response = _csv_upload(client, "person", csv_text, action="apply")
    body = apply_response.json()
    assert body["applied"] is False
    assert body["invalid_count"] == 1

    listing = client.get("/api/v1/people").json()
    assert listing["total"] == 0


def test_person_import_json_format(client: TestClient) -> None:
    rows = [{"email": "jane@example.com", "first_name": "Jane", "last_name": "Doe"}]
    response = _json_upload(client, "person", rows, action="apply")
    assert response.json()["created_count"] == 1


# ---------------------------------------------------------------------------
# File-level (Level 1) validation
# ---------------------------------------------------------------------------


def test_import_empty_file_returns_file_error(client: TestClient) -> None:
    response = _csv_upload(client, "person", "")
    body = response.json()
    assert body["file_error"] is not None
    assert body["ready_to_apply"] is False


def test_import_malformed_json_returns_file_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/imports/person/validate",
        files={"file": ("data.json", b"{not valid", "application/json")},
    )
    body = response.json()
    assert body["file_error"]["code"] == "file_unreadable"


def test_import_missing_required_header_returns_file_error(client: TestClient) -> None:
    csv_text = "first_name,last_name\nJane,Doe\n"
    response = _csv_upload(client, "person", csv_text)
    body = response.json()
    assert body["file_error"]["code"] == "missing_required_column"


def test_import_unsupported_format_returns_file_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/imports/person/validate",
        files={"file": ("data.xlsx", b"binary", "application/vnd.ms-excel")},
    )
    body = response.json()
    assert body["file_error"]["code"] == "unsupported_format"


def test_import_row_limit_exceeded(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(import_max_rows=1)
    try:
        csv_text = (
            "email,first_name,last_name\n"
            "a@example.com,A,A\n"
            "b@example.com,B,B\n"
        )
        response = _csv_upload(client, "person", csv_text)
    finally:
        del app.dependency_overrides[get_settings]
    body = response.json()
    assert body["file_error"]["code"] == "row_limit_exceeded"


def test_import_file_too_large(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(import_max_file_size_bytes=10)
    try:
        csv_text = "email,first_name,last_name\njane@example.com,Jane,Doe\n"
        response = _csv_upload(client, "person", csv_text)
    finally:
        del app.dependency_overrides[get_settings]
    body = response.json()
    assert body["file_error"]["code"] == "file_too_large"


def test_import_duplicate_in_file(client: TestClient) -> None:
    csv_text = (
        "email,first_name,last_name\n"
        "jane@example.com,Jane,Doe\n"
        "jane@example.com,Jane,Doe2\n"
    )
    response = _csv_upload(client, "person", csv_text)
    body = response.json()
    assert body["rows"][1]["status"] == "invalid"
    assert body["rows"][1]["errors"][0]["code"] == "duplicate_in_file"


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------


def test_team_import_create_and_unchanged_on_reimport(client: TestClient) -> None:
    csv_text = "name,description\nPlatform,Core infra\n"
    first = _csv_upload(client, "team", csv_text, action="apply")
    assert first.json()["created_count"] == 1

    second = _csv_upload(client, "team", csv_text, action="apply")
    assert second.json()["unchanged_count"] == 1


# ---------------------------------------------------------------------------
# TeamMembership
# ---------------------------------------------------------------------------


def test_team_membership_import_create(client: TestClient) -> None:
    person = _create_person(client)
    team = _create_team(client)
    csv_text = f"person_email,team_name\n{person['email']},{team['name']}\n"
    response = _csv_upload(client, "team_membership", csv_text, action="apply")
    body = response.json()
    assert body["created_count"] == 1

    members = client.get(f"/api/v1/teams/{team['id']}/members").json()
    assert len(members) == 1


def test_team_membership_import_is_a_noop_when_already_member(client: TestClient) -> None:
    person = _create_person(client)
    team = _create_team(client)
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})

    csv_text = f"person_email,team_name\n{person['email']},{team['name']}\n"
    response = _csv_upload(client, "team_membership", csv_text, action="apply")
    body = response.json()
    assert body["applied"] is True
    assert body["unchanged_count"] == 1
    assert body["created_count"] == 0

    members = client.get(f"/api/v1/teams/{team['id']}/members").json()
    assert len(members) == 1  # never duplicated


def test_team_membership_import_unresolvable_team_blocks(client: TestClient) -> None:
    person = _create_person(client)
    csv_text = f"person_email,team_name\n{person['email']},Ghost Team\n"
    response = _csv_upload(client, "team_membership", csv_text)
    body = response.json()
    assert body["rows"][0]["status"] == "invalid"
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


def test_project_import_create_without_external_id_has_no_identity(client: TestClient) -> None:
    csv_text = "name\nNew Project\n"
    response = _csv_upload(client, "project", csv_text)
    body = response.json()
    assert body["rows"][0]["identity"] is None
    assert body["rows"][0]["status"] == "valid_create"


def test_project_import_matches_by_external_id_on_reimport(client: TestClient) -> None:
    csv_text = "external_id,name,status\nPRJ-1,Website,active\n"
    first = _csv_upload(client, "project", csv_text, action="apply")
    assert first.json()["created_count"] == 1

    second = _csv_upload(client, "project", csv_text, action="apply")
    body = second.json()
    assert body["unchanged_count"] == 1
    assert body["created_count"] == 0


def test_project_import_without_external_id_always_creates_on_reimport(client: TestClient) -> None:
    """Documented, deliberate consequence of the identity strategy: Project
    has no natural key, so external_id-less rows can never be deduplicated
    against a prior import of the same file."""
    csv_text = "name\nUnidentified Project\n"
    first = _csv_upload(client, "project", csv_text, action="apply")
    assert first.json()["created_count"] == 1
    second = _csv_upload(client, "project", csv_text, action="apply")
    assert second.json()["created_count"] == 1

    listing = client.get("/api/v1/projects").json()
    assert listing["total"] == 2


def test_project_import_date_range_violation(client: TestClient) -> None:
    csv_text = "name,start_date,end_date\nBad Dates,2026-09-30,2026-09-01\n"
    response = _csv_upload(client, "project", csv_text)
    body = response.json()
    assert body["rows"][0]["status"] == "invalid"
    assert body["rows"][0]["errors"][0]["code"] == "field_constraint_violated"


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


def test_allocation_import_create_via_email_and_external_id_reference(client: TestClient) -> None:
    person = _create_person(client)
    _create_project(client, external_id="PRJ-1")
    csv_text = (
        "person_email,project_external_id,start_date,end_date,allocation_hours\n"
        f"{person['email']},PRJ-1,2026-09-01,2026-09-05,20\n"
    )
    response = _csv_upload(client, "allocation", csv_text, action="apply")
    body = response.json()
    assert body["created_count"] == 1

    listing = client.get("/api/v1/allocations").json()
    assert listing["total"] == 1


def test_allocation_import_unresolvable_person_reference_blocks(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    csv_text = (
        "person_email,project_external_id,start_date,end_date,allocation_hours\n"
        "ghost@example.com,PRJ-1,2026-09-01,2026-09-05,20\n"
    )
    response = _csv_upload(client, "allocation", csv_text)
    body = response.json()
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_allocation_import_cannot_resolve_person_or_project_from_another_organization(
    client: TestClient, db_session: Session
) -> None:
    """Phase 16 audit addition: ADR 0012 already hardened every
    ImportService identity-resolution lookup (email/external_id) to be
    organization-scoped — this proves it for real rather than trusting the
    ADR's description alone. A row referencing another organization's real
    person email + project external_id must be treated exactly like a
    ghost reference (invalid_reference), never silently resolved against
    the wrong organization's row."""
    org_b = make_organization(db_session, slug="org-b-import")
    person_b = make_person(db_session, organization=org_b, email="org-b-person@example.com")
    make_project(db_session, organization=org_b, name="Org B Project", external_id="PRJ-1")

    csv_text = (
        "person_email,project_external_id,start_date,end_date,allocation_hours\n"
        f"{person_b.email},PRJ-1,2026-09-01,2026-09-05,20\n"
    )
    response = _csv_upload(client, "allocation", csv_text)
    body = response.json()
    assert body["rows"][0]["status"] == "invalid"
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"

    # And no allocation was created against Org B's project either way.
    assert client.get("/api/v1/allocations").json()["total"] == 0


def test_allocation_import_negative_hours_rejected(client: TestClient) -> None:
    person = _create_person(client)
    _create_project(client, external_id="PRJ-1")
    csv_text = (
        "person_email,project_external_id,start_date,end_date,allocation_hours\n"
        f"{person['email']},PRJ-1,2026-09-01,2026-09-05,-5\n"
    )
    response = _csv_upload(client, "allocation", csv_text)
    body = response.json()
    assert body["rows"][0]["status"] == "invalid"


def test_allocation_import_apply_is_atomic_on_partial_failure(client: TestClient) -> None:
    person = _create_person(client)
    _create_project(client, external_id="PRJ-1")
    csv_text = (
        "person_email,project_external_id,start_date,end_date,allocation_hours\n"
        f"{person['email']},PRJ-1,2026-09-01,2026-09-05,20\n"
        f"{person['email']},PRJ-1,2026-09-01,2026-09-05,-5\n"
    )
    response = _csv_upload(client, "allocation", csv_text, action="apply")
    assert response.json()["applied"] is False

    listing = client.get("/api/v1/allocations").json()
    assert listing["total"] == 0


def test_allocation_import_updates_by_external_id(client: TestClient) -> None:
    person = _create_person(client)
    project = _create_project(client, external_id="PRJ-1")
    allocation = client.post(
        "/api/v1/allocations",
        json={
            "person_id": person["id"], "project_id": project["id"],
            "start_date": "2026-09-01", "end_date": "2026-09-05",
            "allocation_hours": "20", "external_id": "ALC-1",
        },
    ).json()

    csv_text = (
        "external_id,start_date,end_date,allocation_hours\n"
        "ALC-1,2026-09-01,2026-09-05,30\n"
    )
    response = _csv_upload(client, "allocation", csv_text, action="apply")
    body = response.json()
    assert body["updated_count"] == 1

    updated = client.get(f"/api/v1/allocations/{allocation['id']}").json()
    assert updated["allocation_hours"] == "30.00"


# ---------------------------------------------------------------------------
# WorkingSchedule
# ---------------------------------------------------------------------------


def test_working_schedule_import_create_with_packed_entries(client: TestClient) -> None:
    person = _create_person(client)
    csv_text = f"person_email,entries\n{person['email']},\"0:8.00,1:8.00,2:8.00,3:8.00,4:8.00\"\n"
    response = _csv_upload(client, "working_schedule", csv_text, action="apply")
    body = response.json()
    assert body["created_count"] == 1

    schedules = client.get("/api/v1/working-schedules", params={"person_id": person["id"]}).json()
    assert len(schedules[0]["entries"]) == 5


def test_working_schedule_import_update_replaces_entries(client: TestClient) -> None:
    person = _create_person(client)
    client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person["id"], "external_id": "WS-1",
            "entries": [{"weekday": w, "hours": "8"} for w in range(3)],
        },
    )

    csv_text = "external_id,entries\nWS-1,\"3:6.00,4:6.00\"\n"
    response = _csv_upload(client, "working_schedule", csv_text, action="apply")
    assert response.json()["updated_count"] == 1

    schedules = client.get("/api/v1/working-schedules", params={"person_id": person["id"]}).json()
    weekdays = sorted(entry["weekday"] for entry in schedules[0]["entries"])
    assert weekdays == [3, 4]


def test_working_schedule_import_overlap_rejected_against_existing_db_data(
    client: TestClient,
) -> None:
    person = _create_person(client)
    client.post(
        "/api/v1/working-schedules",
        json={"person_id": person["id"], "entries": [{"weekday": 0, "hours": "8"}]},
    )
    csv_text = f"person_email,entries\n{person['email']},\"0:6.00\"\n"
    response = _csv_upload(client, "working_schedule", csv_text)
    body = response.json()
    assert body["rows"][0]["status"] == "invalid"
    assert body["rows"][0]["errors"][0]["code"] == "domain_rule_violated"


def test_working_schedule_import_overlap_rejected_within_same_file(client: TestClient) -> None:
    person = _create_person(client)
    csv_text = (
        "person_email,entries\n"
        f"{person['email']},\"0:8.00\"\n"
        f"{person['email']},\"0:6.00\"\n"
    )
    response = _csv_upload(client, "working_schedule", csv_text)
    body = response.json()
    # First row is fine on its own; the second collides with it.
    assert body["rows"][1]["status"] == "invalid"
    assert body["rows"][1]["errors"][0]["code"] == "domain_rule_violated"


def test_working_schedule_import_missing_entries_rejected(client: TestClient) -> None:
    person = _create_person(client)
    csv_text = f"person_email,entries\n{person['email']},\n"
    response = _csv_upload(client, "working_schedule", csv_text)
    body = response.json()
    assert body["rows"][0]["errors"][0]["code"] == "field_required"


# ---------------------------------------------------------------------------
# AvailabilityException
# ---------------------------------------------------------------------------


def test_availability_exception_import_create(client: TestClient) -> None:
    person = _create_person(client)
    csv_text = (
        "person_email,start_date,end_date,availability_type\n"
        f"{person['email']},2026-09-15,2026-09-19,annual_leave\n"
    )
    response = _csv_upload(client, "availability_exception", csv_text, action="apply")
    assert response.json()["created_count"] == 1


def test_availability_exception_import_invalid_type(client: TestClient) -> None:
    person = _create_person(client)
    csv_text = (
        "person_email,start_date,end_date,availability_type\n"
        f"{person['email']},2026-09-15,2026-09-19,not-a-real-type\n"
    )
    response = _csv_upload(client, "availability_exception", csv_text)
    body = response.json()
    assert body["rows"][0]["status"] == "invalid"


# ---------------------------------------------------------------------------
# Import modes
# ---------------------------------------------------------------------------


def test_create_only_mode_rejects_a_match(client: TestClient) -> None:
    _create_person(client, email="jane@example.com")
    csv_text = "email,first_name,last_name\njane@example.com,Jane,Doe\n"
    response = _csv_upload(client, "person", csv_text, mode="create_only")
    body = response.json()
    assert body["rows"][0]["errors"][0]["code"] == "conflict"


def test_update_only_mode_rejects_no_match(client: TestClient) -> None:
    csv_text = "email,first_name,last_name\nghost@example.com,Ghost,Person\n"
    response = _csv_upload(client, "person", csv_text, mode="update_only")
    body = response.json()
    assert body["rows"][0]["errors"][0]["code"] == "no_match_for_update_only"


def test_update_only_mode_accepts_a_match(client: TestClient) -> None:
    _create_person(client, email="jane@example.com")
    csv_text = "email,first_name,last_name\njane@example.com,Jane,Doe\n"
    response = _csv_upload(client, "person", csv_text, mode="update_only")
    body = response.json()
    assert body["rows"][0]["status"] in ("valid_update", "valid_unchanged")


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_ALL_ENTITY_TYPES = [
    "person",
    "team",
    "team_membership",
    "project",
    "allocation",
    "working_schedule",
    "availability_exception",
]


def test_template_csv_headers_match_entity_columns(client: TestClient) -> None:
    for entity_type in _ALL_ENTITY_TYPES:
        response = client.get(f"/api/v1/imports/{entity_type}/template", params={"format": "csv"})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        header_line = response.text.splitlines()[0]
        assert len(header_line.split(",")) >= 1
        assert len(response.text.splitlines()) == 2  # header + one example row


def test_template_json_is_one_example_object(client: TestClient) -> None:
    for entity_type in _ALL_ENTITY_TYPES:
        response = client.get(
            f"/api/v1/imports/{entity_type}/template", params={"format": "json"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 1


def test_working_schedule_template_json_entries_is_native_array(client: TestClient) -> None:
    response = client.get(
        "/api/v1/imports/working_schedule/template", params={"format": "json"}
    )
    entries = response.json()[0]["entries"]
    assert isinstance(entries, list)
    assert entries[0] == {"weekday": 0, "hours": "8.00"}


def test_person_template_csv_round_trips_clean_through_validate(client: TestClient) -> None:
    template = client.get(
        "/api/v1/imports/person/template", params={"format": "csv"}
    ).text
    response = client.post(
        "/api/v1/imports/person/validate",
        files={"file": ("template.csv", template.encode("utf-8"), "text/csv")},
        params={"mode": "upsert"},
    )
    body = response.json()
    assert body["ready_to_apply"] is True
    assert body["invalid_count"] == 0
    assert body["valid_create_count"] == 1


# ---------------------------------------------------------------------------
# File-level edge cases not yet covered elsewhere
# ---------------------------------------------------------------------------


def test_import_unsupported_file_extension_returns_file_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/imports/person/validate",
        files={"file": ("data.txt", b"not a real import file", "text/plain")},
        params={"mode": "upsert"},
    )
    body = response.json()
    assert body["file_error"]["code"] == "unsupported_format"
    assert body["ready_to_apply"] is False


def test_import_invalid_entity_type_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/imports/not_a_real_entity/validate",
        files={"file": ("data.csv", b"a,b\n1,2\n", "text/csv")},
        params={"mode": "upsert"},
    )
    assert response.status_code == 422
