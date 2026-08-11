import uuid

from fastapi.testclient import TestClient


def _create_person(client: TestClient, email: str = "alex.morgan@example.com") -> dict[str, object]:
    return client.post(
        "/api/v1/people", json={"first_name": "Alex", "last_name": "Morgan", "email": email}
    ).json()


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": name}).json()


def _give_schedule(client: TestClient, person_id: object, hours: int = 8) -> None:
    entries = [{"weekday": weekday, "hours": hours} for weekday in range(5)]
    client.post("/api/v1/working-schedules", json={"person_id": person_id, "entries": entries})


def _create_allocation(
    client: TestClient, person_id: object, project_id: object, start: str, end: str, hours: float
) -> dict[str, object]:
    return client.post(
        "/api/v1/allocations",
        json={
            "person_id": person_id,
            "project_id": project_id,
            "start_date": start,
            "end_date": end,
            "allocation_hours": hours,
        },
    ).json()


# 2026-08-17..21 is a Monday-Friday work week.
WEEK_START = "2026-08-17"
WEEK_END = "2026-08-21"


def test_get_person_capacity_returns_expected_totals(client: TestClient) -> None:
    person = _create_person(client)
    _give_schedule(client, person["id"])
    project = _create_project(client)
    _create_allocation(client, person["id"], project["id"], WEEK_START, WEEK_END, 20)

    response = client.get(
        f"/api/v1/capacity/people/{person['id']}",
        params={"start_date": WEEK_START, "end_date": WEEK_END},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["person_id"] == person["id"]
    assert body["gross_capacity"] == "40.00"
    assert body["effective_capacity"] == "40.00"
    assert body["allocated_hours"] == "20.00"
    assert body["remaining_capacity"] == "20.00"
    assert body["utilization"] == "0.5000"
    assert body["over_allocation"] == "0.00"
    assert len(body["daily_breakdown"]) == 5


def test_get_person_capacity_for_nonexistent_person_returns_404(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/capacity/people/{uuid.uuid4()}",
        params={"start_date": WEEK_START, "end_date": WEEK_END},
    )
    assert response.status_code == 404


def test_get_person_capacity_with_end_before_start_returns_422(client: TestClient) -> None:
    person = _create_person(client)
    response = client.get(
        f"/api/v1/capacity/people/{person['id']}",
        params={"start_date": WEEK_END, "end_date": WEEK_START},
    )
    assert response.status_code == 422


def test_get_person_capacity_with_oversized_range_returns_422(client: TestClient) -> None:
    person = _create_person(client)
    response = client.get(
        f"/api/v1/capacity/people/{person['id']}",
        params={"start_date": "2020-01-01", "end_date": "2026-08-17"},
    )
    assert response.status_code == 422


def test_get_person_capacity_on_full_leave_returns_null_utilization(client: TestClient) -> None:
    person = _create_person(client)
    _give_schedule(client, person["id"])
    client.post(
        "/api/v1/availability-exceptions",
        json={
            "person_id": person["id"],
            "start_date": WEEK_START,
            "end_date": WEEK_END,
            "availability_type": "annual_leave",
        },
    )

    response = client.get(
        f"/api/v1/capacity/people/{person['id']}",
        params={"start_date": WEEK_START, "end_date": WEEK_END},
    )
    body = response.json()
    assert body["effective_capacity"] == "0.00"
    assert body["utilization"] is None


def test_get_team_capacity_is_weighted_across_members(client: TestClient) -> None:
    team = client.post("/api/v1/teams", json={"name": "Creative"}).json()
    project = _create_project(client)

    fully_allocated = _create_person(client, email="fully-allocated@example.com")
    _give_schedule(client, fully_allocated["id"])
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": fully_allocated["id"]})
    _create_allocation(client, fully_allocated["id"], project["id"], WEEK_START, WEEK_END, 40)

    lightly_allocated = _create_person(client, email="lightly-allocated@example.com")
    _give_schedule(client, lightly_allocated["id"], hours=2)  # 10h/week effective
    client.post(f"/api/v1/teams/{team['id']}/members", json={"person_id": lightly_allocated["id"]})
    _create_allocation(client, lightly_allocated["id"], project["id"], WEEK_START, WEEK_END, 5)

    response = client.get(
        f"/api/v1/capacity/teams/{team['id']}",
        params={"start_date": WEEK_START, "end_date": WEEK_END},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["effective_capacity"] == "50.00"
    assert body["allocated_hours"] == "45.00"
    assert body["utilization"] == "0.9000"  # weighted (45/50), not average of 100%/50%
    assert len(body["members"]) == 2


def test_get_team_capacity_for_nonexistent_team_returns_404(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/capacity/teams/{uuid.uuid4()}",
        params={"start_date": WEEK_START, "end_date": WEEK_END},
    )
    assert response.status_code == 404


def test_get_project_demand_breaks_down_by_person_and_day(client: TestClient) -> None:
    project = _create_project(client)
    alice = _create_person(client, email="alice@example.com")
    bob = _create_person(client, email="bob@example.com")
    _create_allocation(client, alice["id"], project["id"], WEEK_START, WEEK_END, 10)
    _create_allocation(client, bob["id"], project["id"], WEEK_START, WEEK_START, 4)

    response = client.get(
        f"/api/v1/capacity/projects/{project['id']}",
        params={"start_date": WEEK_START, "end_date": WEEK_END},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["allocated_hours"] == "14.00"
    assert body["allocated_people"] == 2
    assert len(body["by_person"]) == 2
    assert len(body["daily_breakdown"]) == 5


def test_get_project_demand_for_nonexistent_project_returns_404(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/capacity/projects/{uuid.uuid4()}",
        params={"start_date": WEEK_START, "end_date": WEEK_END},
    )
    assert response.status_code == 404
