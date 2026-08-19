"""End-to-end Phase 11 flow, not just individual authorization functions:
create a Manager, confirm no access, grant Team A, succeed on A / still
denied on B, grant Project B, succeed, revoke, denied again, then verify
the complete ordered audit trail. See
docs/adr/0011-instance-level-resource-authorization.md."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.models.enums import UserRole
from tests.conftest import user_id_of


def test_full_grant_scope_revoke_flow_with_audit_trail(
    client_as: Callable[[UserRole], TestClient],
) -> None:
    owner = client_as(UserRole.OWNER)
    team_a = owner.post("/api/v1/teams", json={"name": "Team A"}).json()
    team_b = owner.post("/api/v1/teams", json={"name": "Team B"}).json()
    project_b = owner.post("/api/v1/projects", json={"name": "Project B"}).json()

    manager = client_as(UserRole.MANAGER)
    manager_id = user_id_of(manager)

    # 1. Manager starts with no instance access at all — writes denied.
    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(f"/api/v1/teams/{team_a['id']}", json={"name": "A v2"}).status_code == 403

    # 2. Grant Team A.
    owner.activate()  # type: ignore[attr-defined]
    assert owner.post(
        f"/api/v1/teams/{team_a['id']}/access-grants", json={"user_id": manager_id}
    ).status_code == 201

    # 3. Manager can now act on Team A, but Team B remains denied.
    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(f"/api/v1/teams/{team_a['id']}", json={"name": "A v2"}).status_code == 200
    assert manager.patch(f"/api/v1/teams/{team_b['id']}", json={"name": "B v2"}).status_code == 403

    # 4. Grant Project B.
    owner.activate()  # type: ignore[attr-defined]
    assert owner.post(
        f"/api/v1/projects/{project_b['id']}/access-grants", json={"user_id": manager_id}
    ).status_code == 201

    # 5. Manager can now act on Project B.
    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(
        f"/api/v1/projects/{project_b['id']}", json={"name": "Project B v2"}
    ).status_code == 200

    # 6. Revoke Project B.
    owner.activate()  # type: ignore[attr-defined]
    assert owner.delete(
        f"/api/v1/projects/{project_b['id']}/access-grants/{manager_id}"
    ).status_code == 204

    # 7. Immediate denial on Project B again; Team A access is untouched.
    manager.activate()  # type: ignore[attr-defined]
    assert manager.patch(
        f"/api/v1/projects/{project_b['id']}", json={"name": "Project B v3"}
    ).status_code == 403
    assert manager.patch(f"/api/v1/teams/{team_a['id']}", json={"name": "A v3"}).status_code == 200

    # 8. Inspect the full ordered audit trail for this manager.
    owner.activate()  # type: ignore[attr-defined]
    events = owner.get(
        "/api/v1/audit", params={"actor_user_id": manager_id, "limit": 500}
    ).json()["items"]
    actions_oldest_first = [e["action"] for e in reversed(events)]

    assert actions_oldest_first == [
        "resource_access.denied",  # step 1: Team A denied
        "team.update",  # step 3: Team A allowed
        "resource_access.denied",  # step 3: Team B denied
        "project.update",  # step 5: Project B allowed
        "resource_access.denied",  # step 7: Project B denied again
        "team.update",  # step 7: Team A still allowed
    ]
