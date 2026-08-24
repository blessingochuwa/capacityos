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


class RiskProbability(StrEnum):
    """Controlled vocabulary for Risk.probability (Phase 13).

    A deliberately coarse 3-tier scale, DB-CHECK-constrained like
    ProjectStatus/SkillProficiency — real business meaning, not an open
    vocabulary. CLAUDE.md §17: "Do not create risk scores that imply false
    precision" — a fine-grained numeric scale here would invite exactly
    that. Combined with RiskImpact via the explicit lookup table in
    app/domain/risk.py to derive exposure; never multiplied into a score.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskImpact(StrEnum):
    """Controlled vocabulary for Risk.impact (Phase 13). See
    RiskProbability's docstring — same rationale, same 3-tier scale."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskStatus(StrEnum):
    """Controlled vocabulary for Risk.status (Phase 13).

    CLAUDE.md §12/§17: "Risk management should be continuous" — a risk
    moves through a real lifecycle, not just open/closed. MITIGATING: a
    response is actively underway. MONITORING: no longer being actively
    worked, but still watched (mitigated but not yet safe to close, or a
    low-priority risk being tracked passively). CLOSED: no longer
    relevant — the terminal state. DB-CHECK-constrained like ProjectStatus,
    since status gates real behavior (a CLOSED risk never produces an
    Insights signal — see app/domain/risk.py::classify_risk_signal).
    """

    OPEN = "open"
    MITIGATING = "mitigating"
    MONITORING = "monitoring"
    CLOSED = "closed"


class StakeholderInfluence(StrEnum):
    """Controlled vocabulary for Stakeholder.influence (Phase 14,
    CLAUDE.md §16) — how much power this stakeholder has to affect the
    project's outcome or direction.

    A deliberately coarse 3-tier scale, DB-CHECK-constrained like
    RiskProbability/RiskImpact — the well-established power/interest
    grid from stakeholder-management practice (CLAUDE.md §37: prefer
    established frameworks) uses exactly this granularity. No numeric
    weighting or combined score is derived from it anywhere — CLAUDE.md
    §16/§17's "do not imply false precision" applies here exactly as it
    does to Risk.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StakeholderInterest(StrEnum):
    """Controlled vocabulary for Stakeholder.interest (Phase 14,
    CLAUDE.md §16) — how invested this stakeholder is in the project's
    outcome. See StakeholderInfluence's docstring — same rationale, same
    3-tier scale, the other axis of the same established power/interest
    grid."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class StakeholderDecisionAuthority(StrEnum):
    """Controlled vocabulary for Stakeholder.decision_authority (Phase 14,
    CLAUDE.md §16) — how much say this stakeholder has in project
    decisions. CLAUDE.md §5: "every important... decision... should have
    an accountable owner" — this field is what lets a decision's owner be
    identified among a project's stakeholders.

    DECISION_MAKER: can make or veto the decision outright. ADVISOR: is
    consulted before a decision is made but doesn't make it. INFORMED:
    is told about decisions after the fact, with no input into them.
    Three ordered levels, not a full RACI matrix — CLAUDE.md §16 asks for
    one "decision authority" field, not a responsibility-assignment
    system; a fourth axis (who does the work) is a different concept this
    phase does not model.
    """

    DECISION_MAKER = "decision_maker"
    ADVISOR = "advisor"
    INFORMED = "informed"


class PrioritizationFrameworkType(StrEnum):
    """Controlled vocabulary for PrioritizationFramework.framework_type
    (Phase 17/18, CLAUDE.md §18).

    Deliberately NOT DB-CHECK-constrained (see
    PrioritizationFramework.__table_args__) — matching AvailabilityType's
    precedent, not RiskProbability's: CLAUDE.md §18 names RICE, WSJF, ICE,
    MoSCoW, and weighted scoring as frameworks that "may be supported
    later," so this vocabulary is expected to grow across phases, and a
    new framework type must stay a pure code change, never a migration.
    Phase 18 completes the set CLAUDE.md §18 names — every member here now
    has a formula in app/domain/prioritization.py. See
    docs/adr/0017-prioritization-engine.md and
    docs/adr/0018-prioritization-frameworks-and-dependencies.md.
    """

    RICE = "rice"
    ICE = "ice"
    WSJF = "wsjf"
    MOSCOW = "moscow"
    WEIGHTED = "weighted"


class MoscowCategory(StrEnum):
    """Controlled vocabulary for ProjectPriorityScore.category (Phase 18)
    — MoSCoW's own four buckets, a fixed, universally-defined method
    (unlike PrioritizationFrameworkType itself) — DB-CHECK-constrained
    like RiskProbability/RiskImpact, matching the "small, fixed vocabulary
    with real business meaning" precedent rather than AvailabilityType's
    open one. Deliberately categorical, never combined into a numeric
    score — see app/domain/prioritization.py's module docstring for why
    MoSCoW has no formula at all."""

    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


class ProjectDependencyType(StrEnum):
    """Controlled vocabulary for ProjectDependency.dependency_type (Phase
    18). `blocks` is the one directional type cycle detection is applied
    to (see app/domain/prioritization.py::detects_cycle) — `blocked_by`
    is deliberately NOT a stored type, it is the reverse query of
    `blocks` (see ProjectDependency's model docstring). `related` is
    symmetric/non-directional in meaning though still stored as one
    directional row; `enables` is directional but, like `related`, is not
    cycle-checked (see docs/adr/0018-prioritization-frameworks-and-dependencies.md
    for why cycle-checking is scoped to `blocks` only in this phase).
    DB-CHECK-constrained — a small, fixed, closed vocabulary."""

    BLOCKS = "blocks"
    RELATED = "related"
    ENABLES = "enables"


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


class MembershipStatus(StrEnum):
    """Controlled vocabulary for OrganizationMembership.status (Phase 12).

    Distinct from User.status: User.status governs whether the ACCOUNT can
    log in at all; MembershipStatus governs whether this particular
    organization membership is currently in effect. A user can be
    ACTIVE (able to log in) while REVOKED from one organization but still
    ACTIVE in another. DB-CHECK-constrained, like UserStatus — a small,
    fixed, closed set with real authorization meaning.
    """

    ACTIVE = "active"
    REVOKED = "revoked"


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

    RISK_CREATE = "risk.create"
    RISK_UPDATE = "risk.update"
    RISK_DELETE = "risk.delete"

    STAKEHOLDER_CREATE = "stakeholder.create"
    STAKEHOLDER_UPDATE = "stakeholder.update"
    STAKEHOLDER_DELETE = "stakeholder.delete"

    SCENARIO_CREATE = "scenario.create"
    SCENARIO_UPDATE = "scenario.update"
    SCENARIO_DELETE = "scenario.delete"
    SCENARIO_OPERATION_CREATE = "scenario_operation.create"
    SCENARIO_OPERATION_UPDATE = "scenario_operation.update"
    SCENARIO_OPERATION_DELETE = "scenario_operation.delete"
    SCENARIO_PRIORITY_OVERRIDE_CREATE = "scenario_priority_override.create"
    SCENARIO_PRIORITY_OVERRIDE_DELETE = "scenario_priority_override.delete"

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

    ORGANIZATION_CREATE = "organization.create"
    ORGANIZATION_UPDATE = "organization.update"
    ORGANIZATION_DEACTIVATE = "organization.deactivate"

    MEMBERSHIP_CREATE = "membership.create"
    MEMBERSHIP_ROLE_CHANGE = "membership.role_change"
    MEMBERSHIP_REVOKE = "membership.revoke"
    MEMBERSHIP_REACTIVATE = "membership.reactivate"

    AUTH_ORGANIZATION_SWITCH = "auth.organization_switch"
    NO_ACTIVE_ORGANIZATION = "organization.no_active_context"
    """Recorded when an authenticated request reaches an organization-scoped
    route with no valid active-organization context (none selected, or the
    membership/organization was revoked/deactivated since login) — the
    Phase 12 counterpart to PERMISSION_DENIED/RESOURCE_ACCESS_DENIED."""

    PRIORITIZATION_FRAMEWORK_CREATE = "prioritization_framework.create"
    PRIORITIZATION_FRAMEWORK_UPDATE = "prioritization_framework.update"
    PRIORITIZATION_FRAMEWORK_DEACTIVATE = "prioritization_framework.deactivate"
    PROJECT_PRIORITY_SCORE_CREATE = "project_priority_score.create"
    PROJECT_PRIORITY_SCORE_UPDATE = "project_priority_score.update"
    PROJECT_PRIORITY_SCORE_DELETE = "project_priority_score.delete"

    PRIORITIZATION_CRITERION_CREATE = "prioritization_criterion.create"
    PRIORITIZATION_CRITERION_UPDATE = "prioritization_criterion.update"
    PRIORITIZATION_CRITERION_DELETE = "prioritization_criterion.delete"
    PROJECT_DEPENDENCY_CREATE = "project_dependency.create"
    PROJECT_DEPENDENCY_DELETE = "project_dependency.delete"
