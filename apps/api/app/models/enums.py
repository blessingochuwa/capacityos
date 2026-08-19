from enum import StrEnum


class EmploymentStatus(StrEnum):
    """Controlled vocabulary for Person.employment_status.

    Extending this list (e.g. "on_leave", "contractor") is a code change plus
    a migration to widen the DB CHECK constraint — deliberately not a raw
    string column, since employment status gates real business rules later
    (e.g. whether a person counts toward team capacity).
    """

    ACTIVE = "active"
    INACTIVE = "inactive"


class ProjectStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AllocationUnit(StrEnum):
    """Unit that Allocation.allocation_hours is expressed in.

    Only one member today: the total planned hours across the allocation's
    whole [start_date, end_date] period (see Allocation docstring). The enum
    exists so a future time-phased unit (e.g. hours_per_week) can be added
    without changing the column shape.
    """

    TOTAL_HOURS = "total_hours"


class AvailabilityType(StrEnum):
    """Controlled vocabulary for AvailabilityException.availability_type.

    Unlike the other enums here, this one is NOT backed by a DB CHECK
    constraint (see AvailabilityException.__table_args__) — the spec is
    explicit that availability reasons must not be hard-coded into the
    database structure. Adding a new reason is a pure code change.
    """

    ANNUAL_LEAVE = "annual_leave"
    SICK_LEAVE = "sick_leave"
    PUBLIC_HOLIDAY = "public_holiday"
    TRAINING = "training"
    COMPANY_EVENT = "company_event"
    PARENTAL_LEAVE = "parental_leave"
    PERSONAL_LEAVE = "personal_leave"
    REDUCED_AVAILABILITY = "reduced_availability"
    OTHER = "other"


class ScenarioStatus(StrEnum):
    """Controlled vocabulary for Scenario.status (Phase 4).

    A workflow label the user sets deliberately (PATCH) — it has no effect
    on calculation: draft/active/archived scenarios all calculate exactly
    the same way. It exists purely so a user can distinguish "still being
    built," "the one we're actually planning around," and "no longer
    relevant" in the scenario list.
    """

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ScenarioOperationType(StrEnum):
    """Controlled vocabulary for ScenarioOperation.operation_type (Phase 4).

    See docs/adr/0004-phase-4-scenario-planning.md for why these 8 types
    were chosen over the prompt's original 6 categories (in particular, why
    there is no standalone "change project demand" type: Project has no
    stored demand field — demand is derived from Allocation rows — so demand
    changes are expressed as add_allocation/adjust_allocation instead of an
    invented distribution rule).
    """

    ADD_ALLOCATION = "add_allocation"
    ADJUST_ALLOCATION = "adjust_allocation"
    REMOVE_ALLOCATION = "remove_allocation"
    MOVE_ALLOCATION = "move_allocation"
    SHIFT_PROJECT = "shift_project"
    AVAILABILITY_OVERRIDE = "availability_override"
    AVAILABILITY_CLEAR = "availability_clear"
    ADD_HYPOTHETICAL_RESOURCE = "add_hypothetical_resource"


class SkillProficiency(StrEnum):
    """Controlled vocabulary for PersonSkill.proficiency and
    ProjectSkillRequirement.minimum_proficiency (Phase 7).

    An ordered scale, deliberately small and fixed (a DB CHECK constraint,
    like EmploymentStatus/ProjectStatus — proficiency has real business
    meaning for qualification, unlike AvailabilityType's open vocabulary).
    Ordering is not expressed by enum member order (Python StrEnum has none)
    but by the explicit PROFICIENCY_RANK table in app/domain/skills.py — the
    single place proficiency comparison happens, matching this codebase's
    existing convention of explicit rank dicts (_SEVERITY_RANK, _TYPE_RANK in
    app/services/insight_service.py) over relying on enum declaration order.
    """

    BEGINNER = "beginner"
    WORKING = "working"
    PROFICIENT = "proficient"
    ADVANCED = "advanced"
    EXPERT = "expert"


class UserRole(StrEnum):
    """Controlled vocabulary for User.role (Phase 10).

    Ordering/precedence is not expressed by enum declaration order — see the
    explicit ROLE_PERMISSIONS table in app/domain/authorization.py, the
    single place a role's grants are decided (matching this codebase's
    existing convention of explicit rank/grant tables over relying on enum
    member order, e.g. PROFICIENCY_RANK, _SEVERITY_RANK).
    """

    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    VIEWER = "viewer"


class UserStatus(StrEnum):
    """Controlled vocabulary for User.status (Phase 10).

    "invited" is a user created by an admin but who has not yet completed
    account setup (Phase 10 has no invite-email flow — see
    docs/adr/0010-authentication-rbac-audit.md — but the status exists so a
    future phase can add one without a schema change). "disabled" blocks
    login entirely without deleting audit/history-relevant rows.
    """

    ACTIVE = "active"
    INVITED = "invited"
    DISABLED = "disabled"


class AuditOutcome(StrEnum):
    """Controlled vocabulary for AuditEvent.outcome (Phase 10).

    A small, fixed, closed set with real meaning to every audit consumer
    (e.g. filtering "show me every denial") — DB CHECK-constrained like
    EmploymentStatus/ProjectStatus/UserStatus, unlike AuditAction below.
    """

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"


class AuditAction(StrEnum):
    """Controlled vocabulary for AuditEvent.action (Phase 10).

    Deliberately NOT DB-CHECK-constrained, unlike AuditOutcome — matching
    AvailabilityType's precedent (open vocabulary, application-layer only)
    rather than EmploymentStatus's (fixed, DB-enforced): new audited actions
    are expected to be added as the product grows, and that must be a pure
    code change, never a migration. One systematic `{entity}.{verb}` member
    per mutating capability in the system.
    """

    AUTH_LOGIN_SUCCESS = "auth.login_success"
    AUTH_LOGIN_FAILURE = "auth.login_failure"
    AUTH_LOGOUT = "auth.logout"
    AUTH_ACCOUNT_LOCKED = "auth.account_locked"
    PERMISSION_DENIED = "permission.denied"

    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_ROLE_CHANGE = "user.role_change"
    USER_STATUS_CHANGE = "user.status_change"

    PERSON_CREATE = "person.create"
    PERSON_UPDATE = "person.update"
    PERSON_DELETE = "person.delete"
    PERSON_SKILL_ADD = "person_skill.add"
    PERSON_SKILL_UPDATE = "person_skill.update"
    PERSON_SKILL_REMOVE = "person_skill.remove"

    TEAM_CREATE = "team.create"
    TEAM_UPDATE = "team.update"
    TEAM_DELETE = "team.delete"
    TEAM_MEMBER_ADD = "team.member_add"
    TEAM_MEMBER_REMOVE = "team.member_remove"

    PROJECT_CREATE = "project.create"
    PROJECT_UPDATE = "project.update"
    PROJECT_DELETE = "project.delete"
    PROJECT_SKILL_REQUIREMENT_ADD = "project_skill_requirement.add"
    PROJECT_SKILL_REQUIREMENT_UPDATE = "project_skill_requirement.update"
    PROJECT_SKILL_REQUIREMENT_REMOVE = "project_skill_requirement.remove"

    ALLOCATION_CREATE = "allocation.create"
    ALLOCATION_UPDATE = "allocation.update"
    ALLOCATION_DELETE = "allocation.delete"

    WORKING_SCHEDULE_CREATE = "working_schedule.create"
    WORKING_SCHEDULE_UPDATE = "working_schedule.update"
    WORKING_SCHEDULE_DELETE = "working_schedule.delete"

    AVAILABILITY_EXCEPTION_CREATE = "availability_exception.create"
    AVAILABILITY_EXCEPTION_UPDATE = "availability_exception.update"
    AVAILABILITY_EXCEPTION_DELETE = "availability_exception.delete"

    SKILL_CREATE = "skill.create"
    SKILL_UPDATE = "skill.update"
    SKILL_DELETE = "skill.delete"

    SCENARIO_CREATE = "scenario.create"
    SCENARIO_UPDATE = "scenario.update"
    SCENARIO_DELETE = "scenario.delete"
    SCENARIO_OPERATION_CREATE = "scenario_operation.create"
    SCENARIO_OPERATION_UPDATE = "scenario_operation.update"
    SCENARIO_OPERATION_DELETE = "scenario_operation.delete"

    IMPORT_APPLY = "import.apply"
    EXPORT_USE = "export.use"

    RESOURCE_ACCESS_DENIED = "resource_access.denied"
    """A caller held the type-level permission but not an instance-level
    grant for this specific Team/Project (Phase 11) — distinct from
    PERMISSION_DENIED above, which fires when the role lacks the permission
    entirely. Always carries resource_id (unlike PERMISSION_DENIED, which
    never knows a specific instance)."""

    ACCESS_GRANT_CREATE = "access_grant.create"
    ACCESS_GRANT_REVOKE = "access_grant.revoke"
