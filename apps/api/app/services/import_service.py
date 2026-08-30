"""Orchestrates Phase 6 import validate/apply for all 7 entities (CLAUDE.md
§39 Phase 6).

Stateless: validate() and apply() both run the identical parse -> normalize
pipeline on demand — no persisted import job/batch entity (see
docs/adr/0006-phase-6-import-export.md). apply() additionally writes.
Atomicity comes entirely from app/core/database.py's existing single-
commit-per-request contract: this service never calls session.commit()/
rollback(), and only starts calling create()/update()/add_member() once
every row in the batch has already been confirmed clean by the read-only
pre-check pass. If a service call still raises mid-write (a narrow
concurrent-write race — the pre-check already ruled out every predictable
failure), the exception propagates through the existing NotFoundError/
ConflictError/DomainValidationError handling exactly like every other
service in this codebase; get_db's `except Exception: db.rollback()` still
discards everything flushed so far in the same request, so atomicity holds
either way.
"""

import contextlib
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, cast

from app.domain.dates import ranges_overlap
from app.domain.import_export_diff import (
    AllocationFact,
    AvailabilityExceptionFact,
    NormalizeOutcome,
    PersonFact,
    PersonSkillFact,
    PersonSkillPayload,
    PrioritizationFrameworkFact,
    ProjectDependencyFact,
    ProjectDependencyPayload,
    ProjectFact,
    ProjectPriorityScoreFact,
    ProjectPriorityScorePayload,
    ProjectSkillRequirementFact,
    ProjectSkillRequirementPayload,
    ReferenceLookup,
    RiskFact,
    RiskPayload,
    SkillFact,
    StakeholderFact,
    StakeholderPayload,
    TeamFact,
    TeamMembershipFact,
    TeamMembershipPayload,
    WorkingScheduleFact,
    apply_mode_policy,
    normalize_allocation_row,
    normalize_availability_exception_row,
    normalize_person_row,
    normalize_person_skill_row,
    normalize_project_dependency_row,
    normalize_project_priority_score_row,
    normalize_project_row,
    normalize_project_skill_requirement_row,
    normalize_risk_row,
    normalize_skill_row,
    normalize_stakeholder_row,
    normalize_team_membership_row,
    normalize_team_row,
    normalize_working_schedule_row,
    resolve_named_project_reference,
    resolve_person_reference,
    resolve_project_reference,
)
from app.domain.import_export_parsing import (
    ExportFormat,
    ImportEntityType,
    ImportErrorCode,
    ImportMode,
    ParseFailure,
    coerce_optional_str,
    detect_format,
    parse_csv_rows,
    parse_json_rows,
)
from app.domain.prioritization import detects_cycle
from app.models.allocation import Allocation
from app.models.availability_exception import AvailabilityException
from app.models.enums import ProjectDependencyType
from app.models.person import Person
from app.models.person_skill import PersonSkill
from app.models.prioritization_framework import PrioritizationFramework
from app.models.project import Project
from app.models.project_dependency import ProjectDependency
from app.models.project_priority_score import ProjectPriorityScore
from app.models.project_skill_requirement import ProjectSkillRequirement
from app.models.risk import Risk
from app.models.skill import Skill
from app.models.stakeholder import Stakeholder
from app.models.team import Team
from app.models.working_schedule import WorkingSchedule
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.prioritization_framework import PrioritizationFrameworkRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_dependency import ProjectDependencyRepository
from app.repositories.project_priority_score import ProjectPriorityScoreRepository
from app.repositories.project_skill_requirement import ProjectSkillRequirementRepository
from app.repositories.risk import RiskRepository
from app.repositories.skill import SkillRepository
from app.repositories.stakeholder import StakeholderRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.allocation import AllocationCreate, AllocationUpdate
from app.schemas.availability_exception import (
    AvailabilityExceptionCreate,
    AvailabilityExceptionUpdate,
)
from app.schemas.import_export import (
    ImportApplyResult,
    ImportFieldError,
    ImportRowResult,
    ImportRowStatus,
    ImportValidationReport,
)
from app.schemas.person import PersonCreate, PersonUpdate
from app.schemas.person_skill import PersonSkillCreate, PersonSkillUpdate
from app.schemas.prioritization import ProjectPriorityScoreCreate, ProjectPriorityScoreUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.schemas.project_skill_requirement import (
    ProjectSkillRequirementCreate,
    ProjectSkillRequirementUpdate,
)
from app.schemas.risk import RiskCreate, RiskUpdate
from app.schemas.skill import SkillCreate, SkillUpdate
from app.schemas.stakeholder import StakeholderCreate, StakeholderUpdate
from app.schemas.team import TeamCreate, TeamUpdate
from app.schemas.working_schedule import WorkingScheduleCreate, WorkingScheduleUpdate
from app.services.allocation import AllocationService
from app.services.availability_exception import AvailabilityExceptionService
from app.services.person import PersonService
from app.services.person_skill import PersonSkillService
from app.services.project import ProjectService
from app.services.project_dependency import ProjectDependencyService
from app.services.project_priority_score import ProjectPriorityScoreService
from app.services.project_skill_requirement import ProjectSkillRequirementService
from app.services.risk import RiskService
from app.services.skill import SkillService
from app.services.stakeholder import StakeholderService
from app.services.team import TeamService
from app.services.team_membership import TeamMembershipService
from app.services.working_schedule import WorkingScheduleService

# ---------------------------------------------------------------------------
# ORM row -> Fact conversion (the only place this service touches an ORM
# attribute directly — everything past this point works with plain Facts,
# mirroring how app/services/capacity.py hands app/domain/capacity.py
# nothing but fact dataclasses)
# ---------------------------------------------------------------------------


def _person_fact(person: Person) -> PersonFact:
    return PersonFact(
        id=person.id, email=person.email, first_name=person.first_name,
        last_name=person.last_name, display_name=person.display_name,
        job_title=person.job_title, timezone=person.timezone,
        employment_status=person.employment_status,
    )


def _team_fact(team: Team) -> TeamFact:
    return TeamFact(id=team.id, name=team.name, description=team.description)


def _project_fact(project: Project) -> ProjectFact:
    return ProjectFact(
        id=project.id, external_id=project.external_id, name=project.name,
        description=project.description, status=project.status,
        start_date=project.start_date, end_date=project.end_date,
    )


def _allocation_fact(allocation: Allocation) -> AllocationFact:
    return AllocationFact(
        id=allocation.id, external_id=allocation.external_id, person_id=allocation.person_id,
        project_id=allocation.project_id, start_date=allocation.start_date,
        end_date=allocation.end_date, allocation_hours=allocation.allocation_hours,
        allocation_unit=allocation.allocation_unit, notes=allocation.notes,
    )


def _working_schedule_fact(schedule: WorkingSchedule) -> WorkingScheduleFact:
    return WorkingScheduleFact(
        id=schedule.id, external_id=schedule.external_id, person_id=schedule.person_id,
        effective_start_date=schedule.effective_start_date,
        effective_end_date=schedule.effective_end_date,
        entries=tuple((entry.weekday, entry.hours) for entry in schedule.entries),
    )


def _availability_exception_fact(exception: AvailabilityException) -> AvailabilityExceptionFact:
    return AvailabilityExceptionFact(
        id=exception.id, external_id=exception.external_id, person_id=exception.person_id,
        start_date=exception.start_date, end_date=exception.end_date,
        availability_type=exception.availability_type, hours=exception.hours,
        notes=exception.notes,
    )


def _skill_fact(skill: Skill) -> SkillFact:
    return SkillFact(
        id=skill.id, name=skill.name, description=skill.description,
        category=skill.category, is_active=skill.is_active,
    )


def _person_skill_fact(person_skill: PersonSkill) -> PersonSkillFact:
    return PersonSkillFact(
        id=person_skill.id, person_id=person_skill.person_id, skill_id=person_skill.skill_id,
        proficiency=person_skill.proficiency, notes=person_skill.notes,
    )


def _project_skill_requirement_fact(
    requirement: ProjectSkillRequirement,
) -> ProjectSkillRequirementFact:
    return ProjectSkillRequirementFact(
        id=requirement.id, project_id=requirement.project_id, skill_id=requirement.skill_id,
        required_hours=requirement.required_hours,
        minimum_proficiency=requirement.minimum_proficiency, notes=requirement.notes,
    )


def _risk_fact(risk: Risk) -> RiskFact:
    return RiskFact(
        id=risk.id, external_id=risk.external_id, project_id=risk.project_id,
        description=risk.description, cause=risk.cause,
        potential_effect=risk.potential_effect, probability=risk.probability,
        impact=risk.impact, response=risk.response, owner_person_id=risk.owner_person_id,
        status=risk.status, review_date=risk.review_date,
    )


def _stakeholder_fact(stakeholder: Stakeholder) -> StakeholderFact:
    return StakeholderFact(
        id=stakeholder.id, project_id=stakeholder.project_id, name=stakeholder.name,
        person_id=stakeholder.person_id, role=stakeholder.role,
        influence=stakeholder.influence, interest=stakeholder.interest,
        decision_authority=stakeholder.decision_authority,
        communication_needs=stakeholder.communication_needs,
    )


def _framework_fact(framework: PrioritizationFramework) -> PrioritizationFrameworkFact:
    return PrioritizationFrameworkFact(
        id=framework.id, name=framework.name, framework_type=framework.framework_type,
        criterion_keys=frozenset(c.key for c in framework.criteria),
    )


def _project_priority_score_fact(score: ProjectPriorityScore) -> ProjectPriorityScoreFact:
    criteria_by_id = {c.id: c for c in score.framework.criteria}
    values: list[tuple[str, Decimal]] = []
    for value in score.values:
        criterion = criteria_by_id.get(value.criterion_id)
        if criterion is not None:
            values.append((criterion.key, value.value))
    return ProjectPriorityScoreFact(
        id=score.id, project_id=score.project_id, framework_id=score.framework_id,
        category=score.category, notes=score.notes, values=tuple(values),
    )


def _project_dependency_fact(dependency: ProjectDependency) -> ProjectDependencyFact:
    return ProjectDependencyFact(
        from_project_id=dependency.from_project_id, to_project_id=dependency.to_project_id,
        dependency_type=dependency.dependency_type,
    )


def _collect(rows: Sequence[Mapping[str, object]], column: str) -> set[str]:
    return {v for v in (coerce_optional_str(row.get(column)) for row in rows) if v is not None}


def _collect_uuids(rows: Sequence[Mapping[str, object]], column: str) -> set[uuid.UUID]:
    result: set[uuid.UUID] = set()
    for row in rows:
        raw = coerce_optional_str(row.get(column))
        if raw is None:
            continue
        # An invalid literal id is reported per-row during normalize, not here.
        with contextlib.suppress(ValueError):
            result.add(uuid.UUID(raw))
    return result


@dataclass(frozen=True)
class _PreparedRow:
    row_number: int
    outcome: NormalizeOutcome[Any]


@dataclass(frozen=True)
class _Prepared:
    file_error: ImportFieldError | None
    rows: list[_PreparedRow]


class ImportService:
    def __init__(
        self,
        person_repository: PersonRepository,
        person_service: PersonService,
        team_repository: TeamRepository,
        team_service: TeamService,
        team_membership_repository: TeamMembershipRepository,
        team_membership_service: TeamMembershipService,
        project_repository: ProjectRepository,
        project_service: ProjectService,
        allocation_repository: AllocationRepository,
        allocation_service: AllocationService,
        working_schedule_repository: WorkingScheduleRepository,
        working_schedule_service: WorkingScheduleService,
        availability_exception_repository: AvailabilityExceptionRepository,
        availability_exception_service: AvailabilityExceptionService,
        skill_repository: SkillRepository,
        skill_service: SkillService,
        person_skill_repository: PersonSkillRepository,
        person_skill_service: PersonSkillService,
        project_skill_requirement_repository: ProjectSkillRequirementRepository,
        project_skill_requirement_service: ProjectSkillRequirementService,
        risk_repository: RiskRepository,
        risk_service: RiskService,
        stakeholder_repository: StakeholderRepository,
        stakeholder_service: StakeholderService,
        prioritization_framework_repository: PrioritizationFrameworkRepository,
        project_priority_score_repository: ProjectPriorityScoreRepository,
        project_priority_score_service: ProjectPriorityScoreService,
        project_dependency_repository: ProjectDependencyRepository,
        project_dependency_service: ProjectDependencyService,
        *,
        max_file_size_bytes: int,
        max_rows: int,
    ) -> None:
        self.person_repository = person_repository
        self.person_service = person_service
        self.team_repository = team_repository
        self.team_service = team_service
        self.team_membership_repository = team_membership_repository
        self.team_membership_service = team_membership_service
        self.project_repository = project_repository
        self.project_service = project_service
        self.allocation_repository = allocation_repository
        self.allocation_service = allocation_service
        self.working_schedule_repository = working_schedule_repository
        self.working_schedule_service = working_schedule_service
        self.availability_exception_repository = availability_exception_repository
        self.availability_exception_service = availability_exception_service
        self.skill_repository = skill_repository
        self.skill_service = skill_service
        self.person_skill_repository = person_skill_repository
        self.person_skill_service = person_skill_service
        self.project_skill_requirement_repository = project_skill_requirement_repository
        self.project_skill_requirement_service = project_skill_requirement_service
        self.risk_repository = risk_repository
        self.risk_service = risk_service
        self.stakeholder_repository = stakeholder_repository
        self.stakeholder_service = stakeholder_service
        self.prioritization_framework_repository = prioritization_framework_repository
        self.project_priority_score_repository = project_priority_score_repository
        self.project_priority_score_service = project_priority_score_service
        self.project_dependency_repository = project_dependency_repository
        self.project_dependency_service = project_dependency_service
        self.max_file_size_bytes = max_file_size_bytes
        self.max_rows = max_rows

    # -- Public entry points ------------------------------------------------

    def validate(
        self,
        organization_id: uuid.UUID,
        entity_type: ImportEntityType,
        raw_bytes: bytes,
        filename: str | None,
        content_type: str | None,
        mode: ImportMode,
    ) -> ImportValidationReport:
        prepared = self._prepare(
            organization_id, entity_type, raw_bytes, filename, content_type, mode
        )
        return self._to_validation_report(entity_type, mode, prepared)

    def apply(
        self,
        organization_id: uuid.UUID,
        entity_type: ImportEntityType,
        raw_bytes: bytes,
        filename: str | None,
        content_type: str | None,
        mode: ImportMode,
    ) -> ImportApplyResult:
        prepared = self._prepare(
            organization_id, entity_type, raw_bytes, filename, content_type, mode
        )
        if prepared.file_error is not None or any(p.outcome.errors for p in prepared.rows):
            return self._to_apply_result(entity_type, mode, prepared, applied=False)

        for prow in prepared.rows:
            self._write_row(organization_id, entity_type, prow.outcome)
        return self._to_apply_result(entity_type, mode, prepared, applied=True)

    # -- Level 1 (file) + dispatch --------------------------------------------

    def _prepare(
        self,
        organization_id: uuid.UUID,
        entity_type: ImportEntityType,
        raw_bytes: bytes,
        filename: str | None,
        content_type: str | None,
        mode: ImportMode,
    ) -> _Prepared:
        detected_format = detect_format(filename, content_type)
        if detected_format is None:
            return _Prepared(
                ImportFieldError(
                    field=None, code=ImportErrorCode.UNSUPPORTED_FORMAT,
                    message="Could not determine the file's format. Upload a .csv or .json file.",
                ),
                [],
            )

        if len(raw_bytes) > self.max_file_size_bytes:
            return _Prepared(
                ImportFieldError(
                    field=None, code=ImportErrorCode.FILE_TOO_LARGE,
                    message=f"File exceeds the {self.max_file_size_bytes}-byte limit.",
                ),
                [],
            )

        parsed = (
            parse_csv_rows(raw_bytes, entity_type)
            if detected_format == ExportFormat.CSV
            else parse_json_rows(raw_bytes, entity_type)
        )
        if isinstance(parsed, ParseFailure):
            return _Prepared(
                ImportFieldError(field=None, code=parsed.code, message=parsed.message), []
            )

        if len(parsed) > self.max_rows:
            return _Prepared(
                ImportFieldError(
                    field=None, code=ImportErrorCode.ROW_LIMIT_EXCEEDED,
                    message=(
                        f"File has {len(parsed)} rows, exceeding the {self.max_rows}-row limit."
                    ),
                ),
                [],
            )

        preparers = {
            ImportEntityType.PERSON: self._prepare_person,
            ImportEntityType.TEAM: self._prepare_team,
            ImportEntityType.TEAM_MEMBERSHIP: self._prepare_team_membership,
            ImportEntityType.PROJECT: self._prepare_project,
            ImportEntityType.ALLOCATION: self._prepare_allocation,
            ImportEntityType.WORKING_SCHEDULE: self._prepare_working_schedule,
            ImportEntityType.AVAILABILITY_EXCEPTION: self._prepare_availability_exception,
            ImportEntityType.SKILL: self._prepare_skill,
            ImportEntityType.PERSON_SKILL: self._prepare_person_skill,
            ImportEntityType.PROJECT_SKILL_REQUIREMENT: self._prepare_project_skill_requirement,
            ImportEntityType.RISK: self._prepare_risk,
            ImportEntityType.STAKEHOLDER: self._prepare_stakeholder,
            ImportEntityType.PROJECT_PRIORITY_SCORE: self._prepare_project_priority_score,
            ImportEntityType.PROJECT_DEPENDENCY: self._prepare_project_dependency,
        }
        rows = preparers[entity_type](organization_id, parsed, mode)
        return _Prepared(None, self._flag_duplicate_identities(rows))

    def _flag_duplicate_identities(self, rows: list[_PreparedRow]) -> list[_PreparedRow]:
        """Level 4 (cross-row): two rows in the same file resolving to the
        same identity — always blocking, regardless of the classified
        action, since the second occurrence would otherwise silently
        collide with the first at apply time."""
        seen: dict[str, int] = {}
        result: list[_PreparedRow] = []
        for prow in rows:
            identity = prow.outcome.identity
            if identity is None or prow.outcome.errors:
                result.append(prow)
                continue
            if identity in seen:
                duplicate = ImportFieldError(
                    field=None, code=ImportErrorCode.DUPLICATE_IN_FILE,
                    message=f"Row {seen[identity]} already resolves to the same record.",
                )
                result.append(
                    _PreparedRow(
                        prow.row_number,
                        NormalizeOutcome(
                            None, None, prow.outcome.matched_id, identity, [duplicate]
                        ),
                    )
                )
            else:
                seen[identity] = prow.row_number
                result.append(prow)
        return result

    # -- Lookup construction (batched — one query per fact type per file,
    # never per row, per CLAUDE.md §27) --------------------------------------

    def _person_lookup_maps(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]]
    ) -> tuple[dict[uuid.UUID, PersonFact], dict[str, PersonFact]]:
        # "person_id"/"person_email" is the reference shape every entity
        # through Phase 7 uses; Risk's OPTIONAL owner reference (Phase 36)
        # is spelled "owner_person_id"/"owner_person_email" instead (it
        # can't reuse "person_id" — Risk has no such column), so both
        # column-name pairs are scanned into the same Person catalog here
        # rather than building a second, parallel lookup map.
        ids = _collect_uuids(rows, "person_id") | _collect_uuids(rows, "owner_person_id")
        emails = _collect(rows, "person_email") | _collect(rows, "owner_person_email")
        by_id: dict[uuid.UUID, PersonFact] = {}
        for person in self.person_repository.list_by_ids(list(ids), organization_id):
            by_id[person.id] = _person_fact(person)
        for person in self.person_repository.list_by_emails(list(emails), organization_id):
            by_id[person.id] = _person_fact(person)
        by_email = {fact.email: fact for fact in by_id.values()}
        return by_id, by_email

    def _team_lookup_maps(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]]
    ) -> tuple[dict[uuid.UUID, TeamFact], dict[str, TeamFact]]:
        ids = _collect_uuids(rows, "team_id")
        names = _collect(rows, "team_name")
        by_id: dict[uuid.UUID, TeamFact] = {}
        for team in self.team_repository.list_by_ids(list(ids), organization_id):
            by_id[team.id] = _team_fact(team)
        for team in self.team_repository.list_by_names(list(names), organization_id):
            by_id[team.id] = _team_fact(team)
        by_name = {fact.name: fact for fact in by_id.values()}
        return by_id, by_name

    def _project_lookup_maps(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]]
    ) -> tuple[dict[uuid.UUID, ProjectFact], dict[str, ProjectFact]]:
        # "project_id"/"project_external_id" is the reference shape every
        # single-project-reference entity uses; ProjectDependency (Phase
        # 37) references TWO projects per row under different column names
        # ("from_project_id"/"from_project_external_id" and
        # "to_project_id"/"to_project_external_id" — see
        # resolve_named_project_reference), so all three column-name pairs
        # are scanned into the same Project catalog here rather than
        # building a second, parallel lookup map.
        ids = (
            _collect_uuids(rows, "project_id")
            | _collect_uuids(rows, "from_project_id")
            | _collect_uuids(rows, "to_project_id")
        )
        external_ids = (
            _collect(rows, "project_external_id")
            | _collect(rows, "from_project_external_id")
            | _collect(rows, "to_project_external_id")
        )
        by_id: dict[uuid.UUID, ProjectFact] = {}
        for project in self.project_repository.list_by_ids(list(ids), organization_id):
            by_id[project.id] = _project_fact(project)
        for project in self.project_repository.list_by_external_ids(
            list(external_ids), organization_id
        ):
            by_id[project.id] = _project_fact(project)
        by_external_id = {
            fact.external_id: fact for fact in by_id.values() if fact.external_id is not None
        }
        return by_id, by_external_id

    def _skill_lookup_maps(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]]
    ) -> tuple[dict[uuid.UUID, SkillFact], dict[str, SkillFact]]:
        ids = _collect_uuids(rows, "skill_id")
        names = _collect(rows, "skill_name")
        by_id: dict[uuid.UUID, SkillFact] = {}
        for skill in self.skill_repository.list_by_ids(list(ids), organization_id):
            by_id[skill.id] = _skill_fact(skill)
        for skill in self.skill_repository.list_by_names(list(names), organization_id):
            by_id[skill.id] = _skill_fact(skill)
        by_name = {fact.name: fact for fact in by_id.values()}
        return by_id, by_name

    def _framework_lookup_maps(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]]
    ) -> tuple[
        dict[uuid.UUID, PrioritizationFrameworkFact], dict[str, PrioritizationFrameworkFact]
    ]:
        ids = _collect_uuids(rows, "framework_id")
        names = _collect(rows, "framework_name")
        by_id: dict[uuid.UUID, PrioritizationFrameworkFact] = {}
        for framework in self.prioritization_framework_repository.list_by_ids(
            list(ids), organization_id
        ):
            by_id[framework.id] = _framework_fact(framework)
        for framework in self.prioritization_framework_repository.list_by_names(
            list(names), organization_id
        ):
            by_id[framework.id] = _framework_fact(framework)
        by_name = {fact.name: fact for fact in by_id.values()}
        return by_id, by_name

    def _build_lookup(
        self,
        organization_id: uuid.UUID,
        rows: Sequence[Mapping[str, object]],
        *,
        need_people: bool = False,
        need_teams: bool = False,
        need_projects: bool = False,
        need_skills: bool = False,
        need_frameworks: bool = False,
    ) -> ReferenceLookup:
        people_by_id, people_by_email = (
            self._person_lookup_maps(organization_id, rows) if need_people else ({}, {})
        )
        teams_by_id, teams_by_name = (
            self._team_lookup_maps(organization_id, rows) if need_teams else ({}, {})
        )
        projects_by_id, projects_by_external_id = (
            self._project_lookup_maps(organization_id, rows) if need_projects else ({}, {})
        )
        skills_by_id, skills_by_name = (
            self._skill_lookup_maps(organization_id, rows) if need_skills else ({}, {})
        )
        frameworks_by_id, frameworks_by_name = (
            self._framework_lookup_maps(organization_id, rows) if need_frameworks else ({}, {})
        )
        return ReferenceLookup(
            people_by_id=people_by_id, people_by_email=people_by_email,
            teams_by_id=teams_by_id, teams_by_name=teams_by_name,
            projects_by_id=projects_by_id, projects_by_external_id=projects_by_external_id,
            frameworks_by_id=frameworks_by_id, frameworks_by_name=frameworks_by_name,
            skills_by_id=skills_by_id, skills_by_name=skills_by_name,
        )

    # -- Per-entity preparation -----------------------------------------------

    def _prepare_person(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        # Self-identity match: Person's own "email" column — NOT the
        # "person_email" column other entities use to *reference* a person
        # (see _person_lookup_maps, which is for that latter case only).
        emails = _collect(rows, "email")
        people_by_email = {
            person.email: _person_fact(person)
            for person in self.person_repository.list_by_emails(list(emails), organization_id)
        }
        lookup = ReferenceLookup(
            people_by_id={f.id: f for f in people_by_email.values()},
            people_by_email=people_by_email,
            teams_by_id={}, teams_by_name={}, projects_by_id={}, projects_by_external_id={},
            skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
        )
        return [
            _PreparedRow(i, apply_mode_policy(normalize_person_row(row, lookup), mode))
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_team(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        # Self-identity match: Team's own "name" column — NOT "team_name"
        # (see _team_lookup_maps, which is for reference resolution only).
        names = _collect(rows, "name")
        teams_by_name = {
            team.name: _team_fact(team)
            for team in self.team_repository.list_by_names(list(names), organization_id)
        }
        lookup = ReferenceLookup(
            people_by_id={}, people_by_email={},
            teams_by_id={f.id: f for f in teams_by_name.values()}, teams_by_name=teams_by_name,
            projects_by_id={}, projects_by_external_id={},
            skills_by_id={}, skills_by_name={}, frameworks_by_id={}, frameworks_by_name={},
        )
        return [
            _PreparedRow(i, apply_mode_policy(normalize_team_row(row, lookup), mode))
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_team_membership(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_people=True, need_teams=True)
        resolved_person_ids: set[uuid.UUID] = set()
        for row in rows:
            ref = resolve_person_reference(row, lookup)
            if not isinstance(ref, ImportFieldError):
                resolved_person_ids.add(ref)
        memberships = self.team_membership_repository.list_for_people(
            list(resolved_person_ids), organization_id
        )
        existing = {
            (m.person_id, m.team_id): TeamMembershipFact(person_id=m.person_id, team_id=m.team_id)
            for m in memberships
        }
        return [
            _PreparedRow(
                i, apply_mode_policy(normalize_team_membership_row(row, lookup, existing), mode)
            )
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_project(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        # Self-identity match: Project's own "external_id" column — NOT
        # "project_external_id" (see _project_lookup_maps, which is for
        # reference resolution only, e.g. an Allocation row pointing at a
        # project).
        external_ids = _collect(rows, "external_id")
        existing = {
            project.external_id: _project_fact(project)
            for project in self.project_repository.list_by_external_ids(
                list(external_ids), organization_id
            )
            if project.external_id is not None
        }
        return [
            _PreparedRow(i, apply_mode_policy(normalize_project_row(row, existing), mode))
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_allocation(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_people=True, need_projects=True)
        external_ids = _collect(rows, "external_id")
        existing = {
            a.external_id: _allocation_fact(a)
            for a in self.allocation_repository.list_by_external_ids(
                list(external_ids), organization_id
            )
            if a.external_id is not None
        }
        return [
            _PreparedRow(
                i, apply_mode_policy(normalize_allocation_row(row, lookup, existing), mode)
            )
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_working_schedule(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_people=True)
        external_ids = _collect(rows, "external_id")
        existing = {
            s.external_id: _working_schedule_fact(s)
            for s in self.working_schedule_repository.list_by_external_ids(
                list(external_ids), organization_id
            )
            if s.external_id is not None
        }

        # Overlap pre-check (Level 3): seed every referenced person's
        # COMPLETE existing schedule set (not date-bounded — see
        # list_all_for_people), then simulate the batch in file order so a
        # later row also sees the effect of an earlier one, exactly
        # mirroring WorkingScheduleService's own overlap rule (see
        # docs/adr/0006-phase-6-import-export.md).
        resolved_person_ids: set[uuid.UUID] = set()
        for row in rows:
            ref = resolve_person_reference(row, lookup)
            if not isinstance(ref, ImportFieldError):
                resolved_person_ids.add(ref)
        resolved_person_ids.update(fact.person_id for fact in existing.values())
        ranges_by_person: dict[uuid.UUID, list[tuple[uuid.UUID, date | None, date | None]]] = {}
        for schedule in self.working_schedule_repository.list_all_for_people(
            list(resolved_person_ids), organization_id
        ):
            ranges_by_person.setdefault(schedule.person_id, []).append(
                (schedule.id, schedule.effective_start_date, schedule.effective_end_date)
            )

        result: list[_PreparedRow] = []
        for i, row in enumerate(rows, start=1):
            outcome = apply_mode_policy(normalize_working_schedule_row(row, lookup, existing), mode)
            outcome = self._check_working_schedule_overlap(outcome, ranges_by_person)
            result.append(_PreparedRow(i, outcome))
        return result

    def _check_working_schedule_overlap(
        self,
        outcome: NormalizeOutcome[Any],
        ranges_by_person: dict[uuid.UUID, list[tuple[uuid.UUID, date | None, date | None]]],
    ) -> NormalizeOutcome[Any]:
        if outcome.errors or outcome.action in (None, "unchanged"):
            return outcome

        payload = outcome.payload
        self_id: uuid.UUID | None = None
        if isinstance(payload, WorkingScheduleCreate):
            person_id = payload.person_id
            candidate_start = payload.effective_start_date
            candidate_end = payload.effective_end_date
        elif isinstance(payload, WorkingScheduleUpdate):
            self_id = outcome.matched_id
            owner = next(
                (
                    (pid, start, end)
                    for pid, entries in ranges_by_person.items()
                    for sid, start, end in entries
                    if sid == self_id
                ),
                None,
            )
            if owner is None:
                return outcome  # no existing schedules to compare against at all
            person_id, existing_start, existing_end = owner
            candidate_start = (
                payload.effective_start_date
                if "effective_start_date" in payload.model_fields_set
                else existing_start
            )
            candidate_end = (
                payload.effective_end_date
                if "effective_end_date" in payload.model_fields_set
                else existing_end
            )
        else:
            return outcome

        for other_id, other_start, other_end in ranges_by_person.get(person_id, []):
            if other_id == self_id:
                continue
            if ranges_overlap(candidate_start, candidate_end, other_start, other_end):
                error = ImportFieldError(
                    field=None, code=ImportErrorCode.DOMAIN_RULE_VIOLATED,
                    message=(
                        "effective date range overlaps an existing working schedule "
                        "for this person."
                    ),
                )
                return NormalizeOutcome(None, None, outcome.matched_id, outcome.identity, [error])

        ranges_by_person.setdefault(person_id, []).append(
            (self_id or uuid.uuid4(), candidate_start, candidate_end)
        )
        return outcome

    def _prepare_availability_exception(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_people=True)
        external_ids = _collect(rows, "external_id")
        existing = {
            e.external_id: _availability_exception_fact(e)
            for e in self.availability_exception_repository.list_by_external_ids(
                list(external_ids), organization_id
            )
            if e.external_id is not None
        }
        return [
            _PreparedRow(
                i,
                apply_mode_policy(
                    normalize_availability_exception_row(row, lookup, existing), mode
                ),
            )
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_skill(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        # Self-identity match: Skill's own "name" column — NOT "skill_name"
        # (see _skill_lookup_maps, which is for reference resolution only,
        # e.g. a PersonSkill row pointing at a skill).
        names = _collect(rows, "name")
        skills_by_name = {
            skill.name: _skill_fact(skill)
            for skill in self.skill_repository.list_by_names(list(names), organization_id)
        }
        return [
            _PreparedRow(i, apply_mode_policy(normalize_skill_row(row, skills_by_name), mode))
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_person_skill(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_people=True, need_skills=True)
        resolved_person_ids: set[uuid.UUID] = set()
        for row in rows:
            ref = resolve_person_reference(row, lookup)
            if not isinstance(ref, ImportFieldError):
                resolved_person_ids.add(ref)
        existing = {
            (row.person_id, row.skill_id): _person_skill_fact(row)
            for row in self.person_skill_repository.list_for_people(
                list(resolved_person_ids), organization_id
            )
        }
        return [
            _PreparedRow(
                i, apply_mode_policy(normalize_person_skill_row(row, lookup, existing), mode)
            )
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_project_skill_requirement(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_projects=True, need_skills=True)
        resolved_project_ids: set[uuid.UUID] = set()
        for row in rows:
            ref = resolve_project_reference(row, lookup)
            if not isinstance(ref, ImportFieldError):
                resolved_project_ids.add(ref)
        existing = {
            (row.project_id, row.skill_id): _project_skill_requirement_fact(row)
            for row in self.project_skill_requirement_repository.list_for_projects(
                list(resolved_project_ids), organization_id
            )
        }
        return [
            _PreparedRow(
                i,
                apply_mode_policy(
                    normalize_project_skill_requirement_row(row, lookup, existing), mode
                ),
            )
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_risk(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_projects=True, need_people=True)
        external_ids = _collect(rows, "external_id")
        existing = {
            r.external_id: _risk_fact(r)
            for r in self.risk_repository.list_by_external_ids(
                list(external_ids), organization_id
            )
            if r.external_id is not None
        }
        return [
            _PreparedRow(i, apply_mode_policy(normalize_risk_row(row, lookup, existing), mode))
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_stakeholder(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_projects=True, need_people=True)
        resolved_project_ids: set[uuid.UUID] = set()
        for row in rows:
            ref = resolve_project_reference(row, lookup)
            if not isinstance(ref, ImportFieldError):
                resolved_project_ids.add(ref)
        existing = {
            (s.project_id, s.person_id): _stakeholder_fact(s)
            for s in self.stakeholder_repository.list_for_projects(
                list(resolved_project_ids), organization_id
            )
            if s.person_id is not None
        }
        return [
            _PreparedRow(
                i, apply_mode_policy(normalize_stakeholder_row(row, lookup, existing), mode)
            )
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_project_priority_score(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_projects=True, need_frameworks=True)
        resolved_project_ids: set[uuid.UUID] = set()
        for row in rows:
            ref = resolve_project_reference(row, lookup)
            if not isinstance(ref, ImportFieldError):
                resolved_project_ids.add(ref)
        existing = {
            (s.project_id, s.framework_id): _project_priority_score_fact(s)
            for s in self.project_priority_score_repository.list_for_projects(
                list(resolved_project_ids), organization_id
            )
        }
        return [
            _PreparedRow(
                i,
                apply_mode_policy(
                    normalize_project_priority_score_row(row, lookup, existing), mode
                ),
            )
            for i, row in enumerate(rows, start=1)
        ]

    def _prepare_project_dependency(
        self, organization_id: uuid.UUID, rows: Sequence[Mapping[str, object]], mode: ImportMode
    ) -> list[_PreparedRow]:
        lookup = self._build_lookup(organization_id, rows, need_projects=True)
        resolved_project_ids: set[uuid.UUID] = set()
        for row in rows:
            for ref in (
                resolve_named_project_reference(
                    row, lookup,
                    id_field="from_project_id", external_id_field="from_project_external_id",
                ),
                resolve_named_project_reference(
                    row, lookup,
                    id_field="to_project_id", external_id_field="to_project_external_id",
                ),
            ):
                if not isinstance(ref, ImportFieldError):
                    resolved_project_ids.add(ref)
        existing = {
            (d.from_project_id, d.to_project_id, d.dependency_type): _project_dependency_fact(d)
            for d in self.project_dependency_repository.list_for_projects(
                list(resolved_project_ids), organization_id
            )
        }
        existing_triples = set(existing.keys())

        # BLOCKS-edge cycle pre-check (Level 3): seed the organization's
        # current BLOCKS edges, then simulate the batch in file order so a
        # later row also sees a cycle a PRECEDING row in this same file
        # would introduce — exactly mirroring
        # _check_working_schedule_overlap's identical batch-simulation
        # shape, and ProjectDependencyService.create's own cycle check
        # (self-dependency is already rejected inside
        # normalize_project_dependency_row itself, needing no batch state).
        blocks_edges = [
            (str(f), str(t)) for f, t in self.project_dependency_repository.list_blocks_edges(
                organization_id
            )
        ]
        result: list[_PreparedRow] = []
        for i, row in enumerate(rows, start=1):
            outcome = apply_mode_policy(
                normalize_project_dependency_row(row, lookup, existing_triples), mode
            )
            outcome = self._check_project_dependency_cycle(outcome, blocks_edges)
            result.append(_PreparedRow(i, outcome))
        return result

    def _check_project_dependency_cycle(
        self, outcome: NormalizeOutcome[Any], blocks_edges: list[tuple[str, str]]
    ) -> NormalizeOutcome[Any]:
        if outcome.errors or outcome.action != "create":
            return outcome
        payload = outcome.payload
        if not isinstance(payload, ProjectDependencyPayload):
            return outcome
        if payload.data.dependency_type != ProjectDependencyType.BLOCKS:
            return outcome

        from_id = str(payload.from_project_id)
        to_id = str(payload.data.to_project_id)
        if detects_cycle(blocks_edges, (from_id, to_id)):
            error = ImportFieldError(
                field=None, code=ImportErrorCode.DOMAIN_RULE_VIOLATED,
                message="This dependency would create a cycle in the project dependency graph.",
            )
            return NormalizeOutcome(None, None, outcome.matched_id, outcome.identity, [error])

        blocks_edges.append((from_id, to_id))
        return outcome

    # -- Writing (apply only; every row already confirmed clean) -------------

    def _write_row(
        self,
        organization_id: uuid.UUID,
        entity_type: ImportEntityType,
        outcome: NormalizeOutcome[Any],
    ) -> None:
        if outcome.action in (None, "unchanged"):
            return

        if entity_type == ImportEntityType.PERSON:
            if outcome.action == "create":
                self.person_service.create(organization_id, cast(PersonCreate, outcome.payload))
            else:
                self.person_service.update(
                    organization_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(PersonUpdate, outcome.payload),
                )
        elif entity_type == ImportEntityType.TEAM:
            if outcome.action == "create":
                self.team_service.create(organization_id, cast(TeamCreate, outcome.payload))
            else:
                self.team_service.update(
                    organization_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(TeamUpdate, outcome.payload),
                )
        elif entity_type == ImportEntityType.TEAM_MEMBERSHIP:
            payload = cast(TeamMembershipPayload, outcome.payload)
            self.team_membership_service.add_member(organization_id, payload.team_id, payload.data)
        elif entity_type == ImportEntityType.PROJECT:
            if outcome.action == "create":
                self.project_service.create(organization_id, cast(ProjectCreate, outcome.payload))
            else:
                self.project_service.update(
                    organization_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(ProjectUpdate, outcome.payload),
                )
        elif entity_type == ImportEntityType.ALLOCATION:
            if outcome.action == "create":
                self.allocation_service.create(
                    organization_id, cast(AllocationCreate, outcome.payload)
                )
            else:
                self.allocation_service.update(
                    organization_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(AllocationUpdate, outcome.payload),
                )
        elif entity_type == ImportEntityType.WORKING_SCHEDULE:
            if outcome.action == "create":
                self.working_schedule_service.create(
                    organization_id, cast(WorkingScheduleCreate, outcome.payload)
                )
            else:
                self.working_schedule_service.update(
                    organization_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(WorkingScheduleUpdate, outcome.payload),
                )
        elif entity_type == ImportEntityType.AVAILABILITY_EXCEPTION:
            if outcome.action == "create":
                self.availability_exception_service.create(
                    organization_id, cast(AvailabilityExceptionCreate, outcome.payload)
                )
            else:
                self.availability_exception_service.update(
                    organization_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(AvailabilityExceptionUpdate, outcome.payload),
                )
        elif entity_type == ImportEntityType.SKILL:
            if outcome.action == "create":
                self.skill_service.create(organization_id, cast(SkillCreate, outcome.payload))
            else:
                self.skill_service.update(
                    organization_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(SkillUpdate, outcome.payload),
                )
        elif entity_type == ImportEntityType.PERSON_SKILL:
            payload = cast(PersonSkillPayload, outcome.payload)
            if outcome.action == "create":
                self.person_skill_service.add(
                    organization_id, payload.person_id, cast(PersonSkillCreate, payload.data)
                )
            else:
                self.person_skill_service.update(
                    organization_id,
                    payload.person_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(PersonSkillUpdate, payload.data),
                )
        elif entity_type == ImportEntityType.PROJECT_SKILL_REQUIREMENT:
            requirement_payload = cast(ProjectSkillRequirementPayload, outcome.payload)
            if outcome.action == "create":
                self.project_skill_requirement_service.add(
                    organization_id,
                    requirement_payload.project_id,
                    cast(ProjectSkillRequirementCreate, requirement_payload.data),
                )
            else:
                self.project_skill_requirement_service.update(
                    organization_id,
                    requirement_payload.project_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(ProjectSkillRequirementUpdate, requirement_payload.data),
                )
        elif entity_type == ImportEntityType.RISK:
            risk_payload = cast(RiskPayload, outcome.payload)
            if outcome.action == "create":
                self.risk_service.create(
                    organization_id, risk_payload.project_id, cast(RiskCreate, risk_payload.data)
                )
            else:
                self.risk_service.update(
                    organization_id,
                    risk_payload.project_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(RiskUpdate, risk_payload.data),
                )
        elif entity_type == ImportEntityType.STAKEHOLDER:
            stakeholder_payload = cast(StakeholderPayload, outcome.payload)
            if outcome.action == "create":
                self.stakeholder_service.create(
                    organization_id,
                    stakeholder_payload.project_id,
                    cast(StakeholderCreate, stakeholder_payload.data),
                )
            else:
                self.stakeholder_service.update(
                    organization_id,
                    stakeholder_payload.project_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(StakeholderUpdate, stakeholder_payload.data),
                )
        elif entity_type == ImportEntityType.PROJECT_PRIORITY_SCORE:
            score_payload = cast(ProjectPriorityScorePayload, outcome.payload)
            if outcome.action == "create":
                self.project_priority_score_service.create(
                    organization_id,
                    score_payload.project_id,
                    cast(ProjectPriorityScoreCreate, score_payload.data),
                )
            else:
                self.project_priority_score_service.update(
                    organization_id,
                    score_payload.project_id,
                    cast(uuid.UUID, outcome.matched_id),
                    cast(ProjectPriorityScoreUpdate, score_payload.data),
                )
        else:
            # PROJECT_DEPENDENCY — always "create" (see
            # ProjectDependencyFact's docstring: no update case exists).
            dependency_payload = cast(ProjectDependencyPayload, outcome.payload)
            self.project_dependency_service.create(
                organization_id, dependency_payload.from_project_id, dependency_payload.data
            )

    # -- Report assembly -------------------------------------------------

    def _to_row_result(self, prow: _PreparedRow) -> ImportRowResult:
        outcome = prow.outcome
        if outcome.errors:
            status = ImportRowStatus.INVALID
        elif outcome.action == "create":
            status = ImportRowStatus.VALID_CREATE
        elif outcome.action == "update":
            status = ImportRowStatus.VALID_UPDATE
        else:
            status = ImportRowStatus.VALID_UNCHANGED
        return ImportRowResult(
            row_number=prow.row_number, status=status, identity=outcome.identity,
            matched_id=outcome.matched_id, errors=outcome.errors,
        )

    def _to_validation_report(
        self, entity_type: ImportEntityType, mode: ImportMode, prepared: _Prepared
    ) -> ImportValidationReport:
        if prepared.file_error is not None:
            return ImportValidationReport(
                entity_type=entity_type, mode=mode, file_error=prepared.file_error,
                total_rows=0, valid_create_count=0, valid_update_count=0,
                valid_unchanged_count=0, invalid_count=0, ready_to_apply=False, rows=[],
            )
        results = [self._to_row_result(p) for p in prepared.rows]
        creates = sum(1 for r in results if r.status == ImportRowStatus.VALID_CREATE)
        updates = sum(1 for r in results if r.status == ImportRowStatus.VALID_UPDATE)
        unchanged = sum(1 for r in results if r.status == ImportRowStatus.VALID_UNCHANGED)
        invalid = sum(1 for r in results if r.status == ImportRowStatus.INVALID)
        return ImportValidationReport(
            entity_type=entity_type, mode=mode, total_rows=len(results),
            valid_create_count=creates, valid_update_count=updates,
            valid_unchanged_count=unchanged, invalid_count=invalid,
            ready_to_apply=invalid == 0 and len(results) > 0, rows=results,
        )

    def _to_apply_result(
        self, entity_type: ImportEntityType, mode: ImportMode, prepared: _Prepared, *, applied: bool
    ) -> ImportApplyResult:
        if prepared.file_error is not None:
            return ImportApplyResult(
                entity_type=entity_type, mode=mode, file_error=prepared.file_error, applied=False,
                total_rows=0, created_count=0, updated_count=0, unchanged_count=0,
                invalid_count=0, rows=[],
            )
        results = [self._to_row_result(p) for p in prepared.rows]
        creates = sum(1 for r in results if r.status == ImportRowStatus.VALID_CREATE)
        updates = sum(1 for r in results if r.status == ImportRowStatus.VALID_UPDATE)
        unchanged = sum(1 for r in results if r.status == ImportRowStatus.VALID_UNCHANGED)
        invalid = sum(1 for r in results if r.status == ImportRowStatus.INVALID)
        return ImportApplyResult(
            entity_type=entity_type, mode=mode, applied=applied, total_rows=len(results),
            created_count=creates if applied else 0, updated_count=updates if applied else 0,
            unchanged_count=unchanged if applied else 0, invalid_count=invalid, rows=results,
        )
