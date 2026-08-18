"""Centralized RBAC policy (Phase 10) — pure, DB-free, no HTTP.

The single place a role's grants are decided, matching this codebase's
existing convention of explicit rank/grant tables over scattered
conditionals (e.g. PROFICIENCY_RANK in app/domain/skills.py, _SEVERITY_RANK
in app/services/insight_service.py). Routes and dependencies call
has_permission(role, permission) — never `if user.role == "admin"` inline.

Phase 10 implements TYPE-level authorization only (role -> permission on an
entity TYPE). The `resource` parameter on has_permission is accepted but
unused today — a deliberate forward-compat seam so a future phase can add
instance-level scoping (e.g. "only this team's Manager") without changing
every call site's signature. See docs/adr/0010-authentication-rbac-audit.md.
"""

from enum import StrEnum
from typing import Any

from app.models.enums import UserRole


class Permission(StrEnum):
    """One permission per entity type per read/write/delete, plus a few
    cross-cutting capabilities. schedule.* covers both WorkingSchedule and
    AvailabilityException (both "this person's time," same granularity the
    domain docs already group them at). skill.* covers the Skill catalog,
    PersonSkill, and ProjectSkillRequirement (all skill-assignment data)."""

    PERSON_READ = "person.read"
    PERSON_WRITE = "person.write"
    PERSON_DELETE = "person.delete"

    TEAM_READ = "team.read"
    TEAM_WRITE = "team.write"
    TEAM_DELETE = "team.delete"

    PROJECT_READ = "project.read"
    PROJECT_WRITE = "project.write"
    PROJECT_DELETE = "project.delete"

    ALLOCATION_READ = "allocation.read"
    ALLOCATION_WRITE = "allocation.write"
    ALLOCATION_DELETE = "allocation.delete"

    SCHEDULE_READ = "schedule.read"
    SCHEDULE_WRITE = "schedule.write"
    SCHEDULE_DELETE = "schedule.delete"

    SKILL_READ = "skill.read"
    SKILL_WRITE = "skill.write"
    SKILL_DELETE = "skill.delete"

    SCENARIO_READ = "scenario.read"
    SCENARIO_WRITE = "scenario.write"
    SCENARIO_DELETE = "scenario.delete"

    INSIGHT_READ = "insight.read"
    IMPORT_USE = "import.use"
    EXPORT_USE = "export.use"
    AI_USE = "ai.use"

    USER_READ = "user.read"
    USER_WRITE = "user.write"
    AUDIT_READ = "audit.read"


_READ_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.PERSON_READ,
        Permission.TEAM_READ,
        Permission.PROJECT_READ,
        Permission.ALLOCATION_READ,
        Permission.SCHEDULE_READ,
        Permission.SKILL_READ,
        Permission.SCENARIO_READ,
        Permission.INSIGHT_READ,
        Permission.AI_USE,
    }
)
"""Granted to every role, including Viewer — reads are gated on
"authenticated," not on role, in Phase 10. AI is included: it never mutates
data (Phase 8), so it carries the same risk profile as a read."""

_WRITE_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.PERSON_WRITE,
        Permission.PERSON_DELETE,
        Permission.TEAM_WRITE,
        Permission.TEAM_DELETE,
        Permission.PROJECT_WRITE,
        Permission.PROJECT_DELETE,
        Permission.ALLOCATION_WRITE,
        Permission.ALLOCATION_DELETE,
        Permission.SCHEDULE_WRITE,
        Permission.SCHEDULE_DELETE,
        Permission.SKILL_WRITE,
        Permission.SKILL_DELETE,
        Permission.SCENARIO_WRITE,
        Permission.SCENARIO_DELETE,
        Permission.IMPORT_USE,
    }
)

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.VIEWER: _READ_PERMISSIONS,
    UserRole.MEMBER: _READ_PERMISSIONS | {Permission.EXPORT_USE},
    UserRole.MANAGER: _READ_PERMISSIONS | {Permission.EXPORT_USE} | _WRITE_PERMISSIONS,
    UserRole.ADMIN: (
        _READ_PERMISSIONS
        | {Permission.EXPORT_USE}
        | _WRITE_PERMISSIONS
        | {Permission.USER_READ, Permission.USER_WRITE, Permission.AUDIT_READ}
    ),
    UserRole.OWNER: (
        _READ_PERMISSIONS
        | {Permission.EXPORT_USE}
        | _WRITE_PERMISSIONS
        | {Permission.USER_READ, Permission.USER_WRITE, Permission.AUDIT_READ}
    ),
    # Owner and Admin share an identical permission SET — what distinguishes
    # Owner is procedural, enforced in UserService, not an extra Permission:
    # only an Owner may promote/demote another Owner or Admin, and the
    # system must always retain >=1 active Owner.
}


def has_permission(role: UserRole, permission: Permission, resource: Any = None) -> bool:
    """resource is accepted for forward compatibility (see module docstring)
    but ignored in Phase 10 — every check today is purely role-based."""
    del resource
    return permission in ROLE_PERMISSIONS[role]
