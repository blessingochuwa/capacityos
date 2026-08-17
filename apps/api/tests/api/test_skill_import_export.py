"""Phase 7 import/export coverage for Skill, PersonSkill, and
ProjectSkillRequirement — registered into the EXISTING Phase 6
import/export system (same /api/v1/imports, /api/v1/exports endpoints,
same validate-then-apply flow). See
docs/adr/0007-phase-7-skills-bottleneck-analysis.md.
"""

import json
from collections.abc import Mapping, Sequence

import httpx
from fastapi.testclient import TestClient


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


def _create_person(client: TestClient, email: str = "jane@example.com") -> dict[str, object]:
    return client.post(
        "/api/v1/people", json={"first_name": "Jane", "last_name": "Doe", "email": email}
    ).json()


def _create_project(client: TestClient, external_id: str = "PRJ-1") -> dict[str, object]:
    return client.post(
        "/api/v1/projects", json={"name": "Website", "external_id": external_id}
    ).json()


def _create_skill(client: TestClient, name: str = "Backend Development") -> dict[str, object]:
    return client.post("/api/v1/skills", json={"name": name}).json()


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------


def test_skill_import_validate_create(client: TestClient) -> None:
    csv_text = "name,description\nBackend Development,Server-side work\n"
    response = _csv_upload(client, "skill", csv_text)
    assert response.status_code == 200
    body = response.json()
    assert body["ready_to_apply"] is True
    assert body["valid_create_count"] == 1


def test_skill_import_apply_creates(client: TestClient) -> None:
    csv_text = "name\nBackend Development\n"
    response = _csv_upload(client, "skill", csv_text, action="apply")
    assert response.json()["created_count"] == 1
    listing = client.get("/api/v1/skills").json()
    assert listing["total"] == 1


def test_skill_import_matches_by_name_on_reimport(client: TestClient) -> None:
    _create_skill(client, "Backend Development")
    csv_text = "name,category\nBackend Development,Engineering\n"
    response = _csv_upload(client, "skill", csv_text, action="apply")
    body = response.json()
    assert body["updated_count"] == 1
    assert client.get("/api/v1/skills").json()["items"][0]["category"] == "Engineering"


def test_skill_import_repeated_identical_file_is_deterministic_unchanged(
    client: TestClient,
) -> None:
    csv_text = "name,description\nBackend Development,Server-side work\n"
    _csv_upload(client, "skill", csv_text, action="apply")
    response = _csv_upload(client, "skill", csv_text, action="apply")
    body = response.json()
    assert body["unchanged_count"] == 1
    assert body["created_count"] == 0


def test_skill_import_can_deactivate_via_is_active_column(client: TestClient) -> None:
    skill = _create_skill(client, "Legacy Tech")
    csv_text = "name,is_active\nLegacy Tech,false\n"
    _csv_upload(client, "skill", csv_text, action="apply")
    assert client.get(f"/api/v1/skills/{skill['id']}").json()["is_active"] is False


# ---------------------------------------------------------------------------
# PersonSkill
# ---------------------------------------------------------------------------


def test_person_skill_import_create_via_email_and_skill_name(client: TestClient) -> None:
    _create_person(client)
    _create_skill(client)
    rows = [{"person_email": "jane@example.com", "skill_name": "Backend Development",
             "proficiency": "advanced"}]
    response = _json_upload(client, "person_skill", rows, action="apply")
    body = response.json()
    assert body["created_count"] == 1


def test_person_skill_import_is_a_noop_when_already_recorded(client: TestClient) -> None:
    person = _create_person(client)
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "advanced"},
    )
    rows = [{"person_email": "jane@example.com", "skill_name": "Backend Development",
             "proficiency": "advanced"}]
    response = _json_upload(client, "person_skill", rows, action="apply")
    assert response.json()["unchanged_count"] == 1


def test_person_skill_import_updates_proficiency(client: TestClient) -> None:
    person = _create_person(client)
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "beginner"},
    )
    rows = [{"person_email": "jane@example.com", "skill_name": "Backend Development",
             "proficiency": "expert"}]
    response = _json_upload(client, "person_skill", rows, action="apply")
    assert response.json()["updated_count"] == 1
    updated = client.get(f"/api/v1/people/{person['id']}/skills").json()
    assert updated[0]["proficiency"] == "expert"


def test_person_skill_import_unresolvable_skill_reference_blocks(client: TestClient) -> None:
    _create_person(client)
    rows = [{"person_email": "jane@example.com", "skill_name": "Nonexistent Skill",
             "proficiency": "advanced"}]
    response = _json_upload(client, "person_skill", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "invalid_reference"


def test_person_skill_import_rejects_inactive_skill_on_create(client: TestClient) -> None:
    _create_person(client)
    skill = _create_skill(client)
    client.delete(f"/api/v1/skills/{skill['id']}")
    rows = [{"person_email": "jane@example.com", "skill_name": "Backend Development",
             "proficiency": "advanced"}]
    response = _json_upload(client, "person_skill", rows)
    body = response.json()
    assert body["ready_to_apply"] is False
    assert body["rows"][0]["errors"][0]["code"] == "domain_rule_violated"


def test_person_skill_import_duplicate_pair_in_file_blocks(client: TestClient) -> None:
    _create_person(client)
    _create_skill(client)
    rows = [
        {"person_email": "jane@example.com", "skill_name": "Backend Development",
         "proficiency": "advanced"},
        {"person_email": "jane@example.com", "skill_name": "Backend Development",
         "proficiency": "expert"},
    ]
    response = _json_upload(client, "person_skill", rows)
    body = response.json()
    assert body["invalid_count"] == 1
    assert body["rows"][1]["errors"][0]["code"] == "duplicate_in_file"


# ---------------------------------------------------------------------------
# ProjectSkillRequirement
# ---------------------------------------------------------------------------


def test_project_skill_requirement_import_create_via_external_id_and_skill_name(
    client: TestClient,
) -> None:
    _create_project(client, external_id="PRJ-1")
    _create_skill(client)
    rows = [{"project_external_id": "PRJ-1", "skill_name": "Backend Development",
             "required_hours": "80"}]
    response = _json_upload(client, "project_skill_requirement", rows, action="apply")
    assert response.json()["created_count"] == 1


def test_project_skill_requirement_import_updates_required_hours(client: TestClient) -> None:
    project = _create_project(client, external_id="PRJ-1")
    skill = _create_skill(client)
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "40"},
    )
    rows = [{"project_external_id": "PRJ-1", "skill_name": "Backend Development",
             "required_hours": "80"}]
    response = _json_upload(client, "project_skill_requirement", rows, action="apply")
    assert response.json()["updated_count"] == 1


def test_project_skill_requirement_import_negative_hours_rejected(client: TestClient) -> None:
    _create_project(client, external_id="PRJ-1")
    _create_skill(client)
    rows = [{"project_external_id": "PRJ-1", "skill_name": "Backend Development",
             "required_hours": "-5"}]
    response = _json_upload(client, "project_skill_requirement", rows)
    assert response.json()["ready_to_apply"] is False


def test_project_skill_requirement_import_apply_is_atomic_on_partial_failure(
    client: TestClient,
) -> None:
    _create_project(client, external_id="PRJ-1")
    _create_skill(client, "Backend Development")
    _create_skill(client, "Design")
    rows = [
        {"project_external_id": "PRJ-1", "skill_name": "Backend Development",
         "required_hours": "40"},
        {"project_external_id": "PRJ-1", "skill_name": "Design", "required_hours": "-5"},
    ]
    response = _json_upload(client, "project_skill_requirement", rows, action="apply")
    assert response.json()["applied"] is False
    listing = client.get(
        f"/api/v1/projects/{_create_project(client, external_id='PRJ-2')['id']}"
        "/skill-requirements"
    ).json()
    assert listing == []


# ---------------------------------------------------------------------------
# create_only / update_only modes (reusing the existing generic policy)
# ---------------------------------------------------------------------------


def test_skill_create_only_mode_rejects_a_match(client: TestClient) -> None:
    _create_skill(client, "Backend Development")
    csv_text = "name\nBackend Development\n"
    response = _csv_upload(client, "skill", csv_text, mode="create_only")
    assert response.json()["rows"][0]["errors"][0]["code"] == "conflict"


def test_person_skill_update_only_mode_rejects_no_match(client: TestClient) -> None:
    _create_person(client)
    _create_skill(client)
    rows = [{"person_email": "jane@example.com", "skill_name": "Backend Development",
             "proficiency": "advanced"}]
    response = _json_upload(client, "person_skill", rows, mode="update_only")
    assert response.json()["rows"][0]["errors"][0]["code"] == "no_match_for_update_only"


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------


def test_skill_template_headers(client: TestClient) -> None:
    response = client.get("/api/v1/imports/skill/template", params={"format": "csv"})
    header = response.text.splitlines()[0]
    assert "name" in header


def test_person_skill_template_round_trips_clean_through_validate(client: TestClient) -> None:
    _create_person(client, "jane.doe@example.com")
    _create_skill(client, "Backend Development")
    template = client.get(
        "/api/v1/imports/person_skill/template", params={"format": "csv"}
    ).text
    response = _csv_upload(client, "person_skill", template)
    assert response.json()["ready_to_apply"] is True


def test_project_skill_requirement_template_round_trips_clean_through_validate(
    client: TestClient,
) -> None:
    _create_project(client, external_id="PRJ-100")
    _create_skill(client, "Backend Development")
    template = client.get(
        "/api/v1/imports/project_skill_requirement/template", params={"format": "csv"}
    ).text
    response = _csv_upload(client, "project_skill_requirement", template)
    assert response.json()["ready_to_apply"] is True


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_skill_export_csv_includes_headers_and_row(client: TestClient) -> None:
    _create_skill(client, "Backend Development")
    response = client.get("/api/v1/exports/skill", params={"format": "csv"})
    assert response.status_code == 200
    lines = response.text.splitlines()
    assert "name" in lines[0]
    assert "Backend Development" in lines[1]


def test_person_skill_export_json_includes_labels(client: TestClient) -> None:
    person = _create_person(client)
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "advanced"},
    )
    response = client.get("/api/v1/exports/person_skill", params={"format": "json"})
    body = response.json()
    assert body[0]["person_email"] == "jane@example.com"
    assert body[0]["skill_name"] == "Backend Development"


def test_project_skill_requirement_export_round_trips_through_reimport(
    client: TestClient,
) -> None:
    project = _create_project(client, external_id="PRJ-1")
    skill = _create_skill(client)
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "80"},
    )
    exported = client.get(
        "/api/v1/exports/project_skill_requirement", params={"format": "csv"}
    ).text
    response = _csv_upload(client, "project_skill_requirement", exported, action="apply")
    body = response.json()
    assert body["applied"] is True
    assert body["unchanged_count"] == 1
