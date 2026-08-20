"""AccessGrantService (Phase 11, organization-scoped Phase 12) — the single
place instance-level Team/Project scope is decided and grants are managed.
Uses a real db_session (these repositories need actual queries) with a real
AuditService sharing the same session, exactly as
app/api/deps.py::get_access_grant_service and get_audit_service wire them in
production — asserting against persisted AuditEvent rows is more faithful
than mocking AuditService here."""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome, UserRole
from app.models.organization import Organization
from app.repositories.audit_event import AuditEventRepository
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_access_grant import ProjectAccessGrantRepository
from app.repositories.team import TeamRepository
from app.repositories.team_access_grant import TeamAccessGrantRepository
from app.services.access_grant import AccessGrantService
from app.services.audit import AuditService
from tests.factories import make_organization_membership, make_project, make_team, make_user


def _service(session: Session) -> AccessGrantService:
    return AccessGrantService(
        TeamAccessGrantRepository(session),
        ProjectAccessGrantRepository(session),
        TeamRepository(session),
        ProjectRepository(session),
        OrganizationMembershipRepository(session),
    )


def _audit(session: Session) -> AuditService:
    return AuditService(AuditEventRepository(session))


# ---------------------------------------------------------------------------
# enforce_team_access / enforce_project_access
# ---------------------------------------------------------------------------


def test_owner_and_admin_enforce_team_access_with_zero_grant_rows(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    team = make_team(db_session, organization=organization)
    for role in (UserRole.OWNER, UserRole.ADMIN):
        user = make_user(db_session, email=f"{role.value}@example.com")
        membership = make_organization_membership(
            db_session, user=user, organization=organization, role=role
        )
        service.enforce_team_access(
            user, membership, team.id, Permission.TEAM_WRITE, audit_service=audit, request_id=None
        )  # no exception


def test_manager_denied_team_access_without_a_grant(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    membership = make_organization_membership(
        db_session, user=manager, organization=organization, role=UserRole.MANAGER
    )
    team = make_team(db_session, organization=organization)

    with pytest.raises(ForbiddenError):
        service.enforce_team_access(
            manager, membership, team.id, Permission.TEAM_WRITE, audit_service=audit,
            request_id="req-1",
        )


def test_manager_allowed_team_access_with_a_grant(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    membership = make_organization_membership(
        db_session, user=manager, organization=organization, role=UserRole.MANAGER
    )
    team = make_team(db_session, organization=organization)
    service.grant_team_access(organization.id, team.id, manager.id, granted_by=manager)

    service.enforce_team_access(
        manager, membership, team.id, Permission.TEAM_WRITE, audit_service=audit, request_id=None
    )  # no exception


def test_manager_granted_team_a_still_denied_team_b(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    membership = make_organization_membership(
        db_session, user=manager, organization=organization, role=UserRole.MANAGER
    )
    team_a = make_team(db_session, organization=organization, name="Design")
    team_b = make_team(db_session, organization=organization, name="Engineering")
    service.grant_team_access(organization.id, team_a.id, manager.id, granted_by=manager)

    service.enforce_team_access(
        manager, membership, team_a.id, Permission.TEAM_WRITE, audit_service=audit,
        request_id=None,
    )
    with pytest.raises(ForbiddenError):
        service.enforce_team_access(
            manager, membership, team_b.id, Permission.TEAM_WRITE, audit_service=audit,
            request_id=None,
        )


def test_denied_team_access_records_a_resource_access_denied_audit_event(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    membership = make_organization_membership(
        db_session, user=manager, organization=organization, role=UserRole.MANAGER
    )
    team = make_team(db_session, organization=organization)

    with pytest.raises(ForbiddenError):
        service.enforce_team_access(
            manager, membership, team.id, Permission.TEAM_WRITE, audit_service=audit,
            request_id="req-42",
        )

    events, total = AuditEventRepository(db_session).list_filtered(organization_id=organization.id)
    assert total == 1
    event = events[0]
    assert event.action == AuditAction.RESOURCE_ACCESS_DENIED
    assert event.outcome == AuditOutcome.DENIED
    assert event.resource_type == "team"
    assert event.resource_id == str(team.id)
    assert event.request_id == "req-42"
    assert event.event_metadata == {"permission": "team.write", "role": "manager"}


def test_manager_denied_project_access_without_a_grant(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    membership = make_organization_membership(
        db_session, user=manager, organization=organization, role=UserRole.MANAGER
    )
    project = make_project(db_session, organization=organization)

    with pytest.raises(ForbiddenError):
        service.enforce_project_access(
            manager, membership, project.id, Permission.PROJECT_WRITE, audit_service=audit,
            request_id=None,
        )


def test_manager_granted_project_a_still_denied_project_b(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    audit = _audit(db_session)
    manager = make_user(db_session)
    membership = make_organization_membership(
        db_session, user=manager, organization=organization, role=UserRole.MANAGER
    )
    project_a = make_project(db_session, organization=organization, name="Website Redesign")
    project_b = make_project(db_session, organization=organization, name="Mobile App")
    service.grant_project_access(organization.id, project_a.id, manager.id, granted_by=manager)

    service.enforce_project_access(
        manager, membership, project_a.id, Permission.PROJECT_WRITE, audit_service=audit,
        request_id=None,
    )
    with pytest.raises(ForbiddenError):
        service.enforce_project_access(
            manager, membership, project_b.id, Permission.PROJECT_WRITE, audit_service=audit,
            request_id=None,
        )


# ---------------------------------------------------------------------------
# grant/revoke CRUD
# ---------------------------------------------------------------------------


def test_grant_team_access_rejects_nonexistent_team(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    make_organization_membership(
        db_session, user=admin, organization=organization, role=UserRole.ADMIN
    )
    with pytest.raises(NotFoundError):
        service.grant_team_access(organization.id, uuid.uuid4(), admin.id, granted_by=admin)


def test_grant_team_access_rejects_nonexistent_user(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    make_organization_membership(
        db_session, user=admin, organization=organization, role=UserRole.ADMIN
    )
    team = make_team(db_session, organization=organization)
    with pytest.raises(NotFoundError):
        service.grant_team_access(organization.id, team.id, uuid.uuid4(), granted_by=admin)


def test_grant_team_access_rejects_duplicate(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    make_organization_membership(
        db_session, user=admin, organization=organization, role=UserRole.ADMIN
    )
    manager = make_user(db_session, email="manager@example.com")
    make_organization_membership(
        db_session, user=manager, organization=organization, role=UserRole.MANAGER
    )
    team = make_team(db_session, organization=organization)
    service.grant_team_access(organization.id, team.id, manager.id, granted_by=admin)

    with pytest.raises(ConflictError):
        service.grant_team_access(organization.id, team.id, manager.id, granted_by=admin)


def test_revoke_team_access_rejects_nonexistent_grant(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    manager = make_user(db_session)
    team = make_team(db_session, organization=organization)
    with pytest.raises(NotFoundError):
        service.revoke_team_access(organization.id, team.id, manager.id)


def test_grant_then_revoke_then_grant_again_round_trips(
    db_session: Session, organization: Organization
) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    make_organization_membership(
        db_session, user=admin, organization=organization, role=UserRole.ADMIN
    )
    manager = make_user(db_session, email="manager@example.com")
    make_organization_membership(
        db_session, user=manager, organization=organization, role=UserRole.MANAGER
    )
    team = make_team(db_session, organization=organization)

    service.grant_team_access(organization.id, team.id, manager.id, granted_by=admin)
    assert (
        TeamAccessGrantRepository(db_session).exists(manager.id, team.id, organization.id) is True
    )

    service.revoke_team_access(organization.id, team.id, manager.id)
    assert (
        TeamAccessGrantRepository(db_session).exists(manager.id, team.id, organization.id) is False
    )

    service.grant_team_access(organization.id, team.id, manager.id, granted_by=admin)
    assert (
        TeamAccessGrantRepository(db_session).exists(manager.id, team.id, organization.id) is True
    )


def test_accessible_team_and_project_ids(db_session: Session, organization: Organization) -> None:
    service = _service(db_session)
    admin = make_user(db_session)
    make_organization_membership(
        db_session, user=admin, organization=organization, role=UserRole.ADMIN
    )
    manager = make_user(db_session, email="manager@example.com")
    make_organization_membership(
        db_session, user=manager, organization=organization, role=UserRole.MANAGER
    )
    team = make_team(db_session, organization=organization)
    project = make_project(db_session, organization=organization)

    assert service.accessible_team_ids(manager.id, organization.id) == []
    assert service.accessible_project_ids(manager.id, organization.id) == []

    service.grant_team_access(organization.id, team.id, manager.id, granted_by=admin)
    service.grant_project_access(organization.id, project.id, manager.id, granted_by=admin)

    assert service.accessible_team_ids(manager.id, organization.id) == [team.id]
    assert service.accessible_project_ids(manager.id, organization.id) == [project.id]
