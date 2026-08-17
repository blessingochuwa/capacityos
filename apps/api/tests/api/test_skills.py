import uuid
from decimal import Decimal

from fastapi.testclient import TestClient


def _create_person(client: TestClient, email: str = "alex.morgan@example.com") -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={
            "first_name": "Alex", "last_name": "Morgan", "email": email,
        },
    ).json()


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_skill(client: TestClient, name: str = "Backend Development") -> dict[str, object]:
    return client.post("/api/v1/skills", json={"name": name}).json()


def _give_capacity(client: TestClient, person_id: object, hours_per_day: int = 8) -> None:
    client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person_id,
            "entries": [{"weekday": w, "hours": hours_per_day} for w in range(5)],
        },
    )


# ---------------------------------------------------------------------------
# Skill CRUD
# ---------------------------------------------------------------------------


def test_create_skill(client: TestClient) -> None:
    response = client.post(
        "/api/v1/skills",
        json={"name": "Backend Development", "description": "Server-side work", "category": "Eng"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Backend Development"
    assert body["is_active"] is True
    assert body["person_count"] == 0


def test_create_skill_with_duplicate_name_returns_409(client: TestClient) -> None:
    _create_skill(client, "Backend Development")
    response = client.post("/api/v1/skills", json={"name": "Backend Development"})
    assert response.status_code == 409


def test_list_skills_filters_by_is_active(client: TestClient) -> None:
    active = _create_skill(client, "Backend Development")
    inactive = _create_skill(client, "Legacy Tech")
    client.delete(f"/api/v1/skills/{inactive['id']}")

    response = client.get("/api/v1/skills", params={"is_active": True})
    ids = [item["id"] for item in response.json()["items"]]
    assert active["id"] in ids
    assert inactive["id"] not in ids


def test_get_nonexistent_skill_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/v1/skills/{uuid.uuid4()}").status_code == 404


def test_update_skill(client: TestClient) -> None:
    skill = _create_skill(client)
    response = client.patch(f"/api/v1/skills/{skill['id']}", json={"category": "Engineering"})
    assert response.status_code == 200
    assert response.json()["category"] == "Engineering"


def test_deactivate_skill_is_a_soft_delete(client: TestClient) -> None:
    skill = _create_skill(client)
    assert client.delete(f"/api/v1/skills/{skill['id']}").status_code == 204
    response = client.get(f"/api/v1/skills/{skill['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False


# ---------------------------------------------------------------------------
# PersonSkill
# ---------------------------------------------------------------------------


def test_add_person_skill(client: TestClient) -> None:
    person = _create_person(client)
    skill = _create_skill(client)
    response = client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "advanced", "notes": "5 years"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["proficiency"] == "advanced"
    assert body["person_id"] == person["id"]


def test_add_duplicate_person_skill_returns_409(client: TestClient) -> None:
    person = _create_person(client)
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "advanced"},
    )
    response = client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "expert"},
    )
    assert response.status_code == 409


def test_add_person_skill_for_inactive_skill_returns_422(client: TestClient) -> None:
    person = _create_person(client)
    skill = _create_skill(client)
    client.delete(f"/api/v1/skills/{skill['id']}")
    response = client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "advanced"},
    )
    assert response.status_code == 422


def test_add_person_skill_for_nonexistent_skill_returns_404(client: TestClient) -> None:
    person = _create_person(client)
    response = client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": str(uuid.uuid4()), "proficiency": "advanced"},
    )
    assert response.status_code == 404


def test_list_and_update_and_remove_person_skill(client: TestClient) -> None:
    person = _create_person(client)
    skill = _create_skill(client)
    created = client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "working"},
    ).json()

    listed = client.get(f"/api/v1/people/{person['id']}/skills").json()
    assert len(listed) == 1

    updated = client.patch(
        f"/api/v1/people/{person['id']}/skills/{created['id']}",
        json={"proficiency": "expert"},
    )
    assert updated.status_code == 200
    assert updated.json()["proficiency"] == "expert"

    assert (
        client.delete(f"/api/v1/people/{person['id']}/skills/{created['id']}").status_code == 204
    )
    assert client.get(f"/api/v1/people/{person['id']}/skills").json() == []


def test_person_skill_scoped_to_wrong_person_returns_404(client: TestClient) -> None:
    person_a = _create_person(client, "a@example.com")
    person_b = _create_person(client, "b@example.com")
    skill = _create_skill(client)
    created = client.post(
        f"/api/v1/people/{person_a['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "working"},
    ).json()

    response = client.patch(
        f"/api/v1/people/{person_b['id']}/skills/{created['id']}", json={"proficiency": "expert"}
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# ProjectSkillRequirement
# ---------------------------------------------------------------------------


def test_add_project_skill_requirement(client: TestClient) -> None:
    project = _create_project(client)
    skill = _create_skill(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "80", "minimum_proficiency": "working"},
    )
    assert response.status_code == 201
    assert Decimal(response.json()["required_hours"]) == Decimal("80")


def test_add_duplicate_project_skill_requirement_returns_409(client: TestClient) -> None:
    project = _create_project(client)
    skill = _create_skill(client)
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "80"},
    )
    response = client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "40"},
    )
    assert response.status_code == 409


def test_project_skill_requirement_rejects_non_positive_hours(client: TestClient) -> None:
    project = _create_project(client)
    skill = _create_skill(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "0"},
    )
    assert response.status_code == 422


def test_list_update_remove_project_skill_requirement(client: TestClient) -> None:
    project = _create_project(client)
    skill = _create_skill(client)
    created = client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "40"},
    ).json()

    listed = client.get(f"/api/v1/projects/{project['id']}/skill-requirements").json()
    assert len(listed) == 1

    updated = client.patch(
        f"/api/v1/projects/{project['id']}/skill-requirements/{created['id']}",
        json={"required_hours": "60"},
    )
    assert Decimal(updated.json()["required_hours"]) == Decimal("60")

    assert (
        client.delete(
            f"/api/v1/projects/{project['id']}/skill-requirements/{created['id']}"
        ).status_code
        == 204
    )
    assert client.get(f"/api/v1/projects/{project['id']}/skill-requirements").json() == []


# ---------------------------------------------------------------------------
# Project skill coverage
# ---------------------------------------------------------------------------


def test_project_with_no_requirements_returns_empty_list(client: TestClient) -> None:
    project = _create_project(client)
    response = client.get(
        f"/api/v1/projects/{project['id']}/skill-coverage",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    assert response.status_code == 200
    assert response.json()["requirements"] == []


def test_project_skill_coverage_full(client: TestClient) -> None:
    person = _create_person(client)
    _give_capacity(client, person["id"])
    project = _create_project(client)
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "proficient"},
    )
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "40"},
    )

    response = client.get(
        f"/api/v1/projects/{project['id']}/skill-coverage",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    body = response.json()["requirements"][0]
    assert body["gap_hours"] == "0.00"
    assert len(body["qualified_people"]) == 1
    assert body["qualified_people"][0]["person_id"] == person["id"]


def test_project_skill_coverage_zero_qualified_capacity(client: TestClient) -> None:
    project = _create_project(client)
    skill = _create_skill(client)
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "40"},
    )
    response = client.get(
        f"/api/v1/projects/{project['id']}/skill-coverage",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    body = response.json()["requirements"][0]
    assert body["qualified_available_hours"] == "0.00"
    assert body["gap_hours"] == "40.00"
    assert body["qualified_people"] == []


def test_project_skill_coverage_excludes_underqualified_people(client: TestClient) -> None:
    person = _create_person(client)
    _give_capacity(client, person["id"])
    project = _create_project(client)
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "beginner"},
    )
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "40", "minimum_proficiency": "advanced"},
    )
    response = client.get(
        f"/api/v1/projects/{project['id']}/skill-coverage",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    body = response.json()["requirements"][0]
    assert body["qualified_people"] == []
    assert body["gap_hours"] == "40.00"


# ---------------------------------------------------------------------------
# Team skill capacity
# ---------------------------------------------------------------------------


def test_team_skill_capacity_reflects_members(client: TestClient) -> None:
    person = _create_person(client)
    _give_capacity(client, person["id"])
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "expert"},
    )
    team = client.post("/api/v1/teams", json={"name": "Platform"}).json()
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})

    response = client.get(
        f"/api/v1/teams/{team['id']}/skill-capacity",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["skills"]) == 1
    assert body["skills"][0]["skill_id"] == skill["id"]
    assert body["skills"][0]["qualified_available_hours"] != "0.00"


def test_team_with_no_skilled_members_returns_empty(client: TestClient) -> None:
    team = client.post("/api/v1/teams", json={"name": "Platform"}).json()
    response = client.get(
        f"/api/v1/teams/{team['id']}/skill-capacity",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    assert response.json()["skills"] == []


def test_skill_coverage_for_nonexistent_project_returns_404(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/projects/{uuid.uuid4()}/skill-coverage",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    assert response.status_code == 404
