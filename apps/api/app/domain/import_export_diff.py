"""Level 2 (record) + Level 3 (domain reference) normalization and diffing
for Phase 6 import/export (CLAUDE.md §39 Phase 6).

Deliberately NOT framework-free in the same sense as app/domain/capacity.py:
this module's whole mechanism is reusing the real app/schemas/*.py Create/
Update Pydantic models for field-level validation (catching
pydantic.ValidationError) instead of duplicating their rules — see
docs/adr/0006-phase-6-import-export.md. It still has no SQLAlchemy and no
FastAPI/I/O: every existing-record fact this module compares against is a
plain frozen dataclass (a *Fact, mirroring app/domain/capacity.py's own
ScheduleFact/etc. pattern) the service layer builds from ORM rows — this
module never sees an ORM instance.
"""

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, NamedTuple, cast

from pydantic import BaseModel, ValidationError

from app.domain.import_export_parsing import (
    coerce_criterion_values_cell,
    coerce_entries_cell,
    coerce_optional_str,
)
from app.models.enums import (
    AllocationUnit,
    AvailabilityType,
    EmploymentStatus,
    MoscowCategory,
    PrioritizationFrameworkType,
    ProjectDependencyType,
    ProjectStatus,
    RiskImpact,
    RiskProbability,
    RiskStatus,
    SkillProficiency,
    StakeholderDecisionAuthority,
    StakeholderInfluence,
    StakeholderInterest,
)
from app.schemas.allocation import AllocationCreate, AllocationUpdate
from app.schemas.availability_exception import (
    AvailabilityExceptionCreate,
    AvailabilityExceptionUpdate,
)
from app.schemas.import_export import ImportErrorCode, ImportFieldError, ImportMode
from app.schemas.person import PersonCreate, PersonUpdate
from app.schemas.person_skill import PersonSkillCreate, PersonSkillUpdate
from app.schemas.prioritization import (
    CriterionValueInput,
    ProjectDependencyCreate,
    ProjectPriorityScoreCreate,
    ProjectPriorityScoreUpdate,
)
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.project_skill_requirement import (
    ProjectSkillRequirementCreate,
    ProjectSkillRequirementUpdate,
)
from app.schemas.risk import RiskCreate, RiskUpdate
from app.schemas.skill import SkillCreate, SkillUpdate
from app.schemas.stakeholder import StakeholderCreate, StakeholderUpdate
from app.schemas.team import TeamCreate, TeamUpdate
from app.schemas.team_membership import TeamMembershipCreate
from app.schemas.working_schedule import (
    WorkingScheduleCreate,
    WorkingScheduleEntryCreate,
    WorkingScheduleUpdate,
)

# ---------------------------------------------------------------------------
# Facts — plain snapshots of existing rows, built by the service layer from
# ORM instances before calling into this module (never an ORM object itself)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PersonFact:
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    display_name: str
    job_title: str | None
    timezone: str
    employment_status: EmploymentStatus


@dataclass(frozen=True)
class TeamFact:
    id: uuid.UUID
    name: str
    description: str | None


@dataclass(frozen=True)
class ProjectFact:
    id: uuid.UUID
    external_id: str | None
    name: str
    description: str | None
    status: ProjectStatus
    start_date: date | None
    end_date: date | None


@dataclass(frozen=True)
class AllocationFact:
    id: uuid.UUID
    external_id: str | None
    person_id: uuid.UUID
    project_id: uuid.UUID
    start_date: date
    end_date: date
    allocation_hours: Decimal
    allocation_unit: AllocationUnit
    notes: str | None


@dataclass(frozen=True)
class WorkingScheduleFact:
    id: uuid.UUID
    external_id: str | None
    person_id: uuid.UUID
    effective_start_date: date | None
    effective_end_date: date | None
    entries: tuple[tuple[int, Decimal], ...]
    """(weekday, hours) pairs — order-independent, compared via a sorted key."""


@dataclass(frozen=True)
class AvailabilityExceptionFact:
    id: uuid.UUID
    external_id: str | None
    person_id: uuid.UUID
    start_date: date
    end_date: date
    availability_type: AvailabilityType
    hours: Decimal | None
    notes: str | None


@dataclass(frozen=True)
class TeamMembershipFact:
    person_id: uuid.UUID
    team_id: uuid.UUID


@dataclass(frozen=True)
class SkillFact:
    id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    is_active: bool


@dataclass(frozen=True)
class PersonSkillFact:
    id: uuid.UUID
    person_id: uuid.UUID
    skill_id: uuid.UUID
    proficiency: SkillProficiency
    notes: str | None


@dataclass(frozen=True)
class ProjectSkillRequirementFact:
    id: uuid.UUID
    project_id: uuid.UUID
    skill_id: uuid.UUID
    required_hours: Decimal
    minimum_proficiency: SkillProficiency | None
    notes: str | None


@dataclass(frozen=True)
class RiskFact:
    id: uuid.UUID
    external_id: str | None
    project_id: uuid.UUID
    description: str
    cause: str | None
    potential_effect: str | None
    probability: RiskProbability
    impact: RiskImpact
    response: str | None
    owner_person_id: uuid.UUID | None
    status: RiskStatus
    review_date: date | None


@dataclass(frozen=True)
class StakeholderFact:
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    person_id: uuid.UUID | None
    role: str
    influence: StakeholderInfluence
    interest: StakeholderInterest
    decision_authority: StakeholderDecisionAuthority
    communication_needs: str | None


@dataclass(frozen=True)
class PrioritizationFrameworkFact:
    id: uuid.UUID
    name: str
    framework_type: PrioritizationFrameworkType
    criterion_keys: frozenset[str]
    """Every PrioritizationCriterion.key belonging to this framework — used
    to validate a submitted criterion_key against the ACTUAL framework
    definition (mirrors ProjectPriorityScoreService._apply_values's own
    "not a criterion of framework" check), never a second copy of the
    formula/weight logic itself."""


@dataclass(frozen=True)
class ProjectPriorityScoreFact:
    id: uuid.UUID
    project_id: uuid.UUID
    framework_id: uuid.UUID
    category: MoscowCategory | None
    notes: str | None
    values: tuple[tuple[str, Decimal], ...]
    """(criterion_key, value) pairs — order-independent, compared via a
    sorted key like WorkingScheduleFact.entries."""


@dataclass(frozen=True)
class ProjectDependencyFact:
    """Just the composite-key fields — a dependency edge has no mutable
    fields at all (see ProjectDependency's model docstring: "created/added
    or removed only"), so this Fact exists purely for existence-checking,
    matching TeamMembershipFact's identical minimal shape."""

    from_project_id: uuid.UUID
    to_project_id: uuid.UUID
    dependency_type: ProjectDependencyType


@dataclass(frozen=True)
class ReferenceLookup:
    """Batch-loaded once per request via repository list_by_ids/
    list_by_emails/list_by_names/list_by_external_ids calls, then passed to
    every normalize/reference-resolution call — never queried per-row
    (CLAUDE.md §27)."""

    people_by_id: Mapping[uuid.UUID, PersonFact]
    people_by_email: Mapping[str, PersonFact]
    teams_by_id: Mapping[uuid.UUID, TeamFact]
    teams_by_name: Mapping[str, TeamFact]
    projects_by_id: Mapping[uuid.UUID, ProjectFact]
    projects_by_external_id: Mapping[str, ProjectFact]
    skills_by_id: Mapping[uuid.UUID, SkillFact]
    skills_by_name: Mapping[str, SkillFact]
    frameworks_by_id: Mapping[uuid.UUID, PrioritizationFrameworkFact]
    frameworks_by_name: Mapping[str, PrioritizationFrameworkFact]


class NormalizeOutcome[PayloadT](NamedTuple):
    action: Literal["create", "update", "unchanged"] | None
    """None when errors is non-empty — the row couldn't be classified."""
    payload: PayloadT | None
    matched_id: uuid.UUID | None
    identity: str | None
    """The identity used to match this row, e.g. "email=jane@x.com". None
    when the entity has no natural key and the row would always create."""
    errors: list[ImportFieldError]


class TeamMembershipPayload(NamedTuple):
    """TeamMembershipCreate only carries person_id (team_id normally comes
    from the URL path in the real API) — this wrapper carries the resolved
    team_id alongside it so ImportService.apply has everything it needs to
    call TeamMembershipService.add_member(team_id, data)."""

    team_id: uuid.UUID
    data: TeamMembershipCreate


class PersonSkillPayload(NamedTuple):
    """PersonSkillCreate/Update only carry skill_id/proficiency/notes
    (person_id normally comes from the URL path) — this wrapper carries the
    resolved person_id alongside it, the same reason TeamMembershipPayload
    exists, but for BOTH create and update since PersonSkillService.update
    also takes person_id (for its ownership check)."""

    person_id: uuid.UUID
    data: PersonSkillCreate | PersonSkillUpdate


class ProjectSkillRequirementPayload(NamedTuple):
    project_id: uuid.UUID
    data: ProjectSkillRequirementCreate | ProjectSkillRequirementUpdate


class RiskPayload(NamedTuple):
    """RiskCreate/Update only carry the fields on the Risk row itself
    (project_id normally comes from the URL path) — this wrapper carries
    the resolved project_id alongside it, the same reason
    ProjectSkillRequirementPayload exists."""

    project_id: uuid.UUID
    data: RiskCreate | RiskUpdate


class StakeholderPayload(NamedTuple):
    project_id: uuid.UUID
    data: StakeholderCreate | StakeholderUpdate


class ProjectPriorityScorePayload(NamedTuple):
    project_id: uuid.UUID
    data: ProjectPriorityScoreCreate | ProjectPriorityScoreUpdate


class ProjectDependencyPayload(NamedTuple):
    """ProjectDependencyCreate only carries to_project_id/dependency_type
    (from_project_id normally comes from the URL path) — this wrapper
    carries the resolved from_project_id alongside it, the same reason
    ProjectSkillRequirementPayload exists. Always a "create" — there is no
    update case (see ProjectDependencyFact's docstring)."""

    from_project_id: uuid.UUID
    data: ProjectDependencyCreate


# ---------------------------------------------------------------------------
# Reference resolution — literal UUID -> natural key -> INVALID_REFERENCE,
# never a soft skip (docs/adr/0006-phase-6-import-export.md)
# ---------------------------------------------------------------------------


def _parse_uuid(raw: str, field: str) -> uuid.UUID | ImportFieldError:
    try:
        return uuid.UUID(raw)
    except ValueError:
        return ImportFieldError(
            field=field,
            code=ImportErrorCode.INVALID_REFERENCE,
            message=f"'{raw}' is not a valid id.",
        )


def resolve_person_reference(
    row: Mapping[str, object], lookup: ReferenceLookup
) -> uuid.UUID | ImportFieldError:
    id_raw = coerce_optional_str(row.get("person_id"))
    if id_raw:
        parsed = _parse_uuid(id_raw, "person_id")
        if isinstance(parsed, ImportFieldError):
            return parsed
        fact = lookup.people_by_id.get(parsed)
        if fact is None:
            return ImportFieldError(
                field="person_id", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No person with id {id_raw}.",
            )
        return fact.id
    email = coerce_optional_str(row.get("person_email"))
    if email:
        fact = lookup.people_by_email.get(email)
        if fact is None:
            return ImportFieldError(
                field="person_email", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No person with email {email}.",
            )
        return fact.id
    return ImportFieldError(
        field=None, code=ImportErrorCode.INVALID_REFERENCE,
        message="Provide person_id or person_email.",
    )


def resolve_project_reference(
    row: Mapping[str, object], lookup: ReferenceLookup
) -> uuid.UUID | ImportFieldError:
    id_raw = coerce_optional_str(row.get("project_id"))
    if id_raw:
        parsed = _parse_uuid(id_raw, "project_id")
        if isinstance(parsed, ImportFieldError):
            return parsed
        fact = lookup.projects_by_id.get(parsed)
        if fact is None:
            return ImportFieldError(
                field="project_id", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No project with id {id_raw}.",
            )
        return fact.id
    external_id = coerce_optional_str(row.get("project_external_id"))
    if external_id:
        fact = lookup.projects_by_external_id.get(external_id)
        if fact is None:
            return ImportFieldError(
                field="project_external_id", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No project with external_id {external_id}.",
            )
        return fact.id
    return ImportFieldError(
        field=None, code=ImportErrorCode.INVALID_REFERENCE,
        message="Provide project_id or project_external_id.",
    )


def resolve_named_project_reference(
    row: Mapping[str, object], lookup: ReferenceLookup, *, id_field: str, external_id_field: str
) -> uuid.UUID | ImportFieldError:
    """Like resolve_project_reference, but for a row needing MORE THAN ONE
    project reference under different column names — ProjectDependency's
    from_project_id/from_project_external_id and
    to_project_id/to_project_external_id both resolve through this, since
    the plain resolve_project_reference is hardcoded to the single
    "project_id"/"project_external_id" pair every other entity uses."""
    id_raw = coerce_optional_str(row.get(id_field))
    if id_raw:
        parsed = _parse_uuid(id_raw, id_field)
        if isinstance(parsed, ImportFieldError):
            return parsed
        fact = lookup.projects_by_id.get(parsed)
        if fact is None:
            return ImportFieldError(
                field=id_field, code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No project with id {id_raw}.",
            )
        return fact.id
    external_id = coerce_optional_str(row.get(external_id_field))
    if external_id:
        fact = lookup.projects_by_external_id.get(external_id)
        if fact is None:
            return ImportFieldError(
                field=external_id_field, code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No project with external_id {external_id}.",
            )
        return fact.id
    return ImportFieldError(
        field=None, code=ImportErrorCode.INVALID_REFERENCE,
        message=f"Provide {id_field} or {external_id_field}.",
    )


def resolve_team_reference(
    row: Mapping[str, object], lookup: ReferenceLookup
) -> uuid.UUID | ImportFieldError:
    id_raw = coerce_optional_str(row.get("team_id"))
    if id_raw:
        parsed = _parse_uuid(id_raw, "team_id")
        if isinstance(parsed, ImportFieldError):
            return parsed
        fact = lookup.teams_by_id.get(parsed)
        if fact is None:
            return ImportFieldError(
                field="team_id", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No team with id {id_raw}.",
            )
        return fact.id
    name = coerce_optional_str(row.get("team_name"))
    if name:
        fact = lookup.teams_by_name.get(name)
        if fact is None:
            return ImportFieldError(
                field="team_name", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No team named '{name}'.",
            )
        return fact.id
    return ImportFieldError(
        field=None, code=ImportErrorCode.INVALID_REFERENCE,
        message="Provide team_id or team_name.",
    )


def resolve_skill_reference(
    row: Mapping[str, object], lookup: ReferenceLookup
) -> uuid.UUID | ImportFieldError:
    id_raw = coerce_optional_str(row.get("skill_id"))
    if id_raw:
        parsed = _parse_uuid(id_raw, "skill_id")
        if isinstance(parsed, ImportFieldError):
            return parsed
        fact = lookup.skills_by_id.get(parsed)
        if fact is None:
            return ImportFieldError(
                field="skill_id", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No skill with id {id_raw}.",
            )
        return fact.id
    name = coerce_optional_str(row.get("skill_name"))
    if name:
        fact = lookup.skills_by_name.get(name)
        if fact is None:
            return ImportFieldError(
                field="skill_name", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No skill named '{name}'.",
            )
        return fact.id
    return ImportFieldError(
        field=None, code=ImportErrorCode.INVALID_REFERENCE,
        message="Provide skill_id or skill_name.",
    )


def resolve_optional_person_reference(
    row: Mapping[str, object], lookup: ReferenceLookup, *, id_field: str, email_field: str
) -> uuid.UUID | None | ImportFieldError:
    """Like resolve_person_reference, but the reference is OPTIONAL —
    absence of both columns returns None (not an error). Used for Risk's
    owner_person_id/owner_person_email and Stakeholder's person_id/
    person_email, whose underlying model column is nullable (unlike
    person_id/team_id/project_id/skill_id, which are always required
    wherever they're used). A malformed or unresolvable reference is
    still a blocking error — only genuine absence is tolerated."""
    id_raw = coerce_optional_str(row.get(id_field))
    if id_raw:
        parsed = _parse_uuid(id_raw, id_field)
        if isinstance(parsed, ImportFieldError):
            return parsed
        fact = lookup.people_by_id.get(parsed)
        if fact is None:
            return ImportFieldError(
                field=id_field, code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No person with id {id_raw}.",
            )
        return fact.id
    email = coerce_optional_str(row.get(email_field))
    if email:
        fact = lookup.people_by_email.get(email)
        if fact is None:
            return ImportFieldError(
                field=email_field, code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No person with email {email}.",
            )
        return fact.id
    return None


def resolve_framework_reference(
    row: Mapping[str, object], lookup: ReferenceLookup
) -> uuid.UUID | ImportFieldError:
    id_raw = coerce_optional_str(row.get("framework_id"))
    if id_raw:
        parsed = _parse_uuid(id_raw, "framework_id")
        if isinstance(parsed, ImportFieldError):
            return parsed
        fact = lookup.frameworks_by_id.get(parsed)
        if fact is None:
            return ImportFieldError(
                field="framework_id", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No prioritization framework with id {id_raw}.",
            )
        return fact.id
    name = coerce_optional_str(row.get("framework_name"))
    if name:
        fact = lookup.frameworks_by_name.get(name)
        if fact is None:
            return ImportFieldError(
                field="framework_name", code=ImportErrorCode.INVALID_REFERENCE,
                message=f"No prioritization framework named '{name}'.",
            )
        return fact.id
    return ImportFieldError(
        field=None, code=ImportErrorCode.INVALID_REFERENCE,
        message="Provide framework_id or framework_name.",
    )


def _unchanged(payload: BaseModel, current: BaseModel, *, exclude: set[str] | None = None) -> bool:
    """True iff every field the row actually supplied (payload's "set"
    fields — see model_validate's model_fields_set) matches the current
    value. Fields the row left blank are excluded from both this comparison
    and the update itself: every existing XxxService.update() already does
    `data.model_dump(exclude_unset=True)`, so a blank cell means "leave
    this field alone," never "clear it to None" — a blank cell clearing a
    NOT NULL column (e.g. Project.status) would otherwise raise an
    IntegrityError. Compared via JSON-mode dumps (the same Decimal/date/
    enum -> JSON-safe-string serialization operation_payload_to_dict
    already relies on for scenario payloads) so a Decimal("8") vs
    Decimal("8.00") formatting difference doesn't register as a false
    "changed". `exclude` skips fields compared separately by the caller
    (e.g. WorkingSchedule's order-independent entries)."""
    supplied = payload.model_dump(mode="json", exclude_unset=True, exclude=exclude or set())
    if not supplied:
        return True
    current_subset = current.model_dump(mode="json", include=set(supplied.keys()))
    return supplied == current_subset


def _present_fields(fields: Mapping[str, object | None]) -> dict[str, object]:
    """The subset of a raw fields dict whose values were actually supplied
    (non-blank) — used to build an Update payload with correct
    model_fields_set semantics (see _unchanged)."""
    return {k: v for k, v in fields.items() if v is not None}


def _reference_display(row: Mapping[str, object], id_field: str, natural_field: str) -> str:
    natural = coerce_optional_str(row.get(natural_field))
    if natural:
        return f"{natural_field}={natural}"
    return f"{id_field}={coerce_optional_str(row.get(id_field))}"


_CONSTRAINT_ERROR_TYPES = {
    "value_error",
    "greater_than",
    "greater_than_equal",
    "less_than",
    "less_than_equal",
    "too_short",
    "too_long",
    "string_too_short",
    "string_too_long",
}
"""pydantic-core error "type" values that represent a value being the
right shape but outside an allowed range/length — e.g. Field(ge=0) — as
distinct from "missing" (FIELD_REQUIRED) or a genuine type mismatch
(FIELD_TYPE_INVALID, the catch-all)."""


def _validation_errors(exc: ValidationError) -> list[ImportFieldError]:
    errors: list[ImportFieldError] = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"]) or None
        if error["type"] == "missing":
            code = ImportErrorCode.FIELD_REQUIRED
        elif error["type"] in _CONSTRAINT_ERROR_TYPES:
            code = ImportErrorCode.FIELD_CONSTRAINT_VIOLATED
        else:
            code = ImportErrorCode.FIELD_TYPE_INVALID
        errors.append(ImportFieldError(field=field, code=code, message=error["msg"]))
    return errors


def apply_mode_policy[T](outcome: NormalizeOutcome[T], mode: ImportMode) -> NormalizeOutcome[T]:
    """Reclassifies an outcome per the requested ImportMode. Applied uniformly
    after every normalize_*_row call — never duplicated per entity."""
    if outcome.errors or outcome.action is None:
        return outcome
    if mode == ImportMode.CREATE_ONLY and outcome.action in ("update", "unchanged"):
        return NormalizeOutcome(
            None, None, outcome.matched_id, outcome.identity,
            [ImportFieldError(
                field=None, code=ImportErrorCode.CONFLICT,
                message="A matching record already exists (create_only mode).",
            )],
        )
    if mode == ImportMode.UPDATE_ONLY and outcome.action == "create":
        return NormalizeOutcome(
            None, None, None, outcome.identity,
            [ImportFieldError(
                field=None, code=ImportErrorCode.NO_MATCH_FOR_UPDATE_ONLY,
                message="No matching record found (update_only mode).",
            )],
        )
    return outcome


# ---------------------------------------------------------------------------
# Person — matched by email (always present; required column)
# ---------------------------------------------------------------------------


def normalize_person_row(
    row: Mapping[str, object], lookup: ReferenceLookup
) -> NormalizeOutcome[PersonCreate | PersonUpdate]:
    email = coerce_optional_str(row.get("email"))
    existing = lookup.people_by_email.get(email) if email else None
    identity = f"email={email}" if email else None

    fields = {
        "first_name": coerce_optional_str(row.get("first_name")),
        "last_name": coerce_optional_str(row.get("last_name")),
        "display_name": coerce_optional_str(row.get("display_name")),
        "email": email,
        "job_title": coerce_optional_str(row.get("job_title")),
        "timezone": coerce_optional_str(row.get("timezone")),
        "employment_status": coerce_optional_str(row.get("employment_status")),
    }

    if existing is None:
        try:
            payload = PersonCreate.model_validate(
                {k: v for k, v in fields.items() if v is not None}
            )
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome("create", payload, None, identity, [])

    try:
        payload = PersonUpdate.model_validate(_present_fields(fields))
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = PersonUpdate(
        first_name=existing.first_name, last_name=existing.last_name,
        display_name=existing.display_name, email=existing.email,
        job_title=existing.job_title, timezone=existing.timezone,
        employment_status=existing.employment_status,
    )
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(action, payload, existing.id, identity, [])


# ---------------------------------------------------------------------------
# Team — matched by name (always present; required column)
# ---------------------------------------------------------------------------


def normalize_team_row(
    row: Mapping[str, object], lookup: ReferenceLookup
) -> NormalizeOutcome[TeamCreate | TeamUpdate]:
    name = coerce_optional_str(row.get("name"))
    existing = lookup.teams_by_name.get(name) if name else None
    identity = f"name={name}" if name else None
    description = coerce_optional_str(row.get("description"))

    if existing is None:
        fields = {"name": name, "description": description}
        try:
            payload = TeamCreate.model_validate({k: v for k, v in fields.items() if v is not None})
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome("create", payload, None, identity, [])

    try:
        payload = TeamUpdate.model_validate(
            _present_fields({"name": name, "description": description})
        )
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = TeamUpdate(name=existing.name, description=existing.description)
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(action, payload, existing.id, identity, [])


# ---------------------------------------------------------------------------
# TeamMembership — matched by the resolved (person_id, team_id) pair, never
# an "update" (no mutable fields)
# ---------------------------------------------------------------------------


def normalize_team_membership_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing_memberships: Mapping[tuple[uuid.UUID, uuid.UUID], TeamMembershipFact],
) -> NormalizeOutcome[TeamMembershipPayload]:
    person_ref = resolve_person_reference(row, lookup)
    if isinstance(person_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [person_ref])
    team_ref = resolve_team_reference(row, lookup)
    if isinstance(team_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [team_ref])

    identity = (
        f"{_reference_display(row, 'person_id', 'person_email')},"
        f"{_reference_display(row, 'team_id', 'team_name')}"
    )
    if (person_ref, team_ref) in existing_memberships:
        return NormalizeOutcome("unchanged", None, None, identity, [])
    payload = TeamMembershipPayload(
        team_id=team_ref, data=TeamMembershipCreate(person_id=person_ref)
    )
    return NormalizeOutcome("create", payload, None, identity, [])


# ---------------------------------------------------------------------------
# Project — matched by external_id if given; no fallback to name (not
# unique)
# ---------------------------------------------------------------------------


def normalize_project_row(
    row: Mapping[str, object], existing_by_external_id: Mapping[str, ProjectFact]
) -> NormalizeOutcome[ProjectCreate | ProjectUpdate]:
    external_id = coerce_optional_str(row.get("external_id"))
    existing = existing_by_external_id.get(external_id) if external_id else None
    identity = f"external_id={external_id}" if external_id else None

    fields = {
        "name": coerce_optional_str(row.get("name")),
        "description": coerce_optional_str(row.get("description")),
        "status": coerce_optional_str(row.get("status")),
        "start_date": coerce_optional_str(row.get("start_date")),
        "end_date": coerce_optional_str(row.get("end_date")),
        "external_id": external_id,
    }

    if existing is None:
        try:
            payload = ProjectCreate.model_validate(
                {k: v for k, v in fields.items() if v is not None}
            )
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome("create", payload, None, identity, [])

    try:
        payload = ProjectUpdate.model_validate(_present_fields(fields))
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = ProjectUpdate(
        name=existing.name,
        description=existing.description,
        status=existing.status,
        start_date=existing.start_date,
        end_date=existing.end_date,
        external_id=existing.external_id,
    )
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(action, payload, existing.id, identity, [])


# ---------------------------------------------------------------------------
# Allocation — matched by external_id if given; reference resolution only
# needed on the create path (AllocationUpdate can't reassign person/project)
# ---------------------------------------------------------------------------


def normalize_allocation_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing_by_external_id: Mapping[str, AllocationFact],
) -> NormalizeOutcome[AllocationCreate | AllocationUpdate]:
    external_id = coerce_optional_str(row.get("external_id"))
    existing = existing_by_external_id.get(external_id) if external_id else None
    identity = f"external_id={external_id}" if external_id else None

    fields = {
        "start_date": coerce_optional_str(row.get("start_date")),
        "end_date": coerce_optional_str(row.get("end_date")),
        "allocation_hours": coerce_optional_str(row.get("allocation_hours")),
        "allocation_unit": coerce_optional_str(row.get("allocation_unit")),
        "notes": coerce_optional_str(row.get("notes")),
        "external_id": external_id,
    }

    if existing is None:
        person_ref = resolve_person_reference(row, lookup)
        if isinstance(person_ref, ImportFieldError):
            return NormalizeOutcome(None, None, None, identity, [person_ref])
        project_ref = resolve_project_reference(row, lookup)
        if isinstance(project_ref, ImportFieldError):
            return NormalizeOutcome(None, None, None, identity, [project_ref])
        try:
            payload = AllocationCreate.model_validate(
                {
                    "person_id": person_ref,
                    "project_id": project_ref,
                    **{k: v for k, v in fields.items() if v is not None},
                }
            )
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome("create", payload, None, identity, [])

    try:
        payload = AllocationUpdate.model_validate(_present_fields(fields))
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = AllocationUpdate(
        start_date=existing.start_date, end_date=existing.end_date,
        allocation_hours=existing.allocation_hours, allocation_unit=existing.allocation_unit,
        notes=existing.notes, external_id=existing.external_id,
    )
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(action, payload, existing.id, identity, [])


# ---------------------------------------------------------------------------
# WorkingSchedule — matched by external_id if given. entries always
# full-replace on update (mirrors WorkingScheduleUpdate's own semantics).
# ---------------------------------------------------------------------------


def _entries_key(entries: Sequence[WorkingScheduleEntryCreate]) -> tuple[tuple[int, str], ...]:
    """Order-independent comparison key: sorted (weekday, hours-as-string)
    pairs. Compared as strings (not Decimal) so trailing-zero formatting
    differences (e.g. "8" vs "8.00") are treated as a real change, matching
    the exact value a re-export would have written."""
    return tuple(sorted((entry.weekday, str(entry.hours)) for entry in entries))


def _values_key(values: Sequence[CriterionValueInput]) -> tuple[tuple[str, str], ...]:
    """Order-independent comparison key for ProjectPriorityScore's
    criterion values — same rationale as _entries_key (compared as
    strings, not Decimal, so formatting differences count as a change)."""
    return tuple(sorted((item.criterion_key, str(item.value)) for item in values))


def normalize_working_schedule_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing_by_external_id: Mapping[str, WorkingScheduleFact],
) -> NormalizeOutcome[WorkingScheduleCreate | WorkingScheduleUpdate]:
    external_id = coerce_optional_str(row.get("external_id"))
    existing = existing_by_external_id.get(external_id) if external_id else None
    identity = f"external_id={external_id}" if external_id else None

    entries_raw = row.get("entries")
    entries_error: str | None = None
    entries: list[WorkingScheduleEntryCreate] | None = None
    try:
        if isinstance(entries_raw, list):
            raw_entries = cast(list[object], entries_raw)
            entries = [WorkingScheduleEntryCreate.model_validate(entry) for entry in raw_entries]
        elif isinstance(entries_raw, str) and entries_raw.strip():
            entries = [
                WorkingScheduleEntryCreate.model_validate(entry)
                for entry in coerce_entries_cell(entries_raw)
            ]
        else:
            entries = None
    except ValidationError as exc:
        entries_error = "; ".join(e["msg"] for e in exc.errors())
    except ValueError as exc:
        entries_error = str(exc)

    if entries_error is not None:
        message = entries_error
        return NormalizeOutcome(
            None,
            None,
            existing.id if existing else None,
            identity,
            [
                ImportFieldError(
                    field="entries", code=ImportErrorCode.FIELD_TYPE_INVALID, message=message
                )
            ],
        )

    effective_start = coerce_optional_str(row.get("effective_start_date"))
    effective_end = coerce_optional_str(row.get("effective_end_date"))

    if existing is None:
        person_ref = resolve_person_reference(row, lookup)
        if isinstance(person_ref, ImportFieldError):
            return NormalizeOutcome(None, None, None, identity, [person_ref])
        if entries is None:
            return NormalizeOutcome(
                None,
                None,
                None,
                identity,
                [
                    ImportFieldError(
                        field="entries",
                        code=ImportErrorCode.FIELD_REQUIRED,
                        message="Field required",
                    )
                ],
            )
        try:
            payload = WorkingScheduleCreate.model_validate(
                {
                    "person_id": person_ref,
                    "entries": entries,
                    "external_id": external_id,
                    **{
                        k: v
                        for k, v in {
                            "effective_start_date": effective_start,
                            "effective_end_date": effective_end,
                        }.items()
                        if v is not None
                    },
                }
            )
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome("create", payload, None, identity, [])

    # entries is always included (even None) — WorkingScheduleService.update
    # already excludes it from the generic exclude_unset setattr loop and
    # only touches it via the dedicated `if data.entries is not None`
    # branch, so passing entries=None here is safe and means "leave the
    # entries alone," matching every other blank-means-untouched field.
    update_kwargs: dict[str, object] = {
        "entries": entries,
        **_present_fields(
            {"effective_start_date": effective_start, "effective_end_date": effective_end}
        ),
    }
    if external_id is not None:
        update_kwargs["external_id"] = external_id
    try:
        payload = WorkingScheduleUpdate.model_validate(update_kwargs)
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = WorkingScheduleUpdate(
        effective_start_date=existing.effective_start_date,
        effective_end_date=existing.effective_end_date,
        entries=[
            WorkingScheduleEntryCreate(weekday=weekday, hours=hours)
            for weekday, hours in existing.entries
        ],
        external_id=existing.external_id,
    )
    same_dates = _unchanged(payload, current, exclude={"entries"})
    same_entries = entries is None or _entries_key(entries) == _entries_key(
        current.entries or []
    )
    action = "unchanged" if same_dates and same_entries else "update"
    return NormalizeOutcome(action, payload, existing.id, identity, [])


# ---------------------------------------------------------------------------
# AvailabilityException — matched by external_id if given
# ---------------------------------------------------------------------------


def normalize_availability_exception_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing_by_external_id: Mapping[str, AvailabilityExceptionFact],
) -> NormalizeOutcome[AvailabilityExceptionCreate | AvailabilityExceptionUpdate]:
    external_id = coerce_optional_str(row.get("external_id"))
    existing = existing_by_external_id.get(external_id) if external_id else None
    identity = f"external_id={external_id}" if external_id else None

    fields = {
        "start_date": coerce_optional_str(row.get("start_date")),
        "end_date": coerce_optional_str(row.get("end_date")),
        "availability_type": coerce_optional_str(row.get("availability_type")),
        "hours": coerce_optional_str(row.get("hours")),
        "notes": coerce_optional_str(row.get("notes")),
        "external_id": external_id,
    }

    if existing is None:
        person_ref = resolve_person_reference(row, lookup)
        if isinstance(person_ref, ImportFieldError):
            return NormalizeOutcome(None, None, None, identity, [person_ref])
        try:
            payload = AvailabilityExceptionCreate.model_validate(
                {
                    "person_id": person_ref,
                    **{k: v for k, v in fields.items() if v is not None},
                }
            )
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome("create", payload, None, identity, [])

    try:
        payload = AvailabilityExceptionUpdate.model_validate(_present_fields(fields))
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = AvailabilityExceptionUpdate(
        start_date=existing.start_date, end_date=existing.end_date,
        availability_type=existing.availability_type, hours=existing.hours,
        notes=existing.notes, external_id=existing.external_id,
    )
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(action, payload, existing.id, identity, [])


# ---------------------------------------------------------------------------
# Skill — matched by name (Phase 7). is_active on a CREATE row is ignored
# (SkillCreate has no such field — a newly imported skill always starts
# active); is_active on an UPDATE row can deactivate/reactivate an existing
# skill, same as the API's PATCH endpoint.
# ---------------------------------------------------------------------------


def normalize_skill_row(
    row: Mapping[str, object], existing_by_name: Mapping[str, SkillFact]
) -> NormalizeOutcome[SkillCreate | SkillUpdate]:
    name = coerce_optional_str(row.get("name"))
    existing = existing_by_name.get(name) if name else None
    identity = f"name={name}" if name else None
    description = coerce_optional_str(row.get("description"))
    category = coerce_optional_str(row.get("category"))

    if existing is None:
        fields = {"name": name, "description": description, "category": category}
        try:
            payload = SkillCreate.model_validate(
                {k: v for k, v in fields.items() if v is not None}
            )
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome("create", payload, None, identity, [])

    is_active = coerce_optional_str(row.get("is_active"))
    fields = {
        "name": name, "description": description, "category": category, "is_active": is_active,
    }
    try:
        payload = SkillUpdate.model_validate(_present_fields(fields))
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = SkillUpdate(
        name=existing.name, description=existing.description, category=existing.category,
        is_active=existing.is_active,
    )
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(action, payload, existing.id, identity, [])


# ---------------------------------------------------------------------------
# PersonSkill — matched by the resolved (person_id, skill_id) pair; HAS an
# update path (proficiency/notes are mutable), unlike TeamMembership.
# ---------------------------------------------------------------------------


def normalize_person_skill_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing_by_pair: Mapping[tuple[uuid.UUID, uuid.UUID], PersonSkillFact],
) -> NormalizeOutcome[PersonSkillPayload]:
    person_ref = resolve_person_reference(row, lookup)
    if isinstance(person_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [person_ref])
    skill_ref = resolve_skill_reference(row, lookup)
    if isinstance(skill_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [skill_ref])

    identity = (
        f"{_reference_display(row, 'person_id', 'person_email')},"
        f"{_reference_display(row, 'skill_id', 'skill_name')}"
    )
    existing = existing_by_pair.get((person_ref, skill_ref))
    fields = {
        "proficiency": coerce_optional_str(row.get("proficiency")),
        "notes": coerce_optional_str(row.get("notes")),
    }

    if existing is None:
        skill_fact = lookup.skills_by_id.get(skill_ref)
        if skill_fact is not None and not skill_fact.is_active:
            return NormalizeOutcome(
                None, None, None, identity,
                [ImportFieldError(
                    field="skill_id", code=ImportErrorCode.DOMAIN_RULE_VIOLATED,
                    message=f"Skill '{skill_fact.name}' is not active.",
                )],
            )
        try:
            payload = PersonSkillCreate.model_validate(
                {"skill_id": skill_ref, **{k: v for k, v in fields.items() if v is not None}}
            )
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome(
            "create", PersonSkillPayload(person_id=person_ref, data=payload), None, identity, []
        )

    try:
        payload = PersonSkillUpdate.model_validate(_present_fields(fields))
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = PersonSkillUpdate(proficiency=existing.proficiency, notes=existing.notes)
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(
        action, PersonSkillPayload(person_id=person_ref, data=payload), existing.id, identity, []
    )


# ---------------------------------------------------------------------------
# ProjectSkillRequirement — matched by the resolved (project_id, skill_id)
# pair; has an update path (required_hours/minimum_proficiency/notes).
# ---------------------------------------------------------------------------


def normalize_project_skill_requirement_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing_by_pair: Mapping[tuple[uuid.UUID, uuid.UUID], ProjectSkillRequirementFact],
) -> NormalizeOutcome[ProjectSkillRequirementPayload]:
    project_ref = resolve_project_reference(row, lookup)
    if isinstance(project_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [project_ref])
    skill_ref = resolve_skill_reference(row, lookup)
    if isinstance(skill_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [skill_ref])

    identity = (
        f"{_reference_display(row, 'project_id', 'project_external_id')},"
        f"{_reference_display(row, 'skill_id', 'skill_name')}"
    )
    existing = existing_by_pair.get((project_ref, skill_ref))
    fields = {
        "required_hours": coerce_optional_str(row.get("required_hours")),
        "minimum_proficiency": coerce_optional_str(row.get("minimum_proficiency")),
        "notes": coerce_optional_str(row.get("notes")),
    }

    if existing is None:
        skill_fact = lookup.skills_by_id.get(skill_ref)
        if skill_fact is not None and not skill_fact.is_active:
            return NormalizeOutcome(
                None, None, None, identity,
                [ImportFieldError(
                    field="skill_id", code=ImportErrorCode.DOMAIN_RULE_VIOLATED,
                    message=f"Skill '{skill_fact.name}' is not active.",
                )],
            )
        try:
            payload = ProjectSkillRequirementCreate.model_validate(
                {"skill_id": skill_ref, **{k: v for k, v in fields.items() if v is not None}}
            )
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome(
            "create",
            ProjectSkillRequirementPayload(project_id=project_ref, data=payload),
            None, identity, [],
        )

    try:
        payload = ProjectSkillRequirementUpdate.model_validate(_present_fields(fields))
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = ProjectSkillRequirementUpdate(
        required_hours=existing.required_hours,
        minimum_proficiency=existing.minimum_proficiency,
        notes=existing.notes,
    )
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(
        action,
        ProjectSkillRequirementPayload(project_id=project_ref, data=payload),
        existing.id, identity, [],
    )


# ---------------------------------------------------------------------------
# Risk (Phase 36) — matched by external_id if given, mirroring Allocation's
# exact self-identity pattern; owner_person_id is an OPTIONAL reference
# (resolve_optional_person_reference), unlike every REQUIRED reference above.
# ---------------------------------------------------------------------------


def normalize_risk_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing_by_external_id: Mapping[str, RiskFact],
) -> NormalizeOutcome[RiskPayload]:
    external_id = coerce_optional_str(row.get("external_id"))
    existing = existing_by_external_id.get(external_id) if external_id else None
    identity = f"external_id={external_id}" if external_id else None

    owner_ref = resolve_optional_person_reference(
        row, lookup, id_field="owner_person_id", email_field="owner_person_email"
    )
    if isinstance(owner_ref, ImportFieldError):
        return NormalizeOutcome(
            None, None, existing.id if existing else None, identity, [owner_ref]
        )

    fields: dict[str, object | None] = {
        "description": coerce_optional_str(row.get("description")),
        "cause": coerce_optional_str(row.get("cause")),
        "potential_effect": coerce_optional_str(row.get("potential_effect")),
        "probability": coerce_optional_str(row.get("probability")),
        "impact": coerce_optional_str(row.get("impact")),
        "response": coerce_optional_str(row.get("response")),
        "owner_person_id": owner_ref,
        "status": coerce_optional_str(row.get("status")),
        "review_date": coerce_optional_str(row.get("review_date")),
        "external_id": external_id,
    }

    if existing is None:
        project_ref = resolve_project_reference(row, lookup)
        if isinstance(project_ref, ImportFieldError):
            return NormalizeOutcome(None, None, None, identity, [project_ref])
        try:
            payload = RiskCreate.model_validate(_present_fields(fields))
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome(
            "create", RiskPayload(project_id=project_ref, data=payload), None, identity, []
        )

    try:
        payload = RiskUpdate.model_validate(_present_fields(fields))
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = RiskUpdate(
        description=existing.description, cause=existing.cause,
        potential_effect=existing.potential_effect, probability=existing.probability,
        impact=existing.impact, response=existing.response,
        owner_person_id=existing.owner_person_id, status=existing.status,
        review_date=existing.review_date, external_id=existing.external_id,
    )
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(
        action, RiskPayload(project_id=existing.project_id, data=payload), existing.id, identity, []
    )


# ---------------------------------------------------------------------------
# Stakeholder (Phase 36) — matched by the resolved (project_id, person_id)
# pair when person_id is given (mirroring ProjectSkillRequirement's
# composite-key pattern); a row with no person reference has no natural
# key at all and always creates, matching Project/Allocation's "no
# external_id -> always creates" precedent for the same reason.
# ---------------------------------------------------------------------------


def normalize_stakeholder_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing_by_pair: Mapping[tuple[uuid.UUID, uuid.UUID], StakeholderFact],
) -> NormalizeOutcome[StakeholderPayload]:
    project_ref = resolve_project_reference(row, lookup)
    if isinstance(project_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [project_ref])
    person_ref = resolve_optional_person_reference(
        row, lookup, id_field="person_id", email_field="person_email"
    )
    if isinstance(person_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [person_ref])

    # None (not a compound string) when there's no person reference — this
    # row has no natural key at all (matches Project/Allocation's own "no
    # external_id -> identity=None" convention), so
    # _flag_duplicate_identities correctly never treats two different
    # person-less stakeholder rows on the same project as colliding.
    identity = (
        f"{_reference_display(row, 'project_id', 'project_external_id')},"
        f"{_reference_display(row, 'person_id', 'person_email')}"
        if person_ref is not None
        else None
    )
    existing = existing_by_pair.get((project_ref, person_ref)) if person_ref is not None else None
    fields: dict[str, object | None] = {
        "name": coerce_optional_str(row.get("name")),
        "person_id": person_ref,
        "role": coerce_optional_str(row.get("role")),
        "influence": coerce_optional_str(row.get("influence")),
        "interest": coerce_optional_str(row.get("interest")),
        "decision_authority": coerce_optional_str(row.get("decision_authority")),
        "communication_needs": coerce_optional_str(row.get("communication_needs")),
    }

    if existing is None:
        try:
            payload = StakeholderCreate.model_validate(_present_fields(fields))
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome(
            "create", StakeholderPayload(project_id=project_ref, data=payload), None, identity, []
        )

    try:
        payload = StakeholderUpdate.model_validate(_present_fields(fields))
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = StakeholderUpdate(
        name=existing.name, person_id=existing.person_id, role=existing.role,
        influence=existing.influence, interest=existing.interest,
        decision_authority=existing.decision_authority,
        communication_needs=existing.communication_needs,
    )
    action = "unchanged" if _unchanged(payload, current) else "update"
    return NormalizeOutcome(
        action, StakeholderPayload(project_id=project_ref, data=payload), existing.id, identity, []
    )


# ---------------------------------------------------------------------------
# ProjectPriorityScore (Phase 36) — matched by the resolved
# (project_id, framework_id) pair, mirroring ProjectSkillRequirement's
# composite-key pattern exactly (ProjectPriorityScore has the identical
# UniqueConstraint("project_id", "framework_id") shape). category is
# MOSCOW-only, values is every other framework_type's input — which one
# is meaningful is validated against the resolved framework's own
# framework_type/criteria, never re-decided here.
# ---------------------------------------------------------------------------


def normalize_project_priority_score_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing_by_pair: Mapping[tuple[uuid.UUID, uuid.UUID], ProjectPriorityScoreFact],
) -> NormalizeOutcome[ProjectPriorityScorePayload]:
    project_ref = resolve_project_reference(row, lookup)
    if isinstance(project_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [project_ref])
    framework_ref = resolve_framework_reference(row, lookup)
    if isinstance(framework_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [framework_ref])
    framework_fact = lookup.frameworks_by_id[framework_ref]

    identity = (
        f"{_reference_display(row, 'project_id', 'project_external_id')},"
        f"{_reference_display(row, 'framework_id', 'framework_name')}"
    )
    existing = existing_by_pair.get((project_ref, framework_ref))

    category_raw = coerce_optional_str(row.get("category"))
    category: MoscowCategory | None = None
    if category_raw is not None:
        try:
            category = MoscowCategory(category_raw)
        except ValueError:
            return NormalizeOutcome(
                None, None, existing.id if existing else None, identity,
                [ImportFieldError(
                    field="category", code=ImportErrorCode.FIELD_TYPE_INVALID,
                    message=f"'{category_raw}' is not a valid MoSCoW category.",
                )],
            )
        if framework_fact.framework_type != PrioritizationFrameworkType.MOSCOW:
            return NormalizeOutcome(
                None, None, existing.id if existing else None, identity,
                [ImportFieldError(
                    field="category", code=ImportErrorCode.DOMAIN_RULE_VIOLATED,
                    message=(
                        f"'category' is only meaningful for a MOSCOW framework, not "
                        f"{framework_fact.framework_type.value.upper()}."
                    ),
                )],
            )

    values_raw = row.get("values")
    values: list[CriterionValueInput] | None = None
    try:
        if isinstance(values_raw, list):
            raw_values = cast(list[object], values_raw)
            values = [CriterionValueInput.model_validate(item) for item in raw_values]
        elif isinstance(values_raw, str) and values_raw.strip():
            values = [
                CriterionValueInput.model_validate(item)
                for item in coerce_criterion_values_cell(values_raw)
            ]
        else:
            values = None
    except ValidationError as exc:
        return NormalizeOutcome(
            None, None, existing.id if existing else None, identity, _validation_errors(exc)
        )
    except ValueError as exc:
        return NormalizeOutcome(
            None, None, existing.id if existing else None, identity,
            [ImportFieldError(
                field="values", code=ImportErrorCode.FIELD_TYPE_INVALID, message=str(exc)
            )],
        )

    if values:
        unknown = [
            v.criterion_key for v in values if v.criterion_key not in framework_fact.criterion_keys
        ]
        if unknown:
            return NormalizeOutcome(
                None, None, existing.id if existing else None, identity,
                [ImportFieldError(
                    field="values", code=ImportErrorCode.DOMAIN_RULE_VIOLATED,
                    message=(
                        f"'{unknown[0]}' is not a criterion of framework "
                        f"'{framework_fact.name}'."
                    ),
                )],
            )

    notes = coerce_optional_str(row.get("notes"))

    if existing is None:
        try:
            payload = ProjectPriorityScoreCreate.model_validate(
                {
                    "framework_id": framework_ref,
                    "values": values or [],
                    **({"category": category} if category is not None else {}),
                    **({"notes": notes} if notes is not None else {}),
                }
            )
        except ValidationError as exc:
            return NormalizeOutcome(None, None, None, identity, _validation_errors(exc))
        return NormalizeOutcome(
            "create",
            ProjectPriorityScorePayload(project_id=project_ref, data=payload),
            None, identity, [],
        )

    update_fields: dict[str, object] = {}
    if category is not None:
        update_fields["category"] = category
    if notes is not None:
        update_fields["notes"] = notes
    if values is not None:
        update_fields["values"] = values
    try:
        payload = ProjectPriorityScoreUpdate.model_validate(update_fields)
    except ValidationError as exc:
        return NormalizeOutcome(None, None, existing.id, identity, _validation_errors(exc))

    current = ProjectPriorityScoreUpdate(
        category=existing.category,
        notes=existing.notes,
        values=[
            CriterionValueInput(criterion_key=key, value=value) for key, value in existing.values
        ],
    )
    same_scalars = _unchanged(payload, current, exclude={"values"})
    same_values = values is None or _values_key(values) == _values_key(current.values or [])
    action = "unchanged" if same_scalars and same_values else "update"
    return NormalizeOutcome(
        action,
        ProjectPriorityScorePayload(project_id=project_ref, data=payload),
        existing.id, identity, [],
    )


# ---------------------------------------------------------------------------
# ProjectDependency (Phase 37) — matched by the resolved
# (from_project_id, to_project_id, dependency_type) triple, the table's own
# UniqueConstraint. No update case at all — a dependency edge has no
# mutable fields (see ProjectDependencyFact's docstring), so an existing
# match is always "unchanged," never "update," mirroring
# normalize_team_membership_row exactly. Self-dependency is rejected here
# (Level 3, matches ProjectDependencyService.create's unconditional check);
# BLOCKS-edge cycle detection needs cross-row batch state (which edge a
# PREVIOUS row in this same file already added) and is therefore applied
# by the caller (ImportService._check_project_dependency_cycle), the same
# division of labor as WorkingSchedule's overlap check.
# ---------------------------------------------------------------------------


def normalize_project_dependency_row(
    row: Mapping[str, object],
    lookup: ReferenceLookup,
    existing: set[tuple[uuid.UUID, uuid.UUID, ProjectDependencyType]],
) -> NormalizeOutcome[ProjectDependencyPayload]:
    from_ref = resolve_named_project_reference(
        row, lookup, id_field="from_project_id", external_id_field="from_project_external_id"
    )
    if isinstance(from_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [from_ref])
    to_ref = resolve_named_project_reference(
        row, lookup, id_field="to_project_id", external_id_field="to_project_external_id"
    )
    if isinstance(to_ref, ImportFieldError):
        return NormalizeOutcome(None, None, None, None, [to_ref])

    identity_prefix = (
        f"{_reference_display(row, 'from_project_id', 'from_project_external_id')},"
        f"{_reference_display(row, 'to_project_id', 'to_project_external_id')}"
    )
    dependency_type_raw = coerce_optional_str(row.get("dependency_type"))
    try:
        payload_data = ProjectDependencyCreate.model_validate(
            {"to_project_id": to_ref, "dependency_type": dependency_type_raw}
        )
    except ValidationError as exc:
        return NormalizeOutcome(None, None, None, identity_prefix, _validation_errors(exc))

    identity = f"{identity_prefix},{payload_data.dependency_type.value}"

    if from_ref == to_ref:
        return NormalizeOutcome(
            None, None, None, identity,
            [ImportFieldError(
                field=None, code=ImportErrorCode.DOMAIN_RULE_VIOLATED,
                message="A project cannot depend on itself.",
            )],
        )

    if (from_ref, to_ref, payload_data.dependency_type) in existing:
        return NormalizeOutcome("unchanged", None, None, identity, [])

    payload = ProjectDependencyPayload(from_project_id=from_ref, data=payload_data)
    return NormalizeOutcome("create", payload, None, identity, [])
