"""Pure tests of Level 2/3 normalization and diffing — no database, no
FastAPI (same discipline as tests/domain/test_scenario.py).
"""

import uuid
from datetime import date
from decimal import Decimal

from app.domain.import_export_diff import (
    AllocationFact,
    AvailabilityExceptionFact,
    PersonFact,
    ProjectFact,
    ReferenceLookup,
    TeamFact,
    TeamMembershipFact,
    TeamMembershipPayload,
    apply_mode_policy,
    normalize_allocation_row,
    normalize_availability_exception_row,
    normalize_person_row,
    normalize_project_row,
    normalize_team_membership_row,
    normalize_team_row,
    normalize_working_schedule_row,
    resolve_person_reference,
    resolve_project_reference,
    resolve_team_reference,
)
from app.models.enums import AllocationUnit, AvailabilityType, EmploymentStatus, ProjectStatus
from app.schemas.import_export import ImportErrorCode, ImportFieldError, ImportMode

PERSON_A = uuid.UUID(int=1)
TEAM_A = uuid.UUID(int=10)
PROJECT_A = uuid.UUID(int=20)
ALLOCATION_A = uuid.UUID(int=30)

EMPTY_LOOKUP = ReferenceLookup(
    people_by_id={}, people_by_email={}, teams_by_id={}, teams_by_name={},
    projects_by_id={}, projects_by_external_id={},
    skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
)


def _lookup_with_person() -> ReferenceLookup:
    fact = PersonFact(
        id=PERSON_A, email="jane@example.com", first_name="Jane", last_name="Doe",
        display_name="Jane Doe", job_title=None, timezone="UTC",
        employment_status=EmploymentStatus.ACTIVE,
    )
    return ReferenceLookup(
        people_by_id={PERSON_A: fact}, people_by_email={"jane@example.com": fact},
        teams_by_id={}, teams_by_name={}, projects_by_id={}, projects_by_external_id={},
        skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
    )


def _lookup_with_person_and_project() -> ReferenceLookup:
    base = _lookup_with_person()
    project_fact = ProjectFact(
        id=PROJECT_A, external_id="PRJ-1", name="Website", description=None,
        status=ProjectStatus.PLANNED, start_date=None, end_date=None,
    )
    return ReferenceLookup(
        people_by_id=base.people_by_id, people_by_email=base.people_by_email,
        teams_by_id={}, teams_by_name={},
        projects_by_id={PROJECT_A: project_fact}, projects_by_external_id={"PRJ-1": project_fact},
        skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
    )


# ---------------------------------------------------------------------------
# Reference resolution
# ---------------------------------------------------------------------------


def test_resolve_person_reference_by_literal_id() -> None:
    lookup = _lookup_with_person()
    result = resolve_person_reference({"person_id": str(PERSON_A)}, lookup)
    assert result == PERSON_A


def test_resolve_person_reference_unknown_id_is_invalid_reference() -> None:
    lookup = _lookup_with_person()
    result = resolve_person_reference({"person_id": str(uuid.uuid4())}, lookup)
    assert isinstance(result, ImportFieldError)
    assert result.code == ImportErrorCode.INVALID_REFERENCE
    assert result.field == "person_id"


def test_resolve_person_reference_falls_back_to_email() -> None:
    lookup = _lookup_with_person()
    result = resolve_person_reference({"person_email": "jane@example.com"}, lookup)
    assert result == PERSON_A


def test_resolve_person_reference_unknown_email() -> None:
    lookup = _lookup_with_person()
    result = resolve_person_reference({"person_email": "ghost@example.com"}, lookup)
    assert isinstance(result, ImportFieldError)
    assert result.field == "person_email"


def test_resolve_person_reference_neither_column_present() -> None:
    result = resolve_person_reference({}, EMPTY_LOOKUP)
    assert isinstance(result, ImportFieldError)
    assert result.field is None


def test_resolve_project_reference_rejects_name_column() -> None:
    """project_name is never accepted as a reference column — Project has
    no unique name (docs/adr/0006-phase-6-import-export.md)."""
    lookup = _lookup_with_person_and_project()
    result = resolve_project_reference({"project_name": "Website"}, lookup)
    assert isinstance(result, ImportFieldError)


def test_resolve_project_reference_by_external_id() -> None:
    lookup = _lookup_with_person_and_project()
    result = resolve_project_reference({"project_external_id": "PRJ-1"}, lookup)
    assert result == PROJECT_A


def test_resolve_team_reference_by_name() -> None:
    fact = TeamFact(id=TEAM_A, name="Design", description=None)
    lookup = ReferenceLookup(
        people_by_id={}, people_by_email={}, teams_by_id={TEAM_A: fact},
        teams_by_name={"Design": fact}, projects_by_id={}, projects_by_external_id={},
        skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
    )
    assert resolve_team_reference({"team_name": "Design"}, lookup) == TEAM_A


# ---------------------------------------------------------------------------
# Person
# ---------------------------------------------------------------------------


def test_normalize_person_row_create() -> None:
    row = {"email": "new@example.com", "first_name": "Sam", "last_name": "Lee"}
    outcome = normalize_person_row(row, EMPTY_LOOKUP)
    assert outcome.action == "create"
    assert not outcome.errors
    assert outcome.identity == "email=new@example.com"


def test_normalize_person_row_missing_required_field() -> None:
    row = {"email": "new@example.com", "first_name": "Sam"}  # no last_name
    outcome = normalize_person_row(row, EMPTY_LOOKUP)
    assert outcome.action is None
    assert outcome.errors
    assert outcome.errors[0].code == ImportErrorCode.FIELD_REQUIRED


def test_normalize_person_row_invalid_enum() -> None:
    row = {
        "email": "new@example.com", "first_name": "Sam", "last_name": "Lee",
        "employment_status": "not-a-real-status",
    }
    outcome = normalize_person_row(row, EMPTY_LOOKUP)
    assert outcome.action is None
    assert outcome.errors[0].code == ImportErrorCode.FIELD_TYPE_INVALID


def test_normalize_person_row_update_when_matched() -> None:
    lookup = _lookup_with_person()
    row = {
        "email": "jane@example.com", "first_name": "Jane", "last_name": "Doe",
        "job_title": "Staff Engineer",
    }
    outcome = normalize_person_row(row, lookup)
    assert outcome.action == "update"
    assert outcome.matched_id == PERSON_A


def test_normalize_person_row_unchanged_when_identical() -> None:
    lookup = _lookup_with_person()
    row = {
        "email": "jane@example.com", "first_name": "Jane", "last_name": "Doe",
        "display_name": "Jane Doe", "timezone": "UTC", "employment_status": "active",
    }
    outcome = normalize_person_row(row, lookup)
    assert outcome.action == "unchanged"


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------


def test_normalize_team_row_create() -> None:
    outcome = normalize_team_row({"name": "Platform"}, EMPTY_LOOKUP)
    assert outcome.action == "create"


def test_normalize_team_row_unchanged() -> None:
    fact = TeamFact(id=TEAM_A, name="Design", description=None)
    lookup = ReferenceLookup(
        people_by_id={}, people_by_email={}, teams_by_id={TEAM_A: fact},
        teams_by_name={"Design": fact}, projects_by_id={}, projects_by_external_id={},
        skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
    )
    outcome = normalize_team_row({"name": "Design"}, lookup)
    assert outcome.action == "unchanged"


# ---------------------------------------------------------------------------
# TeamMembership
# ---------------------------------------------------------------------------


def test_normalize_team_membership_row_create() -> None:
    person_fact = PersonFact(
        id=PERSON_A, email="jane@example.com", first_name="Jane", last_name="Doe",
        display_name="Jane Doe", job_title=None, timezone="UTC",
        employment_status=EmploymentStatus.ACTIVE,
    )
    team_fact = TeamFact(id=TEAM_A, name="Design", description=None)
    lookup = ReferenceLookup(
        people_by_id={PERSON_A: person_fact}, people_by_email={"jane@example.com": person_fact},
        teams_by_id={TEAM_A: team_fact}, teams_by_name={"Design": team_fact},
        projects_by_id={}, projects_by_external_id={},
        skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
    )
    outcome = normalize_team_membership_row(
        {"person_email": "jane@example.com", "team_name": "Design"}, lookup, {}
    )
    assert outcome.action == "create"
    assert isinstance(outcome.payload, TeamMembershipPayload)
    assert outcome.payload.team_id == TEAM_A
    assert outcome.payload.data.person_id == PERSON_A


def test_normalize_team_membership_row_unchanged_when_already_member() -> None:
    person_fact = PersonFact(
        id=PERSON_A, email="jane@example.com", first_name="Jane", last_name="Doe",
        display_name="Jane Doe", job_title=None, timezone="UTC",
        employment_status=EmploymentStatus.ACTIVE,
    )
    team_fact = TeamFact(id=TEAM_A, name="Design", description=None)
    lookup = ReferenceLookup(
        people_by_id={PERSON_A: person_fact}, people_by_email={"jane@example.com": person_fact},
        teams_by_id={TEAM_A: team_fact}, teams_by_name={"Design": team_fact},
        projects_by_id={}, projects_by_external_id={},
        skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
    )
    existing = {(PERSON_A, TEAM_A): TeamMembershipFact(person_id=PERSON_A, team_id=TEAM_A)}
    outcome = normalize_team_membership_row(
        {"person_email": "jane@example.com", "team_name": "Design"}, lookup, existing
    )
    assert outcome.action == "unchanged"
    assert outcome.payload is None


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


def test_normalize_project_row_create_without_external_id_has_no_identity() -> None:
    outcome = normalize_project_row({"name": "New Project"}, {})
    assert outcome.action == "create"
    assert outcome.identity is None


def test_normalize_project_row_matches_by_external_id() -> None:
    existing = {
        "PRJ-1": ProjectFact(
            id=PROJECT_A, external_id="PRJ-1", name="Website", description=None,
            status=ProjectStatus.PLANNED, start_date=None, end_date=None,
        )
    }
    outcome = normalize_project_row({"external_id": "PRJ-1", "name": "Website"}, existing)
    assert outcome.action == "unchanged"
    assert outcome.matched_id == PROJECT_A


def test_normalize_project_row_date_range_violation() -> None:
    outcome = normalize_project_row(
        {"name": "Bad dates", "start_date": "2026-09-30", "end_date": "2026-09-01"}, {}
    )
    assert outcome.action is None
    assert outcome.errors[0].code == ImportErrorCode.FIELD_CONSTRAINT_VIOLATED


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


def test_normalize_allocation_row_create() -> None:
    lookup = _lookup_with_person_and_project()
    row = {
        "person_email": "jane@example.com", "project_external_id": "PRJ-1",
        "start_date": "2026-09-01", "end_date": "2026-09-05", "allocation_hours": "20",
    }
    outcome = normalize_allocation_row(row, lookup, {})
    assert outcome.action == "create"


def test_normalize_allocation_row_unresolvable_reference_blocks() -> None:
    row = {
        "person_email": "ghost@example.com", "project_external_id": "PRJ-1",
        "start_date": "2026-09-01", "end_date": "2026-09-05", "allocation_hours": "20",
    }
    outcome = normalize_allocation_row(row, EMPTY_LOOKUP, {})
    assert outcome.action is None
    assert outcome.errors[0].code == ImportErrorCode.INVALID_REFERENCE


def test_normalize_allocation_row_negative_hours_rejected() -> None:
    lookup = _lookup_with_person_and_project()
    row = {
        "person_email": "jane@example.com", "project_external_id": "PRJ-1",
        "start_date": "2026-09-01", "end_date": "2026-09-05", "allocation_hours": "-5",
    }
    outcome = normalize_allocation_row(row, lookup, {})
    assert outcome.action is None
    assert outcome.errors[0].code == ImportErrorCode.FIELD_CONSTRAINT_VIOLATED


def test_normalize_allocation_row_update_matched_by_external_id() -> None:
    existing = {
        "ALC-1": AllocationFact(
            id=ALLOCATION_A, external_id="ALC-1", person_id=PERSON_A, project_id=PROJECT_A,
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 5),
            allocation_hours=Decimal("20.00"), allocation_unit=AllocationUnit.TOTAL_HOURS,
            notes=None,
        )
    }
    row = {
        "external_id": "ALC-1", "start_date": "2026-09-01", "end_date": "2026-09-05",
        "allocation_hours": "30",
    }
    outcome = normalize_allocation_row(row, EMPTY_LOOKUP, existing)
    assert outcome.action == "update"
    assert outcome.matched_id == ALLOCATION_A


def test_normalize_allocation_row_unchanged_matched_by_external_id() -> None:
    existing = {
        "ALC-1": AllocationFact(
            id=ALLOCATION_A, external_id="ALC-1", person_id=PERSON_A, project_id=PROJECT_A,
            start_date=date(2026, 9, 1), end_date=date(2026, 9, 5),
            allocation_hours=Decimal("20.00"), allocation_unit=AllocationUnit.TOTAL_HOURS,
            notes=None,
        )
    }
    row = {
        "external_id": "ALC-1", "start_date": "2026-09-01", "end_date": "2026-09-05",
        "allocation_hours": "20.00",
    }
    outcome = normalize_allocation_row(row, EMPTY_LOOKUP, existing)
    assert outcome.action == "unchanged"


# ---------------------------------------------------------------------------
# WorkingSchedule
# ---------------------------------------------------------------------------


def test_normalize_working_schedule_row_create_with_packed_entries() -> None:
    lookup = _lookup_with_person()
    row = {"person_email": "jane@example.com", "entries": "0:8.00,1:8.00,2:8.00,3:8.00,4:8.00"}
    outcome = normalize_working_schedule_row(row, lookup, {})
    assert outcome.action == "create"


def test_normalize_working_schedule_row_malformed_entries() -> None:
    lookup = _lookup_with_person()
    row = {"person_email": "jane@example.com", "entries": "not-valid"}
    outcome = normalize_working_schedule_row(row, lookup, {})
    assert outcome.action is None
    assert outcome.errors[0].field == "entries"


def test_normalize_working_schedule_row_missing_entries_required() -> None:
    lookup = _lookup_with_person()
    row = {"person_email": "jane@example.com"}
    outcome = normalize_working_schedule_row(row, lookup, {})
    assert outcome.action is None
    assert outcome.errors[0].code == ImportErrorCode.FIELD_REQUIRED


def test_normalize_working_schedule_row_unchanged_ignores_entry_order() -> None:
    from app.domain.import_export_diff import WorkingScheduleFact

    schedule_id = uuid.UUID(int=40)
    existing = {
        "WS-1": WorkingScheduleFact(
            id=schedule_id, external_id="WS-1", person_id=PERSON_A,
            effective_start_date=None, effective_end_date=None,
            entries=((0, Decimal("8.00")), (1, Decimal("8.00"))),
        )
    }
    # Same entries, different order in the file.
    row = {"external_id": "WS-1", "entries": "1:8.00,0:8.00"}
    outcome = normalize_working_schedule_row(row, EMPTY_LOOKUP, existing)
    assert outcome.action == "unchanged"


def test_normalize_working_schedule_row_update_when_entries_differ() -> None:
    from app.domain.import_export_diff import WorkingScheduleFact

    schedule_id = uuid.UUID(int=40)
    existing = {
        "WS-1": WorkingScheduleFact(
            id=schedule_id, external_id="WS-1", person_id=PERSON_A,
            effective_start_date=None, effective_end_date=None,
            entries=((0, Decimal("8.00")),),
        )
    }
    row = {"external_id": "WS-1", "entries": "0:8.00,1:8.00"}
    outcome = normalize_working_schedule_row(row, EMPTY_LOOKUP, existing)
    assert outcome.action == "update"


# ---------------------------------------------------------------------------
# AvailabilityException
# ---------------------------------------------------------------------------


def test_normalize_availability_exception_row_create() -> None:
    lookup = _lookup_with_person()
    row = {
        "person_email": "jane@example.com", "start_date": "2026-09-15",
        "end_date": "2026-09-19", "availability_type": "annual_leave",
    }
    outcome = normalize_availability_exception_row(row, lookup, {})
    assert outcome.action == "create"


def test_normalize_availability_exception_row_invalid_type() -> None:
    lookup = _lookup_with_person()
    row = {
        "person_email": "jane@example.com", "start_date": "2026-09-15",
        "end_date": "2026-09-19", "availability_type": "not-a-real-type",
    }
    outcome = normalize_availability_exception_row(row, lookup, {})
    assert outcome.action is None
    assert outcome.errors[0].code == ImportErrorCode.FIELD_TYPE_INVALID


def test_normalize_availability_exception_row_unchanged() -> None:
    exception_id = uuid.UUID(int=50)
    existing = {
        "AE-1": AvailabilityExceptionFact(
            id=exception_id, external_id="AE-1", person_id=PERSON_A,
            start_date=date(2026, 9, 15), end_date=date(2026, 9, 19),
            availability_type=AvailabilityType.ANNUAL_LEAVE, hours=None, notes=None,
        )
    }
    row = {
        "external_id": "AE-1", "start_date": "2026-09-15", "end_date": "2026-09-19",
        "availability_type": "annual_leave",
    }
    outcome = normalize_availability_exception_row(row, EMPTY_LOOKUP, existing)
    assert outcome.action == "unchanged"


# ---------------------------------------------------------------------------
# apply_mode_policy
# ---------------------------------------------------------------------------


def test_apply_mode_policy_upsert_leaves_outcome_unchanged() -> None:
    outcome = normalize_team_row({"name": "Platform"}, EMPTY_LOOKUP)
    result = apply_mode_policy(outcome, ImportMode.UPSERT)
    assert result.action == "create"


def test_apply_mode_policy_create_only_rejects_a_match() -> None:
    fact = TeamFact(id=TEAM_A, name="Design", description=None)
    lookup = ReferenceLookup(
        people_by_id={}, people_by_email={}, teams_by_id={TEAM_A: fact},
        teams_by_name={"Design": fact}, projects_by_id={}, projects_by_external_id={},
        skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
    )
    outcome = normalize_team_row({"name": "Design"}, lookup)
    result = apply_mode_policy(outcome, ImportMode.CREATE_ONLY)
    assert result.action is None
    assert result.errors[0].code == ImportErrorCode.CONFLICT


def test_apply_mode_policy_update_only_rejects_no_match() -> None:
    outcome = normalize_team_row({"name": "Platform"}, EMPTY_LOOKUP)
    result = apply_mode_policy(outcome, ImportMode.UPDATE_ONLY)
    assert result.action is None
    assert result.errors[0].code == ImportErrorCode.NO_MATCH_FOR_UPDATE_ONLY


def test_apply_mode_policy_does_not_mask_existing_errors() -> None:
    outcome = normalize_person_row({"email": "x@example.com"}, EMPTY_LOOKUP)  # missing names
    assert outcome.errors
    result = apply_mode_policy(outcome, ImportMode.CREATE_ONLY)
    assert result.errors == outcome.errors
