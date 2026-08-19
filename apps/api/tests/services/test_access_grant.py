"""AccessGrantService (Phase 11) — the single place instance-level Team/
Project scope is decided and grants are managed. Uses a real db_session
(these repositories need actual queries) with a real AuditService sharing
the same session, exactly as app/api/deps.py::get_access_grant_service and
get_audit_service wire them in production — asserting against persisted
AuditEvent rows is more faithful than mocking AuditService here."""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome, UserRole
from app.repositories.audit_event import AuditEventRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_access_grant import ProjectAccessGrantRepository
from app.repositories.team import TeamRepository
from app.repositories.team_access_grant import TeamAccessGrantRepository
from app.repositories.user import UserRepository
from app.services.access_grant import AccessGrantService
from app.services.audit import AuditService
from tests.factories import make_project, make_team, make_user


def _service(session: Session) -> AccessGrantService:
    return AccessGrantService(
        TeamAccessGrantRepository(session),
        ProjectAccessGrantRepository(session),
        UserRepository(session),
        TeamRepository(session),
        ProjectRepository(session),
    )


def _audit(session: Session) -> AuditService:
    return AuditService(AuditEventRepository(session))


# ---------------------------------------------------------------------------
# enforce_team_access / enforce_project_access
# ---------------------------------------------------------------------------


def test_owner_and_admin_enforce_team_access_with_zero_grant_rows(db_session: Session) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    team = make_team(db_session)
    for role in (UserRole.OWNER, UserRole.ADMIN):
        user = make_user(db_session, email=f"{role.value}@example.com", role=role)
        service.enforce_team_access(
            user, team.id, Permission.TEAM_WRITE, audit_service=audit, request_id=None
        )  # no exception


def test_manager_denied_team_access_without_a_grant(db_session: Session) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    team = make_team(db_session)

    with pytest.raises(ForbiddenError):
        service.enforce_team_access(
            manager, team.id, Permission.TEAM_WRITE, audit_service=audit, request_id="req-1"
        )


def test_manager_allowed_team_access_with_a_grant(db_session: Session) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    team = make_team(db_session)
    service.grant_team_access(team.id, manager.id, granted_by=manager)

    service.enforce_team_access(
        manager, team.id, Permission.TEAM_WRITE, audit_service=audit, request_id=None
    )  # no exception


def test_manager_granted_team_a_still_denied_team_b(db_session: Session) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    team_a = make_team(db_session, name="Design")
    team_b = make_team(db_session, name="Engineering")
    service.grant_team_access(team_a.id, manager.id, granted_by=manager)

    service.enforce_team_access(
        manager, team_a.id, Permission.TEAM_WRITE, audit_service=audit, request_id=None
    )
    with pytest.raises(ForbiddenError):
        service.enforce_team_access(
            manager, team_b.id, Permission.TEAM_WRITE, audit_service=audit, request_id=None
        )


def test_denied_team_access_records_a_resource_access_denied_audit_event(
    db_session: Session,
) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    team = make_team(db_session)

    with pytest.raises(ForbiddenError):
        service.enforce_team_access(
            manager, team.id, Permission.TEAM_WRITE, audit_service=audit, request_id="req-42"
        )

    events, total = AuditEventRepository(db_session).list_filtered()
    assert total == 1
    event = events[0]
    assert event.action == AuditAction.RESOURCE_ACCESS_DENIED
    assert event.outcome == AuditOutcome.DENIED
    assert event.resource_type == "team"
    assert event.resource_id == str(team.id)
    assert event.request_id == "req-42"
    assert event.event_metadata == {"permission": "team.write", "role": "manager"}


def test_manager_denied_project_access_without_a_grant(db_session: Session) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    project = make_project(db_session)

    with pytest.raises(ForbiddenError):
        service.enforce_project_access(
            manager, project.id, Permission.PROJECT_WRITE, audit_service=audit, request_id=None
        )


def test_manager_granted_project_a_still_denied_project_b(db_session: Session) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    project_a = make_project(db_session, name="Website Redesign")
    project_b = make_project(db_session, name="Mobile App")
    service.grant_project_access(project_a.id, manager.id, granted_by=manager)

    service.enforce_project_access(
        manager, project_a.id, Permission.PROJECT_WRITE, audit_service=audit, request_id=None
    )
    with pytest.raises(ForbiddenError):
        service.enforce_project_access(
            manager, project_b.id, Permission.PROJECT_WRITE, audit_service=audit, request_id=None
        )


# ---------------------------------------------------------------------------
# grant/revoke CRUD
# ---------------------------------------------------------------------------


def test_grant_team_access_rejects_nonexistent_team(db_session: Session) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    with pytest.raises(NotFoundError):
        service.grant_team_access(uuid.uuid4(), admin.id, granted_by=admin)


def test_grant_team_access_rejects_nonexistent_user(db_session: Session) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    team = make_team(db_session)
    with pytest.raises(NotFoundError):
        service.grant_team_access(team.id, uuid.uuid4(), granted_by=admin)


def test_grant_team_access_rejects_duplicate(db_session: Session) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    manager = make_user(db_session, email="manager@example.com")
    team = make_team(db_session)
    service.grant_team_access(team.id, manager.id, granted_by=admin)

    with pytest.raises(ConflictError):
        service.grant_team_access(team.id, manager.id, granted_by=admin)


def test_revoke_team_access_rejects_nonexistent_grant(db_session: Session) -> None:
    service = _service(db_session)
    manager = make_user(db_session)
    team = make_team(db_session)
    with pytest.raises(NotFoundError):
        service.revoke_team_access(team.id, manager.id)


def test_grant_then_revoke_then_grant_again_round_trips(db_session: Session) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    manager = make_user(db_session, email="manager@example.com")
    team = make_team(db_session)

    service.grant_team_access(team.id, manager.id, granted_by=admin)
    assert TeamAccessGrantRepository(db_session).exists(manager.id, team.id) is True

    service.revoke_team_access(team.id, manager.id)
    assert TeamAccessGrantRepository(db_session).exists(manager.id, team.id) is False

    service.grant_team_access(team.id, manager.id, granted_by=admin)
    assert TeamAccessGrantRepository(db_session).exists(manager.id, team.id) is True


def test_accessible_team_and_project_ids(db_session: Session) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    manager = make_user(db_session, email="manager@example.com")
    team = make_team(db_session)
    project = make_project(db_session)

    assert service.accessible_team_ids(manager.id) == []
    assert service.accessible_project_ids(manager.id) == []

    service.grant_team_access(team.id, manager.id, granted_by=admin)
    service.grant_project_access(project.id, manager.id, granted_by=admin)

    assert service.accessible_team_ids(manager.id) == [team.id]
    assert service.accessible_project_ids(manager.id) == [project.id]
