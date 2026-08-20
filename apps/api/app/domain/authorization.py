"""Centralized RBAC policy (Phase 10) + instance-level resource scoping
(Phase 11) — pure, DB-free, no HTTP.

The single place a role's grants are decided, matching this codebase's
existing convention of explicit rank/grant tables over scattered
conditionals (e.g. PROFICIENCY_RANK in app/domain/skills.py, _SEVERITY_RANK
in app/services/insight_service.py). Routes and dependencies call
has_permission(role, permission) — never `if user.role == "admin"` inline.

Phase 10 implemented TYPE-level authorization only (role -> permission on an
entity TYPE). Phase 11 fills in the `resource` parameter, which Phase 10 left
accepted-but-unused as a deliberate forward-compat seam: a caller who has
already resolved whether an explicit TeamAccessGrant/ProjectAccessGrant row
exists for this user and this specific instance passes that result in as a
ResourceScope. has_permission itself still performs no I/O — the DB lookup
happens in app/services/access_grant.py::AccessGrantService, which is the
only thing that constructs a ResourceScope. See
docs/adr/0011-instance-level-resource-authorization.md.
"""

from dataclasses import dataclass
from enum import StrEnum

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

    ACCESS_MANAGE = "access.manage"
    """Grant/revoke a TeamAccessGrant or ProjectAccessGrant (Phase 11).
    Deliberately not folded into _WRITE_PERMISSIONS below — Manager holds
    every other write permission but must never hold this one, since it is
    what would let a Manager grant themselves (or anyone) instance-level
    access. Only Admin/Owner receive it, directly in ROLE_PERMISSIONS."""

    ORGANIZATION_MANAGE = "organization.manage"
    """Rename or deactivate an Organization itself (Phase 12) — Owner only,
    directly in ROLE_PERMISSIONS. Organization creation needs no
    permission check at all (any authenticated user may create one,
    becoming its Owner — see OrganizationService.create); this permission
    governs an EXISTING organization's own lifecycle."""

    MEMBERSHIP_MANAGE = "membership.manage"
    """Add/revoke/reactivate a member or change a membership's role within
    one Organization (Phase 12). Mirrors ACCESS_MANAGE's precedent exactly
    — Admin/Owner only, never folded into _WRITE_PERMISSIONS, since it is
    what would let a Manager grant themselves (or anyone) a higher role."""


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
        | {Permission.ACCESS_MANAGE}
        | {Permission.MEMBERSHIP_MANAGE}
    ),
    UserRole.OWNER: (
        _READ_PERMISSIONS
        | {Permission.EXPORT_USE}
        | _WRITE_PERMISSIONS
        | {Permission.USER_READ, Permission.USER_WRITE, Permission.AUDIT_READ}
        | {Permission.ACCESS_MANAGE}
        | {Permission.MEMBERSHIP_MANAGE}
        | {Permission.ORGANIZATION_MANAGE}
    ),
    # Owner and Admin share almost the identical permission set — what
    # distinguishes Owner is ORGANIZATION_MANAGE (rename/deactivate the
    # organization itself — a step above day-to-day membership admin) plus
    # procedural rules enforced in the service layer, not extra
    # Permissions: only an Owner may promote/demote another Owner or
    # Admin, and every organization must always retain >=1 active Owner
    # (Phase 12: this invariant is now per-organization).
}


@dataclass(frozen=True)
class ResourceScope:
    """A precomputed instance-level grant result for a single Team/Project
    resource (Phase 11), resolved by the CALLER — AccessGrantService — via a
    database lookup before calling has_permission. has_permission itself
    performs no I/O, preserving its Phase 10 pure-function invariant.

    granted=True means an explicit TeamAccessGrant/ProjectAccessGrant row
    exists for this user and this specific resource id. It means nothing on
    its own for Owner/Admin (see has_permission below) — those roles bypass
    resource scoping entirely regardless of granted, since their authority
    is role-based, not grant-based.
    """

    granted: bool


def has_permission(
    role: UserRole, permission: Permission, resource: ResourceScope | None = None
) -> bool:
    """Type-level check first (Phase 10, unchanged): a role without the
    permission at all is denied regardless of resource. If resource is None,
    this is a pure type-level check — every Phase 10 call site, and every
    Phase 11 call site for a permission Phase 11 doesn't scope, passes no
    resource and behaves exactly as before.

    If resource is provided, Owner/Admin unconditionally bypass it (their
    authority was never meant to be instance-scoped — see ADR 0011). Every
    other role's access is exactly resource.granted — for Manager (the only
    role that both holds write permissions and is ever passed a
    ResourceScope in Phase 11) this is the instance-grant check; for
    Member/Viewer it's moot in practice since they never reach the write
    permissions Phase 11 scopes in the first place, but the check is applied
    uniformly rather than special-cased.
    """
    if permission not in ROLE_PERMISSIONS[role]:
        return False
    if resource is None:
        return True
    if role in (UserRole.OWNER, UserRole.ADMIN):
        return True
    return resource.granted
