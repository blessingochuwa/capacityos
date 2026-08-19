"""has_permission is a pure function (no I/O, no app, no database) — see
docs/adr/0010-authentication-rbac-audit.md and
docs/adr/0011-instance-level-resource-authorization.md."""

from app.domain.authorization import Permission, ResourceScope, has_permission
from app.models.enums import UserRole


def test_viewer_can_read_but_not_write() -> None:
    assert has_permission(UserRole.VIEWER, Permission.PERSON_READ)
    assert not has_permission(UserRole.VIEWER, Permission.PERSON_WRITE)
    assert not has_permission(UserRole.VIEWER, Permission.PERSON_DELETE)


def test_viewer_can_use_ai_but_not_export_or_import() -> None:
    assert has_permission(UserRole.VIEWER, Permission.AI_USE)
    assert not has_permission(UserRole.VIEWER, Permission.EXPORT_USE)
    assert not has_permission(UserRole.VIEWER, Permission.IMPORT_USE)


def test_member_can_export_but_not_write() -> None:
    assert has_permission(UserRole.MEMBER, Permission.EXPORT_USE)
    assert not has_permission(UserRole.MEMBER, Permission.PERSON_WRITE)
    assert not has_permission(UserRole.MEMBER, Permission.IMPORT_USE)


def test_manager_can_write_and_import_but_not_manage_users() -> None:
    for permission in (
        Permission.PERSON_WRITE,
        Permission.PERSON_DELETE,
        Permission.SCENARIO_WRITE,
        Permission.IMPORT_USE,
        Permission.EXPORT_USE,
    ):
        assert has_permission(UserRole.MANAGER, permission)
    assert not has_permission(UserRole.MANAGER, Permission.USER_WRITE)
    assert not has_permission(UserRole.MANAGER, Permission.USER_READ)
    assert not has_permission(UserRole.MANAGER, Permission.AUDIT_READ)


def test_admin_can_manage_users_and_read_audit() -> None:
    assert has_permission(UserRole.ADMIN, Permission.USER_WRITE)
    assert has_permission(UserRole.ADMIN, Permission.USER_READ)
    assert has_permission(UserRole.ADMIN, Permission.AUDIT_READ)


def test_owner_has_exactly_the_same_permission_set_as_admin() -> None:
    """The Owner/Admin distinction is procedural (see UserService), not an
    extra Permission — the two roles' grants are identical by design."""
    from app.domain.authorization import ROLE_PERMISSIONS

    assert ROLE_PERMISSIONS[UserRole.OWNER] == ROLE_PERMISSIONS[UserRole.ADMIN]


def test_every_role_can_read_all_operational_entities() -> None:
    """user.read and audit.read are deliberately NOT universal — see
    test_manager_can_write_and_import_but_not_manage_users."""
    operational_read_permissions = [
        Permission.PERSON_READ,
        Permission.TEAM_READ,
        Permission.PROJECT_READ,
        Permission.ALLOCATION_READ,
        Permission.SCHEDULE_READ,
        Permission.SKILL_READ,
        Permission.SCENARIO_READ,
        Permission.INSIGHT_READ,
        Permission.AI_USE,
    ]
    for role in UserRole:
        for permission in operational_read_permissions:
            assert has_permission(role, permission), f"{role} should have {permission}"


def test_no_resource_argument_is_a_pure_type_level_check() -> None:
    """Phase 11: passing no `resource` at all preserves Phase 10 behavior
    exactly — every call site that doesn't scope a permission (i.e. every
    call site except the Team/Project write/delete checks) is unaffected."""
    assert has_permission(UserRole.VIEWER, Permission.PERSON_READ) is True
    assert has_permission(UserRole.MANAGER, Permission.PERSON_WRITE) is True


def test_owner_and_admin_bypass_resource_scope_even_when_ungranted() -> None:
    """Owner/Admin authority is role-based, never grant-based — they must
    never need a TeamAccessGrant/ProjectAccessGrant row to act."""
    ungranted = ResourceScope(granted=False)
    assert has_permission(UserRole.OWNER, Permission.TEAM_WRITE, resource=ungranted) is True
    assert has_permission(UserRole.ADMIN, Permission.PROJECT_DELETE, resource=ungranted) is True


def test_manager_denied_resource_scope_without_a_grant() -> None:
    ungranted = ResourceScope(granted=False)
    assert has_permission(UserRole.MANAGER, Permission.TEAM_WRITE, resource=ungranted) is False
    assert has_permission(UserRole.MANAGER, Permission.PROJECT_DELETE, resource=ungranted) is False


def test_manager_allowed_resource_scope_with_a_grant() -> None:
    granted = ResourceScope(granted=True)
    assert has_permission(UserRole.MANAGER, Permission.TEAM_WRITE, resource=granted) is True
    assert has_permission(UserRole.MANAGER, Permission.PROJECT_DELETE, resource=granted) is True


def test_member_and_viewer_still_denied_even_with_a_grant() -> None:
    """The type-level check (ROLE_PERMISSIONS) always runs first — Member
    and Viewer hold no *_WRITE/*_DELETE permission at all, so a ResourceScope
    can never grant them write access regardless of its `granted` value."""
    granted = ResourceScope(granted=True)
    assert has_permission(UserRole.MEMBER, Permission.TEAM_WRITE, resource=granted) is False
    assert has_permission(UserRole.VIEWER, Permission.PROJECT_DELETE, resource=granted) is False


def test_access_manage_is_admin_and_owner_only() -> None:
    """The permission that lets someone grant/revoke instance access must
    never be held by Manager — otherwise a Manager could grant themselves
    access to any team/project, defeating the entire scope model."""
    assert has_permission(UserRole.OWNER, Permission.ACCESS_MANAGE) is True
    assert has_permission(UserRole.ADMIN, Permission.ACCESS_MANAGE) is True
    assert has_permission(UserRole.MANAGER, Permission.ACCESS_MANAGE) is False
    assert has_permission(UserRole.MEMBER, Permission.ACCESS_MANAGE) is False
    assert has_permission(UserRole.VIEWER, Permission.ACCESS_MANAGE) is False
