import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.main import app
from tests.factories import make_organization, make_person, make_project, make_team

START = "2026-08-17"  # Monday
END = "2026-08-21"  # Friday — 5 weekdays, matches a Mon-Fri 8h schedule exactly


def _create_person(
    client: TestClient, *, email: str, first_name: str = "Alex"
) -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={"first_name": first_name, "last_name": "Morgan", "email": email},
    ).json()


def _create_project(client: TestClient, *, name: str = "Website Redesign") -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_team(client: TestClient, *, name: str = "Design") -> dict[str, object]:
    return client.post("/api/v1/teams", json={"name": name}).json()


def _add_team_member(client: TestClient, team_id: str, person_id: str) -> None:
    client.post(f"/api/v1/teams/{team_id}/members", json={"person_id": person_id})


def _create_schedule(client: TestClient, person_id: str, *, hours: str = "8") -> dict[str, object]:
    return client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person_id,
            "entries": [{"weekday": w, "hours": hours} for w in range(5)],
        },
    ).json()


def _create_allocation(
    client: TestClient,
    *,
    person_id: str,
    project_id: str,
    start_date: str = START,
    end_date: str = END,
    hours: str,
) -> dict[str, object]:
    return client.post(
        "/api/v1/allocations",
        json={
            "person_id": person_id,
            "project_id": project_id,
            "start_date": start_date,
            "end_date": end_date,
            "allocation_hours": hours,
        },
    ).json()


def _create_scenario(
    client: TestClient, *, name: str = "Test scenario", start: str = START, end: str = END
) -> dict[str, object]:
    return client.post(
        "/api/v1/scenarios",
        json={"name": name, "baseline_start_date": start, "baseline_end_date": end},
    ).json()


def _add_allocation_operation(
    client: TestClient, scenario_id: str, *, person_id: str, project_id: str, hours: str
) -> dict[str, object]:
    return client.post(
        f"/api/v1/scenarios/{scenario_id}/operations",
        json={
            "operation_type": "add_allocation",
            "person_id": person_id,
            "project_id": project_id,
            "hours": hours,
            "start_date": START,
            "end_date": END,
        },
    ).json()


def _adjust_allocation_operation(
    client: TestClient, scenario_id: str, *, allocation_id: str, hours: str
) -> dict[str, object]:
    return client.post(
        f"/api/v1/scenarios/{scenario_id}/operations",
        json={
            "operation_type": "adjust_allocation",
            "allocation_id": allocation_id,
            "hours": hours,
        },
    ).json()


def _person_and_project_over_allocated(
    client: TestClient, *, email: str = "over@example.com", hours: str = "46"
) -> tuple[dict[str, object], dict[str, object]]:
    """One person with a Mon-Fri 8h schedule (40h effective capacity) and an
    allocation of `hours` over [START, END] — over-allocated whenever
    hours > 40."""
    person = _create_person(client, email=email)
    _create_schedule(client, str(person["id"]))
    project = _create_project(client)
    _create_allocation(
        client, person_id=str(person["id"]), project_id=str(project["id"]), hours=hours
    )
    return person, project


# ---------------------------------------------------------------------------
# Person signals
# ---------------------------------------------------------------------------


def test_get_person_signals_returns_over_allocation_signal(client: TestClient) -> None:
    person, _ = _person_and_project_over_allocated(client)
    response = client.get(
        f"/api/v1/insights/people/{person['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "over_allocation"
    assert items[0]["severity"] == "critical"
    assert items[0]["excess_hours"] == "6.00"


def test_get_person_signals_returns_low_capacity_signal_at_threshold_boundary(
    client: TestClient,
) -> None:
    # effective=40h, allocated=35h -> remaining=5h / 5 days = 1.00h/day == default threshold
    person = _create_person(client, email="low@example.com")
    _create_schedule(client, str(person["id"]))
    project = _create_project(client)
    _create_allocation(
        client, person_id=str(person["id"]), project_id=str(project["id"]), hours="35"
    )
    response = client.get(
        f"/api/v1/insights/people/{person['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "low_capacity"
    assert items[0]["severity"] == "warning"
    assert items[0]["threshold_hours_per_day"] == "1.00"


def test_get_person_signals_returns_empty_list_when_healthy(client: TestClient) -> None:
    person = _create_person(client, email="healthy@example.com")
    _create_schedule(client, str(person["id"]))
    project = _create_project(client)
    _create_allocation(
        client, person_id=str(person["id"]), project_id=str(project["id"]), hours="20"
    )
    response = client.get(
        f"/api/v1/insights/people/{person['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    assert response.json()["items"] == []


def test_get_person_signals_404_for_unknown_person(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/insights/people/{uuid.uuid4()}/signals",
        params={"start_date": START, "end_date": END},
    )
    assert response.status_code == 404


def test_get_signals_404_for_person_team_project_in_another_organization(
    client: TestClient, db_session: Session
) -> None:
    """Phase 16 audit addition: InsightService was one of the four highest
    cross-tenant-leak-risk areas ADR 0012 hardened (its shared
    load_people_facts helper gained organization_id, threaded into every
    fact-type query) — this proves a genuinely EXISTING person/team/project
    in another organization is denied exactly like a nonexistent id, not
    merely that a random uuid 404s."""
    org_b = make_organization(db_session, slug="org-b-insights")
    person_b = make_person(db_session, organization=org_b, email="org-b-insights@example.com")
    team_b = make_team(db_session, organization=org_b, name="Org B Team")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")

    params = {"start_date": START, "end_date": END}
    assert (
        client.get(f"/api/v1/insights/people/{person_b.id}/signals", params=params).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/insights/teams/{team_b.id}/signals", params=params).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/insights/projects/{project_b.id}/signals", params=params
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# Team signals
# ---------------------------------------------------------------------------


def test_get_team_signals_includes_member_and_aggregate_signals(client: TestClient) -> None:
    team = _create_team(client)
    person, _project = _person_and_project_over_allocated(client, email="team-a@example.com")
    _add_team_member(client, str(team["id"]), str(person["id"]))

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    entity_types = {(item["type"], item["entity_type"]) for item in items}
    assert ("over_allocation", "team") in entity_types
    assert ("over_allocation", "person") in entity_types


def test_get_team_signals_never_hides_individual_over_allocation_behind_healthy_aggregate(
    client: TestClient,
) -> None:
    team = _create_team(client)
    project = _create_project(client)

    # person_a: 46h allocated, over by 6h
    person_a, _ = _person_and_project_over_allocated(client, email="a@example.com")
    _add_team_member(client, str(team["id"]), str(person_a["id"]))

    person_b = _create_person(client, email="b@example.com")
    _create_schedule(client, str(person_b["id"]))
    _create_allocation(
        client, person_id=str(person_b["id"]), project_id=str(project["id"]), hours="20"
    )
    _add_team_member(client, str(team["id"]), str(person_b["id"]))

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    person_signals = [item for item in items if item["entity_type"] == "person"]
    assert any(
        item["type"] == "over_allocation" and item["entity_id"] == person_a["id"]
        for item in person_signals
    )
    team_signals = [item for item in items if item["entity_type"] == "team"]
    assert not any(signal["type"] == "over_allocation" for signal in team_signals)


def test_get_team_signals_includes_capacity_imbalance_when_spread_exists(
    client: TestClient,
) -> None:
    team = _create_team(client)
    project = _create_project(client)

    person_a, _ = _person_and_project_over_allocated(client, email="high@example.com")  # util 1.15
    _add_team_member(client, str(team["id"]), str(person_a["id"]))

    person_b = _create_person(client, email="low-util@example.com")
    _create_schedule(client, str(person_b["id"]))
    _create_allocation(
        client, person_id=str(person_b["id"]), project_id=str(project["id"]), hours="8"
    )
    _add_team_member(client, str(team["id"]), str(person_b["id"]))

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    imbalance = next(item for item in items if item["type"] == "capacity_imbalance")
    assert imbalance["max_utilization_person_id"] == person_a["id"]
    assert imbalance["min_utilization_person_id"] == person_b["id"]


def test_get_team_signals_omits_imbalance_when_team_has_one_member(client: TestClient) -> None:
    team = _create_team(client)
    person, _ = _person_and_project_over_allocated(client, email="solo@example.com")
    _add_team_member(client, str(team["id"]), str(person["id"]))

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    assert not any(item["type"] == "capacity_imbalance" for item in items)


def test_get_team_signals_404_for_unknown_team(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/insights/teams/{uuid.uuid4()}/signals",
        params={"start_date": START, "end_date": END},
    )
    assert response.status_code == 404


def test_priority_order_is_severity_first(client: TestClient) -> None:
    team = _create_team(client)
    project = _create_project(client)

    person_a, _ = _person_and_project_over_allocated(client, email="crit@example.com")
    _add_team_member(client, str(team["id"]), str(person_a["id"]))

    person_b = _create_person(client, email="info@example.com")
    _create_schedule(client, str(person_b["id"]))
    _create_allocation(
        client, person_id=str(person_b["id"]), project_id=str(project["id"]), hours="8"
    )
    _add_team_member(client, str(team["id"]), str(person_b["id"]))

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    severities = [item["severity"] for item in items]
    assert severities.index("critical") < severities.index("info")


# ---------------------------------------------------------------------------
# Project signals
# ---------------------------------------------------------------------------


def test_get_project_signals_returns_concentration_risk_for_three_plus_contributors(
    client: TestClient,
) -> None:
    project = _create_project(client)
    contributors = [("p1@example.com", "20"), ("p2@example.com", "10"), ("p3@example.com", "5")]
    for email, hours in contributors:
        person = _create_person(client, email=email)
        _create_schedule(client, str(person["id"]))
        _create_allocation(
            client, person_id=str(person["id"]), project_id=str(project["id"]), hours=hours
        )

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    concentration = next(item for item in items if item["type"] == "concentration_risk")
    assert concentration["concentration_ratio"] == "0.8571"


def test_get_project_signals_omits_concentration_for_two_contributors(client: TestClient) -> None:
    project = _create_project(client)
    for email, hours in [("p1@example.com", "20"), ("p2@example.com", "10")]:
        person = _create_person(client, email=email)
        _create_schedule(client, str(person["id"]))
        _create_allocation(
            client, person_id=str(person["id"]), project_id=str(project["id"]), hours=hours
        )

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    assert not any(item["type"] == "concentration_risk" for item in items)


def test_get_project_signals_returns_project_capacity_pressure_critical(client: TestClient) -> None:
    _person, project = _person_and_project_over_allocated(client, email="pressure@example.com")
    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    pressure = next(item for item in items if item["type"] == "project_capacity_pressure")
    assert pressure["severity"] == "critical"


def test_get_project_signals_returns_project_capacity_pressure_warning_at_low_capacity_boundary(
    client: TestClient,
) -> None:
    person = _create_person(client, email="pressure-warn@example.com")
    _create_schedule(client, str(person["id"]))
    project = _create_project(client)
    _create_allocation(
        client, person_id=str(person["id"]), project_id=str(project["id"]), hours="35"
    )
    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    pressure = next(item for item in items if item["type"] == "project_capacity_pressure")
    assert pressure["severity"] == "warning"


def test_get_project_signals_pressure_uses_aggregate_not_summed_member_over_allocation(
    client: TestClient,
) -> None:
    """A is over-allocated by 6h on its own; B has 30h of slack. Naively
    summing each member's own over_allocation would report 6h of pressure,
    but the aggregate (team) formula nets them out to healthy — no pressure
    signal should fire. Mirrors ScenarioCalculationService's own
    aggregate-vs-summed-member-over-allocation distinction."""
    project = _create_project(client)
    person_a = _create_person(client, email="net-a@example.com")
    _create_schedule(client, str(person_a["id"]))
    _create_allocation(
        client, person_id=str(person_a["id"]), project_id=str(project["id"]), hours="46"
    )
    person_b = _create_person(client, email="net-b@example.com")
    _create_schedule(client, str(person_b["id"]))
    _create_allocation(
        client, person_id=str(person_b["id"]), project_id=str(project["id"]), hours="10"
    )

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    items = response.json()["items"]
    assert not any(item["type"] == "project_capacity_pressure" for item in items)


def test_get_project_signals_404_for_unknown_project(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/insights/projects/{uuid.uuid4()}/signals",
        params={"start_date": START, "end_date": END},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Scenario signals
# ---------------------------------------------------------------------------


def test_get_scenario_signals_distinguishes_new_from_existing(client: TestClient) -> None:
    project = _create_project(client)

    # person_existing must be allocated to the SAME project the scenario's
    # operation references — ScenarioCalculationService only computes
    # comparisons for people/projects touched by the scenario (directly, or
    # via full membership of a referenced project); an allocation on an
    # unrelated project is out of scope entirely.
    person_existing = _create_person(client, email="existing@example.com")
    _create_schedule(client, str(person_existing["id"]))
    _create_allocation(
        client, person_id=str(person_existing["id"]), project_id=str(project["id"]), hours="46"
    )

    person_new = _create_person(client, email="new-risk@example.com")
    _create_schedule(client, str(person_new["id"]))
    _create_allocation(
        client, person_id=str(person_new["id"]), project_id=str(project["id"]), hours="20"
    )

    scenario = _create_scenario(client)
    _add_allocation_operation(
        client,
        str(scenario["id"]),
        person_id=str(person_new["id"]),
        project_id=str(project["id"]),
        hours="26",
    )

    response = client.get(f"/api/v1/insights/scenarios/{scenario['id']}/signals")
    items = response.json()["items"]
    by_person = {item["entity_id"]: item for item in items}
    assert by_person[person_existing["id"]]["type"] == "scenario_existing_risk"
    assert by_person[person_existing["id"]]["is_new"] is False
    assert by_person[person_new["id"]]["type"] == "scenario_new_risk"
    assert by_person[person_new["id"]]["is_new"] is True


def test_get_scenario_signals_existing_risk_reports_worsened_trend(client: TestClient) -> None:
    person, _project = _person_and_project_over_allocated(client, email="worsen@example.com")
    allocation = client.get(
        "/api/v1/allocations", params={"person_id": person["id"]}
    ).json()["items"][0]

    scenario = _create_scenario(client)
    _adjust_allocation_operation(
        client, str(scenario["id"]), allocation_id=str(allocation["id"]), hours="50"
    )

    response = client.get(f"/api/v1/insights/scenarios/{scenario['id']}/signals")
    items = response.json()["items"]
    signal = next(item for item in items if item["entity_id"] == person["id"])
    assert signal["trend"] == "worsened"


def test_get_scenario_signals_existing_risk_reports_improved_trend(client: TestClient) -> None:
    person, _project = _person_and_project_over_allocated(client, email="improve@example.com")
    allocation = client.get(
        "/api/v1/allocations", params={"person_id": person["id"]}
    ).json()["items"][0]

    scenario = _create_scenario(client)
    _adjust_allocation_operation(
        client, str(scenario["id"]), allocation_id=str(allocation["id"]), hours="42"
    )

    response = client.get(f"/api/v1/insights/scenarios/{scenario['id']}/signals")
    items = response.json()["items"]
    signal = next(item for item in items if item["entity_id"] == person["id"])
    assert signal["trend"] == "improved"


def test_get_scenario_signals_reuses_comparison_risk_detection(client: TestClient) -> None:
    _person_and_project_over_allocated(client, email="parity@example.com")
    scenario = _create_scenario(client)

    signals_response = client.get(f"/api/v1/insights/scenarios/{scenario['id']}/signals")
    comparison_response = client.get(f"/api/v1/scenarios/{scenario['id']}/comparison")

    signal_person_ids = sorted(item["entity_id"] for item in signals_response.json()["items"])
    risk_person_ids = sorted(risk["person_id"] for risk in comparison_response.json()["risks"])
    assert signal_person_ids == risk_person_ids
    assert len(signals_response.json()["items"]) == len(comparison_response.json()["risks"])


def test_get_scenario_signals_404_for_unknown_scenario(client: TestClient) -> None:
    response = client.get(f"/api/v1/insights/scenarios/{uuid.uuid4()}/signals")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Team summary
# ---------------------------------------------------------------------------


def test_get_team_summary_returns_severity_counts(client: TestClient) -> None:
    team = _create_team(client)
    person, _ = _person_and_project_over_allocated(client, email="summary@example.com")
    _add_team_member(client, str(team["id"]), str(person["id"]))

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/summary",
        params={"start_date": START, "end_date": END},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["signal_counts"]["critical"] >= 1


def test_get_team_summary_includes_scenario_delta_when_scenario_id_given(
    client: TestClient,
) -> None:
    team = _create_team(client)
    person, _project = _person_and_project_over_allocated(client, email="delta@example.com")
    _add_team_member(client, str(team["id"]), str(person["id"]))
    scenario = _create_scenario(client)

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/summary",
        params={"start_date": START, "end_date": END, "scenario_id": scenario["id"]},
    )
    body = response.json()
    assert body["scenario_id"] == scenario["id"]
    assert body["scenario_delta"] is not None


def test_get_team_summary_omits_scenario_delta_when_scenario_id_omitted(
    client: TestClient,
) -> None:
    team = _create_team(client)
    person, _ = _person_and_project_over_allocated(client, email="no-delta@example.com")
    _add_team_member(client, str(team["id"]), str(person["id"]))

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/summary",
        params={"start_date": START, "end_date": END},
    )
    body = response.json()
    assert body["scenario_id"] is None
    assert body["scenario_delta"] is None
    assert body["scenario_new_risk_count"] == 0
    assert body["scenario_existing_risk_count"] == 0


def test_get_team_summary_narrows_projects_with_project_id_filter(client: TestClient) -> None:
    team = _create_team(client)
    person = _create_person(client, email="multi-project@example.com")
    _create_schedule(client, str(person["id"]))
    _add_team_member(client, str(team["id"]), str(person["id"]))

    project_x = _create_project(client, name="Project X")
    project_y = _create_project(client, name="Project Y")
    _create_allocation(
        client, person_id=str(person["id"]), project_id=str(project_x["id"]), hours="20"
    )
    _create_allocation(
        client, person_id=str(person["id"]), project_id=str(project_y["id"]), hours="20"
    )

    response = client.get(
        f"/api/v1/insights/teams/{team['id']}/summary",
        params={"start_date": START, "end_date": END, "project_id": project_x["id"]},
    )
    body = response.json()
    referenced_project_ids = {area["project_id"] for area in body["concentration_areas"]} | {
        p["project_id"] for p in body["projects_under_pressure"]
    }
    assert referenced_project_ids <= {project_x["id"]}


def test_get_team_summary_404_for_unknown_team(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/insights/teams/{uuid.uuid4()}/summary",
        params={"start_date": START, "end_date": END},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Cross-cutting invariants
# ---------------------------------------------------------------------------


def test_signals_are_deterministic_across_repeated_calls(client: TestClient) -> None:
    person, _ = _person_and_project_over_allocated(client, email="deterministic@example.com")
    params = {"start_date": START, "end_date": END}
    first = client.get(f"/api/v1/insights/people/{person['id']}/signals", params=params).json()
    second = client.get(f"/api/v1/insights/people/{person['id']}/signals", params=params).json()
    assert first == second


def test_signal_endpoints_never_mutate_production_data(client: TestClient) -> None:
    person, project = _person_and_project_over_allocated(client, email="readonly@example.com")
    before = client.get("/api/v1/allocations", params={"person_id": person["id"]}).json()

    client.get(
        f"/api/v1/insights/people/{person['id']}/signals",
        params={"start_date": START, "end_date": END},
    )
    client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": START, "end_date": END},
    )

    after = client.get("/api/v1/allocations", params={"person_id": person["id"]}).json()
    assert before == after


def test_low_capacity_threshold_is_configurable(client: TestClient) -> None:
    # Healthy at the default 1.00h/day threshold (remaining 20h / 5 days = 4h/day).
    person = _create_person(client, email="configurable@example.com")
    _create_schedule(client, str(person["id"]))
    project = _create_project(client)
    _create_allocation(
        client, person_id=str(person["id"]), project_id=str(project["id"]), hours="20"
    )
    params = {"start_date": START, "end_date": END}

    baseline = client.get(f"/api/v1/insights/people/{person['id']}/signals", params=params)
    assert baseline.json()["items"] == []

    app.dependency_overrides[get_settings] = lambda: Settings(
        low_capacity_threshold_hours_per_day=Decimal("5.00")
    )
    try:
        widened = client.get(f"/api/v1/insights/people/{person['id']}/signals", params=params)
    finally:
        del app.dependency_overrides[get_settings]

    items = widened.json()["items"]
    assert len(items) == 1
    assert items[0]["type"] == "low_capacity"
    assert items[0]["threshold_hours_per_day"] == "5.00"
