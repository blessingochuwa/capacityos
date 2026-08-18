"""has_permission is a pure function (no I/O, no app, no database) — see
docs/adr/0010-authentication-rbac-audit.md."""

from app.domain.authorization import Permission, has_permission
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


def test_resource_parameter_is_accepted_but_ignored() -> None:
    """Phase 10 implements type-level authorization only — see the module
    docstring's forward-compat seam."""
    assert has_permission(UserRole.VIEWER, Permission.PERSON_READ, resource=object()) == (
        has_permission(UserRole.VIEWER, Permission.PERSON_READ)
    )
