import uuid

from fastapi.testclient import TestClient


def _create_person(
    client: TestClient, *, email: str = "alex.morgan@example.com"
) -> dict[str, object]:
    return client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": email},
    ).json()


def _create_project(client: TestClient, *, name: str = "Website Redesign") -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_schedule(client: TestClient, person_id: str) -> dict[str, object]:
    return client.post(
        "/api/v1/working-schedules",
        json={
            "person_id": person_id,
            "entries": [{"weekday": w, "hours": "8"} for w in range(5)],
        },
    ).json()


def _create_allocation(
    client: TestClient,
    *,
    person_id: str,
    project_id: str,
    start_date: str = "2026-09-01",
    end_date: str = "2026-09-05",
    hours: str = "20",
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
    client: TestClient,
    *,
    name: str = "Test scenario",
    start: str = "2026-09-01",
    end: str = "2026-09-05",
) -> dict[str, object]:
    return client.post(
        "/api/v1/scenarios",
        json={"name": name, "baseline_start_date": start, "baseline_end_date": end},
    ).json()


def _setup_baseline(
    client: TestClient,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """One person with a Mon-Fri 8h schedule, one project, one 20h
    allocation over [2026-09-01, 2026-09-05] (a full working week)."""
    person = _create_person(client)
    _create_schedule(client, str(person["id"]))
    project = _create_project(client)
    allocation = _create_allocation(
        client, person_id=str(person["id"]), project_id=str(project["id"])
    )
    return person, project, allocation


# ---------------------------------------------------------------------------
# Scenario CRUD
# ---------------------------------------------------------------------------


def test_create_scenario_returns_201(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Launch earlier",
            "description": "Move the launch date up by two weeks",
            "baseline_start_date": "2026-09-01",
            "baseline_end_date": "2026-09-30",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Launch earlier"
    assert body["status"] == "draft"


def test_create_scenario_invalid_date_range_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/scenarios",
        json={
            "name": "Bad range",
            "baseline_start_date": "2026-09-30",
            "baseline_end_date": "2026-09-01",
        },
    )
    assert response.status_code == 422


def test_get_scenario_404_for_missing(client: TestClient) -> None:
    assert client.get(f"/api/v1/scenarios/{uuid.uuid4()}").status_code == 404


def test_list_scenarios_filters_by_status(client: TestClient) -> None:
    scenario = _create_scenario(client)
    client.patch(f"/api/v1/scenarios/{scenario['id']}", json={"status": "archived"})
    _create_scenario(client, name="Still a draft")

    response = client.get("/api/v1/scenarios", params={"status": "archived"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == scenario["id"]


def test_update_scenario_name_and_status(client: TestClient) -> None:
    scenario = _create_scenario(client)
    response = client.patch(
        f"/api/v1/scenarios/{scenario['id']}", json={"name": "Renamed", "status": "active"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["status"] == "active"


def test_delete_scenario(client: TestClient) -> None:
    scenario = _create_scenario(client)
    assert client.delete(f"/api/v1/scenarios/{scenario['id']}").status_code == 204
    assert client.get(f"/api/v1/scenarios/{scenario['id']}").status_code == 404


def test_delete_scenario_never_touches_baseline_data(client: TestClient) -> None:
    person, project, allocation = _setup_baseline(client)
    scenario = _create_scenario(client)
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "remove_allocation",
            "allocation_id": allocation["id"],
        },
    )

    assert client.delete(f"/api/v1/scenarios/{scenario['id']}").status_code == 204

    assert client.get(f"/api/v1/people/{person['id']}").status_code == 200
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 200
    assert client.get(f"/api/v1/allocations/{allocation['id']}").status_code == 200


# ---------------------------------------------------------------------------
# Scenario operations — validation
# ---------------------------------------------------------------------------


def test_create_operation_for_missing_scenario_returns_404(client: TestClient) -> None:
    person, project, _ = _setup_baseline(client)
    response = client.post(
        f"/api/v1/scenarios/{uuid.uuid4()}/operations",
        json={
            "operation_type": "add_allocation",
            "person_id": person["id"],
            "project_id": project["id"],
            "hours": "10",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
    )
    assert response.status_code == 404


def test_add_allocation_for_nonexistent_person_returns_404(client: TestClient) -> None:
    _, project, _ = _setup_baseline(client)
    scenario = _create_scenario(client)
    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "add_allocation",
            "person_id": str(uuid.uuid4()),
            "project_id": project["id"],
            "hours": "10",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
    )
    assert response.status_code == 404


def test_add_allocation_negative_hours_returns_422(client: TestClient) -> None:
    person, project, _ = _setup_baseline(client)
    scenario = _create_scenario(client)
    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "add_allocation",
            "person_id": person["id"],
            "project_id": project["id"],
            "hours": "-5",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
    )
    assert response.status_code == 422


def test_adjust_allocation_for_nonexistent_allocation_returns_404(client: TestClient) -> None:
    scenario = _create_scenario(client)
    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "adjust_allocation",
            "allocation_id": str(uuid.uuid4()),
            "hours": "10",
        },
    )
    assert response.status_code == 404


def test_adjust_allocation_with_nothing_set_returns_422(client: TestClient) -> None:
    _, _, allocation = _setup_baseline(client)
    scenario = _create_scenario(client)
    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={"operation_type": "adjust_allocation", "allocation_id": allocation["id"]},
    )
    assert response.status_code == 422


def test_move_allocation_exceeding_available_hours_returns_422(client: TestClient) -> None:
    _, _, allocation = _setup_baseline(client)
    other_person = _create_person(client, email="sam.ade@example.com")
    scenario = _create_scenario(client)
    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "move_allocation",
            "allocation_id": allocation["id"],
            "to_person_id": other_person["id"],
            "hours": "999",
        },
    )
    assert response.status_code == 422


def test_add_hypothetical_resource_then_allocate_to_it(client: TestClient) -> None:
    _, project, _ = _setup_baseline(client)
    scenario = _create_scenario(client)
    hypothetical = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "add_hypothetical_resource",
            "label": "Senior Designer",
            "hours_per_week": "40",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
    ).json()

    response = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "add_allocation",
            "person_id": hypothetical["id"],
            "project_id": project["id"],
            "hours": "20",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
    )
    assert response.status_code == 201


def test_update_operation_changing_type_returns_422(client: TestClient) -> None:
    _, _, allocation = _setup_baseline(client)
    scenario = _create_scenario(client)
    operation = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "adjust_allocation",
            "allocation_id": allocation["id"],
            "hours": "25",
        },
    ).json()

    response = client.patch(
        f"/api/v1/scenarios/{scenario['id']}/operations/{operation['id']}",
        json={"operation_type": "remove_allocation", "allocation_id": allocation["id"]},
    )
    assert response.status_code == 422


def test_update_operation_same_type_succeeds(client: TestClient) -> None:
    _, _, allocation = _setup_baseline(client)
    scenario = _create_scenario(client)
    operation = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "adjust_allocation",
            "allocation_id": allocation["id"],
            "hours": "25",
        },
    ).json()

    response = client.patch(
        f"/api/v1/scenarios/{scenario['id']}/operations/{operation['id']}",
        json={
            "operation_type": "adjust_allocation",
            "allocation_id": allocation["id"],
            "hours": "35",
        },
    )
    assert response.status_code == 200
    assert response.json()["payload"]["hours"] == "35"


def test_delete_operation(client: TestClient) -> None:
    _, _, allocation = _setup_baseline(client)
    scenario = _create_scenario(client)
    operation = client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={"operation_type": "remove_allocation", "allocation_id": allocation["id"]},
    ).json()

    assert (
        client.delete(f"/api/v1/scenarios/{scenario['id']}/operations/{operation['id']}").status_code
        == 204
    )
    listed = client.get(f"/api/v1/scenarios/{scenario['id']}/operations").json()
    assert listed["total"] == 0


def test_list_operations(client: TestClient) -> None:
    person, project, allocation = _setup_baseline(client)
    scenario = _create_scenario(client)
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "add_allocation",
            "person_id": person["id"],
            "project_id": project["id"],
            "hours": "5",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
    )
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={"operation_type": "remove_allocation", "allocation_id": allocation["id"]},
    )

    response = client.get(f"/api/v1/scenarios/{scenario['id']}/operations")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["sequence"] for item in body["items"]] == [0, 1]


# ---------------------------------------------------------------------------
# Calculation / results / comparison
# ---------------------------------------------------------------------------


def test_calculate_and_comparison_reflect_scenario_changes(client: TestClient) -> None:
    person, project, _ = _setup_baseline(client)
    other_person = _create_person(client, email="sam.ade@example.com")
    _create_schedule(client, str(other_person["id"]))
    scenario = _create_scenario(client)

    client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "add_allocation",
            "person_id": other_person["id"],
            "project_id": project["id"],
            "hours": "48",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
    )

    calc_response = client.post(f"/api/v1/scenarios/{scenario['id']}/calculate")
    assert calc_response.status_code == 200
    results = calc_response.json()
    assert results["baseline"]["aggregate"]["allocated_hours"] == "20.00"
    assert results["scenario_state"]["aggregate"]["allocated_hours"] == "68.00"

    comparison_response = client.get(f"/api/v1/scenarios/{scenario['id']}/comparison")
    assert comparison_response.status_code == 200
    comparison = comparison_response.json()
    assert comparison["aggregate"]["over_allocation"]["baseline"] == "0.00"
    assert comparison["aggregate"]["over_allocation"]["scenario"] != "0.00"

    new_risks = [r for r in comparison["risks"] if r["is_new"]]
    assert any(r["person_id"] == other_person["id"] for r in new_risks)
    assert any(r["type"] == "over_allocation" for r in new_risks)

    assert set(comparison["impact"]["affected_people"]) == {person["id"], other_person["id"]}
    assert comparison["impact"]["affected_projects"] == [project["id"]]


def test_results_and_comparison_404_for_missing_scenario(client: TestClient) -> None:
    missing_id = uuid.uuid4()
    assert client.get(f"/api/v1/scenarios/{missing_id}/results").status_code == 404
    assert client.get(f"/api/v1/scenarios/{missing_id}/comparison").status_code == 404
    assert client.post(f"/api/v1/scenarios/{missing_id}/calculate").status_code == 404


def test_shift_project_moves_allocation_dates(client: TestClient) -> None:
    person, project, _ = _setup_baseline(client)
    scenario = _create_scenario(client, start="2026-08-25", end="2026-09-05")
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={"operation_type": "shift_project", "project_id": project["id"], "day_offset": -7},
    )

    results = client.post(f"/api/v1/scenarios/{scenario['id']}/calculate").json()
    scenario_person = next(
        p for p in results["scenario_state"]["people"] if p["person_id"] == person["id"]
    )
    # Allocation shifted a week earlier — still fully inside the widened
    # baseline range, so allocated_hours is unchanged, but this confirms
    # the operation was applied without error and the person is included.
    assert scenario_person["allocated_hours"] == "20.00"


def test_availability_override_creates_over_allocation_risk(client: TestClient) -> None:
    person, _, _ = _setup_baseline(client)
    scenario = _create_scenario(client)
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "availability_override",
            "person_id": person["id"],
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
            "hours": None,
        },
    )

    comparison = client.get(f"/api/v1/scenarios/{scenario['id']}/comparison").json()
    person_comparison = next(p for p in comparison["people"] if p["person_id"] == person["id"])
    assert person_comparison["baseline"]["over_allocation"] == "0.00"
    assert person_comparison["scenario"]["over_allocation"] == "20.00"
    assert person_comparison["newly_over_allocated"] is True


# ---------------------------------------------------------------------------
# Critical regression: scenario calculation must never mutate baseline data
# ---------------------------------------------------------------------------


def test_calculating_scenario_never_mutates_baseline_data(client: TestClient) -> None:
    person, project, allocation = _setup_baseline(client)
    other_person = _create_person(client, email="sam.ade@example.com")
    _create_schedule(client, str(other_person["id"]))

    baseline_allocation = client.get(f"/api/v1/allocations/{allocation['id']}").json()
    baseline_capacity = client.get(
        f"/api/v1/capacity/people/{person['id']}",
        params={"start_date": "2026-09-01", "end_date": "2026-09-05"},
    ).json()
    baseline_allocations_page = client.get("/api/v1/allocations").json()

    scenario = _create_scenario(client)
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "move_allocation",
            "allocation_id": allocation["id"],
            "to_person_id": other_person["id"],
            "hours": "8",
        },
    )
    client.post(
        f"/api/v1/scenarios/{scenario['id']}/operations",
        json={
            "operation_type": "add_allocation",
            "person_id": other_person["id"],
            "project_id": project["id"],
            "hours": "15",
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
    )

    # Calculate multiple times, and read results/comparison, to make sure
    # NONE of these read-shaped operations write to production tables.
    for _ in range(2):
        assert client.post(f"/api/v1/scenarios/{scenario['id']}/calculate").status_code == 200
        assert client.get(f"/api/v1/scenarios/{scenario['id']}/results").status_code == 200
        assert client.get(f"/api/v1/scenarios/{scenario['id']}/comparison").status_code == 200

    assert client.get(f"/api/v1/allocations/{allocation['id']}").json() == baseline_allocation
    assert (
        client.get(
            f"/api/v1/capacity/people/{person['id']}",
            params={"start_date": "2026-09-01", "end_date": "2026-09-05"},
        ).json()
        == baseline_capacity
    )
    assert client.get("/api/v1/allocations").json() == baseline_allocations_page
