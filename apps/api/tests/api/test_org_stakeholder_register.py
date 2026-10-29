"""Phase 48 — the org-wide Stakeholder register (GET /api/v1/stakeholders):
every Stakeholder across every Project in the caller's active
organization, with the same multi-tenancy IDOR discipline the Phase 47
Risk register already proves (tests/api/test_org_risk_register.py)."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import (
    StakeholderDecisionAuthority,
    StakeholderInfluence,
    StakeholderInterest,
    UserRole,
)
from app.models.organization import Organization
from app.models.project import Project
from app.models.stakeholder import Stakeholder
from tests.factories import make_organization, make_project, make_stakeholder

URL = "/api/v1/stakeholders"


def _org(client: TestClient) -> Organization:
    return client.organization  # type: ignore[attr-defined,no-any-return]


def _project(db_session: Session, client: TestClient, name: str = "Website Redesign") -> Project:
    return make_project(db_session, organization=_org(client), name=name)


def _stakeholder(
    db_session: Session, client: TestClient, project: Project, **overrides: object
) -> Stakeholder:
    return make_stakeholder(
        db_session,
        organization=_org(client),
        project=project,
        **overrides,  # type: ignore[arg-type]
    )


def _ids(body: dict[str, object]) -> list[str]:
    return [item["id"] for item in body["items"]]  # type: ignore[union-attr,index]


# ---------------------------------------------------------------------------
# Cross-project aggregation
# ---------------------------------------------------------------------------


def test_lists_stakeholders_across_every_project(
    client: TestClient, db_session: Session
) -> None:
    project_a = _project(db_session, client, "Project A")
    project_b = _project(db_session, client, "Project B")
    on_a = _stakeholder(db_session, client, project_a, name="Ada")
    on_b = _stakeholder(db_session, client, project_b, name="Bo")

    response = client.get(URL)
    assert response.status_code == 200
    body = response.json()
    assert set(_ids(body)) == {str(on_a.id), str(on_b.id)}
    assert body["total"] == 2
    project_ids = {item["project_id"] for item in body["items"]}
    assert project_ids == {str(project_a.id), str(project_b.id)}


def test_empty_organization_returns_empty_page_not_an_error(client: TestClient) -> None:
    response = client.get(URL)
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_response_exposes_only_the_established_stakeholder_fields(
    client: TestClient, db_session: Session
) -> None:
    """The register reuses StakeholderRead verbatim — it must never grow a
    field (a derived score, a joined project name) beyond that schema."""
    _stakeholder(db_session, client, _project(db_session, client))

    item = client.get(URL).json()["items"][0]
    assert set(item.keys()) == {
        "id",
        "project_id",
        "name",
        "person_id",
        "role",
        "influence",
        "interest",
        "decision_authority",
        "communication_needs",
        "created_at",
        "updated_at",
    }


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_filters_by_project(client: TestClient, db_session: Session) -> None:
    project_a = _project(db_session, client, "Project A")
    project_b = _project(db_session, client, "Project B")
    on_a = _stakeholder(db_session, client, project_a)
    _stakeholder(db_session, client, project_b)

    body = client.get(URL, params={"project_id": str(project_a.id)}).json()
    assert _ids(body) == [str(on_a.id)]
    assert body["total"] == 1


@pytest.mark.parametrize(
    ("param", "field", "match", "other"),
    [
        ("influence", "influence", StakeholderInfluence.HIGH, StakeholderInfluence.LOW),
        ("interest", "interest", StakeholderInterest.HIGH, StakeholderInterest.LOW),
        (
            "decision_authority",
            "decision_authority",
            StakeholderDecisionAuthority.DECISION_MAKER,
            StakeholderDecisionAuthority.INFORMED,
        ),
    ],
)
def test_filters_by_each_enum_field(
    client: TestClient,
    db_session: Session,
    param: str,
    field: str,
    match: str,
    other: str,
) -> None:
    project = _project(db_session, client)
    matching = _stakeholder(db_session, client, project, name="Match", **{field: match})
    _stakeholder(db_session, client, project, name="Other", **{field: other})

    body = client.get(URL, params={param: str(match)}).json()
    assert _ids(body) == [str(matching.id)]
    assert body["total"] == 1
    assert all(item[field] == str(match) for item in body["items"])


def test_combines_every_filter(client: TestClient, db_session: Session) -> None:
    project_a = _project(db_session, client, "Project A")
    project_b = _project(db_session, client, "Project B")
    full = {
        "influence": StakeholderInfluence.HIGH,
        "interest": StakeholderInterest.HIGH,
        "decision_authority": StakeholderDecisionAuthority.DECISION_MAKER,
    }
    match = _stakeholder(db_session, client, project_a, name="Match", **full)
    # Each decoy differs from the match in exactly one dimension.
    _stakeholder(db_session, client, project_b, name="Wrong project", **full)
    _stakeholder(
        db_session, client, project_a, name="Wrong influence",
        **{**full, "influence": StakeholderInfluence.LOW},
    )
    _stakeholder(
        db_session, client, project_a, name="Wrong interest",
        **{**full, "interest": StakeholderInterest.MEDIUM},
    )
    _stakeholder(
        db_session, client, project_a, name="Wrong authority",
        **{**full, "decision_authority": StakeholderDecisionAuthority.ADVISOR},
    )

    body = client.get(
        URL,
        params={
            "project_id": str(project_a.id),
            "influence": "high",
            "interest": "high",
            "decision_authority": "decision_maker",
        },
    ).json()
    assert _ids(body) == [str(match.id)]
    assert body["total"] == 1


def test_filter_with_no_match_returns_empty_not_an_error(
    client: TestClient, db_session: Session
) -> None:
    _stakeholder(
        db_session, client, _project(db_session, client), influence=StakeholderInfluence.LOW
    )

    response = client.get(URL, params={"influence": "high"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


# ---------------------------------------------------------------------------
# Pagination, totals, ordering
# ---------------------------------------------------------------------------


def test_pagination_boundaries_cover_every_row_exactly_once(
    client: TestClient, db_session: Session
) -> None:
    project = _project(db_session, client)
    created = [_stakeholder(db_session, client, project, name=f"S{i}") for i in range(5)]

    pages = [client.get(URL, params={"limit": 2, "offset": o}).json() for o in (0, 2, 4)]
    assert [len(page["items"]) for page in pages] == [2, 2, 1]
    assert all(page["total"] == 5 for page in pages)
    walked = [i for page in pages for i in _ids(page)]
    assert walked == [str(s.id) for s in created]

    past_end = client.get(URL, params={"limit": 2, "offset": 5}).json()
    assert past_end == {"items": [], "total": 5}


def test_total_counts_the_full_filtered_set_not_the_page(
    client: TestClient, db_session: Session
) -> None:
    project = _project(db_session, client)
    for _ in range(3):
        _stakeholder(db_session, client, project, influence=StakeholderInfluence.HIGH)
    for _ in range(4):
        _stakeholder(db_session, client, project, influence=StakeholderInfluence.LOW)

    body = client.get(URL, params={"influence": "high", "limit": 2}).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    second = client.get(URL, params={"influence": "high", "limit": 2, "offset": 2}).json()
    assert second["total"] == 3
    assert len(second["items"]) == 1


def test_ordering_is_deterministic_across_pages_even_when_created_at_ties(
    client: TestClient, db_session: Session
) -> None:
    """Every page is its own SQL query — without the id tie-breaker, rows
    sharing a created_at could legally come back in a different order on
    each query, duplicating some rows across pages and skipping others."""
    project = _project(db_session, client)
    tied_at = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [_stakeholder(db_session, client, project, name=f"T{i}") for i in range(6)]
    for row in rows:
        row.created_at = tied_at
    db_session.flush()

    walked = [
        i
        for offset in (0, 2, 4)
        for i in _ids(client.get(URL, params={"limit": 2, "offset": offset}).json())
    ]
    expected = [str(s.id) for s in sorted(rows, key=lambda s: s.id)]
    assert walked == expected
    assert walked == _ids(client.get(URL).json())


def test_orders_by_creation_time_first(client: TestClient, db_session: Session) -> None:
    project = _project(db_session, client)
    later = _stakeholder(db_session, client, project, name="Later")
    earlier = _stakeholder(db_session, client, project, name="Earlier")
    later.created_at = datetime(2026, 6, 1, tzinfo=UTC)
    earlier.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    db_session.flush()

    assert _ids(client.get(URL).json()) == [str(earlier.id), str(later.id)]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"project_id": "not-a-uuid"},
        {"influence": "critical"},
        {"interest": "extreme"},
        {"decision_authority": "owner"},
        {"limit": 0},
        {"limit": 501},
        {"offset": -1},
    ],
)
def test_invalid_inputs_return_422(client: TestClient, params: dict[str, object]) -> None:
    assert client.get(URL, params=params).status_code == 422


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def test_unauthenticated_request_returns_401(unauthenticated_client: TestClient) -> None:
    assert unauthenticated_client.get(URL).status_code == 401


@pytest.mark.parametrize("role", list(UserRole))
def test_every_role_holds_stakeholder_read(
    client_as: Callable[[UserRole], TestClient], db_session: Session, role: UserRole
) -> None:
    """STAKEHOLDER_READ is in _READ_PERMISSIONS (every role, Viewer
    included) — the same grant set the per-project GET
    /projects/{id}/stakeholders route already relies on, so there is no
    role the register could deny that the per-project route allows."""
    actor = client_as(role)
    _stakeholder(db_session, actor, _project(db_session, actor))

    response = actor.get(URL)
    assert response.status_code == 200
    assert response.json()["total"] == 1


# ---------------------------------------------------------------------------
# Multi-tenancy — cross-organization data must never appear and must never
# be confirmed to exist (CLAUDE.md §27, docs/adr/0012).
# ---------------------------------------------------------------------------


def test_excludes_another_organizations_stakeholders(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    leaked = make_stakeholder(db_session, organization=org_b, project=project_b, name="Org B")
    mine = _stakeholder(db_session, client, _project(db_session, client), name="Org A")

    body = client.get(URL).json()
    assert _ids(body) == [str(mine.id)]
    assert body["total"] == 1
    assert str(leaked.id) not in _ids(body)


def test_project_filter_naming_another_organizations_project_is_indistinguishable_from_unknown(
    client: TestClient, db_session: Session
) -> None:
    """A REAL project in another organization and a random nonexistent id
    must produce byte-identical responses — the filter must not become a
    probe for whether another organization's project (or its stakeholders)
    exists."""
    org_b = make_organization(db_session, slug="org-b-filter")
    project_b = make_project(db_session, organization=org_b, name="Org B Project")
    make_stakeholder(db_session, organization=org_b, project=project_b)
    _stakeholder(db_session, client, _project(db_session, client))

    foreign = client.get(URL, params={"project_id": str(project_b.id)})
    unknown = client.get(URL, params={"project_id": str(uuid.uuid4())})
    assert foreign.status_code == unknown.status_code == 200
    assert foreign.json() == unknown.json() == {"items": [], "total": 0}


def test_permissive_filters_cannot_bypass_organization_scoping(
    client: TestClient, db_session: Session
) -> None:
    org_b = make_organization(db_session, slug="org-b-sweep")
    project_b = make_project(db_session, organization=org_b)
    for influence in StakeholderInfluence:
        make_stakeholder(
            db_session, organization=org_b, project=project_b, influence=influence
        )

    for influence in StakeholderInfluence:
        body = client.get(URL, params={"influence": str(influence)}).json()
        assert body == {"items": [], "total": 0}


def test_per_project_route_is_unchanged(client: TestClient, db_session: Session) -> None:
    """Regression guard: the new org-wide route must not alter the
    existing project-scoped list (bare array, not a Page envelope)."""
    project = _project(db_session, client)
    stakeholder = _stakeholder(db_session, client, project)

    response = client.get(f"/api/v1/projects/{project.id}/stakeholders")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [str(stakeholder.id)]
