"""Phase 7 skill_gap/single_skill_holder/skill_concentration signals,
surfaced through the EXISTING Phase 5 insights endpoints (no separate
/bottlenecks/ API — see docs/adr/0007-phase-7-skills-bottleneck-analysis.md).
"""

from fastapi.testclient import TestClient


def _create_person(client: TestClient, email: str) -> dict[str, object]:
    return client.post(
        "/api/v1/people", json={"first_name": "Alex", "last_name": "Morgan", "email": email}
    ).json()


def _give_capacity(client: TestClient, person_id: object, hours_per_day: int = 8) -> None:
    client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person_id,
            "entries": [{"weekday": w, "hours": hours_per_day} for w in range(5)],
        },
    )


def _create_skill(client: TestClient, name: str = "Backend Development") -> dict[str, object]:
    return client.post("/api/v1/skills", json={"name": name}).json()


def test_project_with_no_skill_requirements_has_no_skill_signals(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Website"}).json()
    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signal_types = {s["type"] for s in response.json()["items"]}
    assert "skill_gap" not in signal_types


def test_skill_gap_signal_when_no_qualified_capacity(client: TestClient) -> None:
    project = client.post("/api/v1/projects", json={"name": "Website"}).json()
    skill = _create_skill(client)
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "40"},
    )
    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signals = response.json()["items"]
    gap_signals = [s for s in signals if s["type"] == "skill_gap"]
    assert len(gap_signals) == 1
    assert gap_signals[0]["severity"] == "critical"
    assert gap_signals[0]["skill_gap_hours"] == "40.00"
    # Regression: skill_id/skill_label must identify which skill is short —
    # caught via live browser/API verification, see docs/adr/0007.
    assert gap_signals[0]["skill_id"] == skill["id"]
    assert gap_signals[0]["skill_label"] == skill["name"]


def test_skill_gap_signal_is_warning_when_partially_covered(client: TestClient) -> None:
    person = _create_person(client, "jane@example.com")
    _give_capacity(client, person["id"])
    project = client.post("/api/v1/projects", json={"name": "Website"}).json()
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "proficient"},
    )
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "1000"},
    )
    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    gap_signals = [s for s in response.json()["items"] if s["type"] == "skill_gap"]
    assert len(gap_signals) == 1
    assert gap_signals[0]["severity"] == "warning"


def test_no_skill_gap_signal_when_fully_covered(client: TestClient) -> None:
    person = _create_person(client, "jane@example.com")
    _give_capacity(client, person["id"])
    project = client.post("/api/v1/projects", json={"name": "Website"}).json()
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "proficient"},
    )
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "10"},
    )
    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    gap_signals = [s for s in response.json()["items"] if s["type"] == "skill_gap"]
    assert gap_signals == []


def test_single_skill_holder_signal_on_project(client: TestClient) -> None:
    person = _create_person(client, "jane@example.com")
    _give_capacity(client, person["id"])
    project = client.post("/api/v1/projects", json={"name": "Website"}).json()
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "advanced"},
    )
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "10"},
    )
    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signals = [s for s in response.json()["items"] if s["type"] == "single_skill_holder"]
    assert len(signals) == 1
    assert signals[0]["severity"] == "warning"
    assert signals[0]["skill_holder_ids"] == [person["id"]]


def test_skill_concentration_signal_with_two_holders(client: TestClient) -> None:
    person_a = _create_person(client, "a@example.com")
    person_b = _create_person(client, "b@example.com")
    _give_capacity(client, person_a["id"])
    _give_capacity(client, person_b["id"])
    project = client.post("/api/v1/projects", json={"name": "Website"}).json()
    skill = _create_skill(client)
    for person in (person_a, person_b):
        client.post(
            f"/api/v1/people/{person['id']}/skills",
            json={"skill_id": skill["id"], "proficiency": "advanced"},
        )
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "10"},
    )
    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signal_types = [s["type"] for s in response.json()["items"]]
    assert "skill_concentration" in signal_types
    assert "single_skill_holder" not in signal_types


def test_team_skill_holder_signal(client: TestClient) -> None:
    person = _create_person(client, "jane@example.com")
    _give_capacity(client, person["id"])
    skill = _create_skill(client)
    client.post(
        f"/api/v1/people/{person['id']}/skills",
        json={"skill_id": skill["id"], "proficiency": "expert"},
    )
    team = client.post("/api/v1/teams", json={"name": "Platform"}).json()
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": person["id"]})

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signal_types = [s["type"] for s in response.json()["items"]]
    assert "single_skill_holder" in signal_types


def test_inactive_skill_never_produces_a_skill_gap_signal(client: TestClient) -> None:
    """A ProjectSkillRequirement row referencing a since-deactivated skill
    must not surface as an active bottleneck — CLAUDE.md invariant."""
    person = _create_person(client, "jane@example.com")
    _give_capacity(client, person["id"])
    project = client.post("/api/v1/projects", json={"name": "Website"}).json()
    skill = _create_skill(client)
    client.post(
        f"/api/v1/projects/{project['id']}/skill-requirements",
        json={"skill_id": skill["id"], "required_hours": "40"},
    )
    client.delete(f"/api/v1/skills/{skill['id']}")

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signal_types = {s["type"] for s in response.json()["items"]}
    assert "skill_gap" not in signal_types
