"""Phase 13 risk_high_exposure/risk_review_overdue signals, surfaced through
the EXISTING Phase 5 insights endpoint (no separate route — mirrors Phase
7's skill signals, see tests/api/test_skill_bottleneck_signals.py and
docs/adr/0013-phase-13-risk-management.md)."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


def _create_project(client: TestClient, name: str = "Website Redesign") -> dict[str, object]:
    return client.post("/api/v1/projects", json={"name": name}).json()


def _create_risk(client: TestClient, project_id: object, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"description": "Vendor delay"} | overrides
    return client.post(f"/api/v1/projects/{project_id}/risks", json=payload).json()


def test_project_with_no_risks_has_no_risk_signals(client: TestClient) -> None:
    project = _create_project(client)
    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signal_types = {s["type"] for s in response.json()["items"]}
    assert "risk_high_exposure" not in signal_types
    assert "risk_review_overdue" not in signal_types


def test_high_exposure_open_risk_signals_critical(client: TestClient) -> None:
    project = _create_project(client)
    risk = _create_risk(client, project["id"], probability="high", impact="high")

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signals = [s for s in response.json()["items"] if s["type"] == "risk_high_exposure"]
    assert len(signals) == 1
    assert signals[0]["severity"] == "critical"
    assert signals[0]["risk_id"] == risk["id"]
    assert signals[0]["risk_exposure"] == "high"


def test_high_exposure_mitigating_risk_signals_warning(client: TestClient) -> None:
    project = _create_project(client)
    _create_risk(client, project["id"], probability="high", impact="high", status="mitigating")

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signals = [s for s in response.json()["items"] if s["type"] == "risk_high_exposure"]
    assert len(signals) == 1
    assert signals[0]["severity"] == "warning"


def test_closed_high_exposure_risk_never_signals(client: TestClient) -> None:
    project = _create_project(client)
    _create_risk(client, project["id"], probability="high", impact="high", status="closed")

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signal_types = {s["type"] for s in response.json()["items"]}
    assert "risk_high_exposure" not in signal_types


def test_overdue_review_signals_warning(client: TestClient) -> None:
    project = _create_project(client)
    risk = _create_risk(
        client,
        project["id"],
        probability="low",
        impact="low",
        review_date=YESTERDAY.isoformat(),
    )

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signals = [s for s in response.json()["items"] if s["type"] == "risk_review_overdue"]
    assert len(signals) == 1
    assert signals[0]["severity"] == "warning"
    assert signals[0]["risk_id"] == risk["id"]


def test_review_due_today_is_not_overdue(client: TestClient) -> None:
    project = _create_project(client)
    _create_risk(
        client, project["id"], probability="low", impact="low", review_date=TODAY.isoformat()
    )

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signal_types = {s["type"] for s in response.json()["items"]}
    assert "risk_review_overdue" not in signal_types


def test_future_review_date_does_not_signal(client: TestClient) -> None:
    project = _create_project(client)
    _create_risk(
        client, project["id"], probability="low", impact="low", review_date=TOMORROW.isoformat()
    )

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signal_types = {s["type"] for s in response.json()["items"]}
    assert "risk_review_overdue" not in signal_types


def test_high_exposure_takes_priority_over_overdue_review(client: TestClient) -> None:
    project = _create_project(client)
    _create_risk(
        client,
        project["id"],
        probability="high",
        impact="high",
        review_date=YESTERDAY.isoformat(),
    )

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signal_types = [s["type"] for s in response.json()["items"]]
    assert signal_types.count("risk_high_exposure") == 1
    assert "risk_review_overdue" not in signal_types


def test_risk_signal_includes_owner_label(client: TestClient) -> None:
    project = _create_project(client)
    person = client.post(
        "/api/v1/people",
        json={"first_name": "Alex", "last_name": "Morgan", "email": "alex@example.com"},
    ).json()
    _create_risk(
        client, project["id"], probability="high", impact="high", owner_person_id=person["id"]
    )

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signals = [s for s in response.json()["items"] if s["type"] == "risk_high_exposure"]
    assert signals[0]["risk_owner_label"] == "Alex Morgan"


def test_unassigned_risk_signal_reports_unassigned_owner(client: TestClient) -> None:
    project = _create_project(client)
    _create_risk(client, project["id"], probability="high", impact="high")

    response = client.get(
        f"/api/v1/insights/projects/{project['id']}/signals",
        params={"start_date": "2026-09-01", "end_date": "2026-09-30"},
    )
    signals = [s for s in response.json()["items"] if s["type"] == "risk_high_exposure"]
    assert signals[0]["risk_owner_label"] == "Unassigned"
