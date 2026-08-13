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
