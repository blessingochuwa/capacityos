"""Orchestrates Phase 6 export for all 7 entities (CLAUDE.md §39 Phase 6).

Read-only: this service's constructor never receives CapacityService/
InsightService/ScenarioCalculationService, so no derived value (utilization,
over-allocation, remaining capacity, ...) can accidentally leak into an
export — only literal model columns plus id/external_id/timestamps ever
appear (see docs/adr/0006-phase-6-import-export.md). Reuses existing
repository read methods exactly; the only new repository method is
ProjectRepository.list_by_ids/list_by_names-equivalent batched lookups
already added for Phase 6 import.
"""

import csv
import io
import json
import uuid

from app.core.exceptions import DomainValidationError
from app.domain.import_export_parsing import (
    ENTITY_COLUMNS,
    ExportFormat,
    ImportEntityType,
    sanitize_csv_cell,
)
from app.models.allocation import Allocation
from app.models.availability_exception import AvailabilityException
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
from app.models.team_membership import TeamMembership
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

# ---------------------------------------------------------------------------
# ORM row -> export-row-dict conversion. Every value is a plain string (or
# None) except WorkingSchedule's "entries" in JSON exports, which is a
# native array — see ENTITY_COLUMNS' header comment for why the shapes must
# stay symmetric with the importer.
# ---------------------------------------------------------------------------


def _person_row(person: Person) -> dict[str, object]:
    return {
        "id": str(person.id),
        "email": person.email,
        "first_name": person.first_name,
        "last_name": person.last_name,
        "display_name": person.display_name,
        "job_title": person.job_title,
        "timezone": person.timezone,
        "employment_status": person.employment_status.value,
        "created_at": person.created_at.isoformat(),
        "updated_at": person.updated_at.isoformat(),
    }


def _team_row(team: Team) -> dict[str, object]:
    return {
        "id": str(team.id),
        "name": team.name,
        "description": team.description,
        "created_at": team.created_at.isoformat(),
        "updated_at": team.updated_at.isoformat(),
    }


def _team_membership_row(
    membership: TeamMembership, people: dict[uuid.UUID, Person], teams: dict[uuid.UUID, Team]
) -> dict[str, object]:
    person = people.get(membership.person_id)
    team = teams.get(membership.team_id)
    return {
        "id": str(membership.id),
        "person_id": str(membership.person_id),
        "person_email": person.email if person else None,
        "team_id": str(membership.team_id),
        "team_name": team.name if team else None,
        "created_at": membership.created_at.isoformat(),
    }


def _project_row(project: Project) -> dict[str, object]:
    return {
        "id": str(project.id),
        "external_id": project.external_id,
        "name": project.name,
        "description": project.description,
        "status": project.status.value,
        "start_date": project.start_date.isoformat() if project.start_date else None,
        "end_date": project.end_date.isoformat() if project.end_date else None,
        "created_at": project.created_at.isoformat(),
        "updated_at": project.updated_at.isoformat(),
    }


def _allocation_row(
    allocation: Allocation, people: dict[uuid.UUID, Person], projects: dict[uuid.UUID, Project]
) -> dict[str, object]:
    person = people.get(allocation.person_id)
    project = projects.get(allocation.project_id)
    return {
        "id": str(allocation.id),
        "external_id": allocation.external_id,
        "person_id": str(allocation.person_id),
        "person_email": person.email if person else None,
        "project_id": str(allocation.project_id),
        "project_external_id": project.external_id if project else None,
        "start_date": allocation.start_date.isoformat(),
        "end_date": allocation.end_date.isoformat(),
        "allocation_hours": str(allocation.allocation_hours),
        "allocation_unit": allocation.allocation_unit.value,
        "notes": allocation.notes,
        "created_at": allocation.created_at.isoformat(),
        "updated_at": allocation.updated_at.isoformat(),
    }


def _working_schedule_row(
    schedule: WorkingSchedule, people: dict[uuid.UUID, Person], fmt: ExportFormat
) -> dict[str, object]:
    person = people.get(schedule.person_id)
    sorted_entries = sorted(schedule.entries, key=lambda entry: entry.weekday)
    entries_value: object = (
        [{"weekday": entry.weekday, "hours": str(entry.hours)} for entry in sorted_entries]
        if fmt == ExportFormat.JSON
        else ",".join(f"{entry.weekday}:{entry.hours}" for entry in sorted_entries)
    )
    return {
        "id": str(schedule.id),
        "external_id": schedule.external_id,
        "person_id": str(schedule.person_id),
        "person_email": person.email if person else None,
        "effective_start_date": (
            schedule.effective_start_date.isoformat() if schedule.effective_start_date else None
        ),
        "effective_end_date": (
            schedule.effective_end_date.isoformat() if schedule.effective_end_date else None
        ),
        "entries": entries_value,
        "created_at": schedule.created_at.isoformat(),
        "updated_at": schedule.updated_at.isoformat(),
    }


def _availability_exception_row(
    exception: AvailabilityException, people: dict[uuid.UUID, Person]
) -> dict[str, object]:
    person = people.get(exception.person_id)
    return {
        "id": str(exception.id),
        "external_id": exception.external_id,
        "person_id": str(exception.person_id),
        "person_email": person.email if person else None,
        "start_date": exception.start_date.isoformat(),
        "end_date": exception.end_date.isoformat(),
        "availability_type": exception.availability_type.value,
        "hours": str(exception.hours) if exception.hours is not None else None,
        "notes": exception.notes,
        "created_at": exception.created_at.isoformat(),
        "updated_at": exception.updated_at.isoformat(),
    }


def _skill_row(skill: Skill) -> dict[str, object]:
    return {
        "id": str(skill.id),
        "name": skill.name,
        "description": skill.description,
        "category": skill.category,
        "is_active": "true" if skill.is_active else "false",
        "created_at": skill.created_at.isoformat(),
        "updated_at": skill.updated_at.isoformat(),
    }


def _person_skill_row(
    person_skill: PersonSkill, people: dict[uuid.UUID, Person], skills: dict[uuid.UUID, Skill]
) -> dict[str, object]:
    person = people.get(person_skill.person_id)
    skill = skills.get(person_skill.skill_id)
    return {
        "id": str(person_skill.id),
        "person_id": str(person_skill.person_id),
        "person_email": person.email if person else None,
        "skill_id": str(person_skill.skill_id),
        "skill_name": skill.name if skill else None,
        "proficiency": person_skill.proficiency.value,
        "notes": person_skill.notes,
        "created_at": person_skill.created_at.isoformat(),
        "updated_at": person_skill.updated_at.isoformat(),
    }


def _project_skill_requirement_row(
    requirement: ProjectSkillRequirement,
    projects: dict[uuid.UUID, Project],
    skills: dict[uuid.UUID, Skill],
) -> dict[str, object]:
    project = projects.get(requirement.project_id)
    skill = skills.get(requirement.skill_id)
    return {
        "id": str(requirement.id),
        "project_id": str(requirement.project_id),
        "project_external_id": project.external_id if project else None,
        "skill_id": str(requirement.skill_id),
        "skill_name": skill.name if skill else None,
        "required_hours": str(requirement.required_hours),
        "minimum_proficiency": (
            requirement.minimum_proficiency.value if requirement.minimum_proficiency else None
        ),
        "notes": requirement.notes,
        "created_at": requirement.created_at.isoformat(),
        "updated_at": requirement.updated_at.isoformat(),
    }


def _risk_row(risk: Risk, projects: dict[uuid.UUID, Project]) -> dict[str, object]:
    project = projects.get(risk.project_id)
    return {
        "id": str(risk.id),
        "external_id": risk.external_id,
        "project_id": str(risk.project_id),
        "project_external_id": project.external_id if project else None,
        "description": risk.description,
        "cause": risk.cause,
        "potential_effect": risk.potential_effect,
        "probability": risk.probability.value,
        "impact": risk.impact.value,
        "response": risk.response,
        "owner_person_id": str(risk.owner_person_id) if risk.owner_person_id else None,
        "status": risk.status.value,
        "review_date": risk.review_date.isoformat() if risk.review_date else None,
        "created_at": risk.created_at.isoformat(),
        "updated_at": risk.updated_at.isoformat(),
    }


def _stakeholder_row(
    stakeholder: Stakeholder, projects: dict[uuid.UUID, Project]
) -> dict[str, object]:
    project = projects.get(stakeholder.project_id)
    return {
        "id": str(stakeholder.id),
        "project_id": str(stakeholder.project_id),
        "project_external_id": project.external_id if project else None,
        "name": stakeholder.name,
        "person_id": str(stakeholder.person_id) if stakeholder.person_id else None,
        "role": stakeholder.role,
        "influence": stakeholder.influence.value,
        "interest": stakeholder.interest.value,
        "decision_authority": stakeholder.decision_authority.value,
        "communication_needs": stakeholder.communication_needs,
        "created_at": stakeholder.created_at.isoformat(),
        "updated_at": stakeholder.updated_at.isoformat(),
    }


def _project_priority_score_row(
    score: ProjectPriorityScore,
    projects: dict[uuid.UUID, Project],
    frameworks: dict[uuid.UUID, PrioritizationFramework],
    fmt: ExportFormat,
) -> dict[str, object]:
    project = projects.get(score.project_id)
    framework = frameworks.get(score.framework_id)
    criteria_by_id = {c.id: c for c in framework.criteria} if framework else {}
    pairs = sorted(
        (criteria_by_id[v.criterion_id].key, v.value)
        for v in score.values
        if v.criterion_id in criteria_by_id
    )
    values_value: object = (
        [{"criterion_key": key, "value": str(value)} for key, value in pairs]
        if fmt == ExportFormat.JSON
        else ",".join(f"{key}:{value}" for key, value in pairs)
    )
    return {
        "id": str(score.id),
        "project_id": str(score.project_id),
        "project_external_id": project.external_id if project else None,
        "framework_id": str(score.framework_id),
        "framework_name": framework.name if framework else None,
        "category": score.category.value if score.category else None,
        "values": values_value,
        "notes": score.notes,
        "created_at": score.created_at.isoformat(),
        "updated_at": score.updated_at.isoformat(),
    }


def _project_dependency_row(
    dependency: ProjectDependency, projects: dict[uuid.UUID, Project]
) -> dict[str, object]:
    from_project = projects.get(dependency.from_project_id)
    to_project = projects.get(dependency.to_project_id)
    return {
        "id": str(dependency.id),
        "from_project_id": str(dependency.from_project_id),
        "from_project_external_id": from_project.external_id if from_project else None,
        "to_project_id": str(dependency.to_project_id),
        "to_project_external_id": to_project.external_id if to_project else None,
        "dependency_type": dependency.dependency_type.value,
        "created_at": dependency.created_at.isoformat(),
    }


class ExportService:
    """Organization-scoped (Phase 12) — export() and every _collect_rows
    branch take organization_id, threaded into every repository call
    including the "no filter given" fallback path. Before Phase 12 that
    fallback called each repository's unscoped list(), which would dump
    every organization's rows for that entity type — the single highest
    cross-tenant leak risk identified in the audit. Every repository's
    list()/list_filtered() now requires organization_id (see
    app/repositories/*.py), so there is no longer an unscoped path left to
    fall back to. See docs/adr/0012-organizations-multi-tenancy.md."""

    def __init__(
        self,
        person_repository: PersonRepository,
        team_repository: TeamRepository,
        team_membership_repository: TeamMembershipRepository,
        project_repository: ProjectRepository,
        allocation_repository: AllocationRepository,
        working_schedule_repository: WorkingScheduleRepository,
        availability_exception_repository: AvailabilityExceptionRepository,
        skill_repository: SkillRepository,
        person_skill_repository: PersonSkillRepository,
        project_skill_requirement_repository: ProjectSkillRequirementRepository,
        risk_repository: RiskRepository,
        stakeholder_repository: StakeholderRepository,
        prioritization_framework_repository: PrioritizationFrameworkRepository,
        project_priority_score_repository: ProjectPriorityScoreRepository,
        project_dependency_repository: ProjectDependencyRepository,
        *,
        max_rows: int,
    ) -> None:
        self.person_repository = person_repository
        self.team_repository = team_repository
        self.team_membership_repository = team_membership_repository
        self.project_repository = project_repository
        self.allocation_repository = allocation_repository
        self.working_schedule_repository = working_schedule_repository
        self.availability_exception_repository = availability_exception_repository
        self.skill_repository = skill_repository
        self.person_skill_repository = person_skill_repository
        self.project_skill_requirement_repository = project_skill_requirement_repository
        self.risk_repository = risk_repository
        self.stakeholder_repository = stakeholder_repository
        self.prioritization_framework_repository = prioritization_framework_repository
        self.project_priority_score_repository = project_priority_score_repository
        self.project_dependency_repository = project_dependency_repository
        self.max_rows = max_rows

    def export(
        self,
        organization_id: uuid.UUID,
        entity_type: ImportEntityType,
        fmt: ExportFormat,
        *,
        person_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> tuple[bytes, str, str]:
        rows = self._collect_rows(
            organization_id,
            entity_type,
            fmt,
            person_id=person_id,
            team_id=team_id,
            project_id=project_id,
        )
        content = self._serialize(entity_type, fmt, rows)
        filename = f"{entity_type.value}_export.{fmt.value}"
        media_type = "text/csv" if fmt == ExportFormat.CSV else "application/json"
        return content, filename, media_type

    def _check_cap(self, total: int) -> None:
        if total > self.max_rows:
            raise DomainValidationError(
                f"Export would return {total} rows, exceeding the {self.max_rows}-row limit "
                "— narrow your filters."
            )

    def _people_by_id(
        self, organization_id: uuid.UUID, ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, Person]:
        return {
            person.id: person
            for person in self.person_repository.list_by_ids(list(ids), organization_id)
        }

    def _teams_by_id(
        self, organization_id: uuid.UUID, ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, Team]:
        return {
            team.id: team
            for team in self.team_repository.list_by_ids(list(ids), organization_id)
        }

    def _projects_by_id(
        self, organization_id: uuid.UUID, ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, Project]:
        return {
            project.id: project
            for project in self.project_repository.list_by_ids(list(ids), organization_id)
        }

    def _skills_by_id(
        self, organization_id: uuid.UUID, ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, Skill]:
        return {
            skill.id: skill
            for skill in self.skill_repository.list_by_ids(list(ids), organization_id)
        }

    def _frameworks_by_id(
        self, organization_id: uuid.UUID, ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, PrioritizationFramework]:
        return {
            framework.id: framework
            for framework in self.prioritization_framework_repository.list_by_ids(
                list(ids), organization_id
            )
        }

    def _collect_rows(
        self,
        organization_id: uuid.UUID,
        entity_type: ImportEntityType,
        fmt: ExportFormat,
        *,
        person_id: uuid.UUID | None,
        team_id: uuid.UUID | None,
        project_id: uuid.UUID | None,
    ) -> list[dict[str, object]]:
        if entity_type == ImportEntityType.PERSON:
            items, total = self.person_repository.list(
                organization_id, limit=self.max_rows, offset=0
            )
            self._check_cap(total)
            return [_person_row(person) for person in items]

        if entity_type == ImportEntityType.TEAM:
            items, total = self.team_repository.list(
                organization_id, limit=self.max_rows, offset=0
            )
            self._check_cap(total)
            return [_team_row(team) for team in items]

        if entity_type == ImportEntityType.TEAM_MEMBERSHIP:
            if team_id is not None:
                memberships = self.team_membership_repository.list_for_team(
                    team_id, organization_id
                )
                self._check_cap(len(memberships))
            else:
                memberships, total = self.team_membership_repository.list(
                    organization_id, limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            people = self._people_by_id(organization_id, {m.person_id for m in memberships})
            teams = self._teams_by_id(organization_id, {m.team_id for m in memberships})
            return [_team_membership_row(m, people, teams) for m in memberships]

        if entity_type == ImportEntityType.PROJECT:
            items, total = self.project_repository.list(
                organization_id, limit=self.max_rows, offset=0
            )
            self._check_cap(total)
            return [_project_row(project) for project in items]

        if entity_type == ImportEntityType.ALLOCATION:
            allocations, total = self.allocation_repository.list_filtered(
                organization_id,
                person_id=person_id,
                project_id=project_id,
                limit=self.max_rows,
                offset=0,
            )
            self._check_cap(total)
            people = self._people_by_id(organization_id, {a.person_id for a in allocations})
            projects = self._projects_by_id(organization_id, {a.project_id for a in allocations})
            return [_allocation_row(a, people, projects) for a in allocations]

        if entity_type == ImportEntityType.WORKING_SCHEDULE:
            if person_id is not None:
                schedules = self.working_schedule_repository.list_for_person(
                    person_id, organization_id
                )
                self._check_cap(len(schedules))
            else:
                schedules, total = self.working_schedule_repository.list(
                    organization_id, limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            people = self._people_by_id(organization_id, {s.person_id for s in schedules})
            return [_working_schedule_row(s, people, fmt) for s in schedules]

        if entity_type == ImportEntityType.AVAILABILITY_EXCEPTION:
            exceptions, total = self.availability_exception_repository.list_filtered(
                organization_id, person_id=person_id, limit=self.max_rows, offset=0
            )
            self._check_cap(total)
            people = self._people_by_id(organization_id, {e.person_id for e in exceptions})
            return [_availability_exception_row(e, people) for e in exceptions]

        if entity_type == ImportEntityType.SKILL:
            items, total = self.skill_repository.list_filtered(
                organization_id, limit=self.max_rows, offset=0
            )
            self._check_cap(total)
            return [_skill_row(skill) for skill in items]

        if entity_type == ImportEntityType.PERSON_SKILL:
            if person_id is not None:
                person_skills = self.person_skill_repository.list_for_person(
                    person_id, organization_id
                )
                self._check_cap(len(person_skills))
            else:
                person_skills, total = self.person_skill_repository.list(
                    organization_id, limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            people = self._people_by_id(organization_id, {ps.person_id for ps in person_skills})
            skills = self._skills_by_id(organization_id, {ps.skill_id for ps in person_skills})
            return [_person_skill_row(ps, people, skills) for ps in person_skills]

        if entity_type == ImportEntityType.PROJECT_SKILL_REQUIREMENT:
            requirements: list[ProjectSkillRequirement]
            if project_id is not None:
                requirements = self.project_skill_requirement_repository.list_for_project(
                    project_id, organization_id
                )
                self._check_cap(len(requirements))
            else:
                requirements, total = self.project_skill_requirement_repository.list(
                    organization_id, limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            projects = self._projects_by_id(organization_id, {r.project_id for r in requirements})
            skills = self._skills_by_id(organization_id, {r.skill_id for r in requirements})
            return [_project_skill_requirement_row(r, projects, skills) for r in requirements]

        if entity_type == ImportEntityType.RISK:
            risks: list[Risk]
            if project_id is not None:
                risks = self.risk_repository.list_for_project(project_id, organization_id)
                self._check_cap(len(risks))
            else:
                risks, total = self.risk_repository.list(
                    organization_id, limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            projects = self._projects_by_id(organization_id, {r.project_id for r in risks})
            return [_risk_row(r, projects) for r in risks]

        if entity_type == ImportEntityType.STAKEHOLDER:
            stakeholders: list[Stakeholder]
            if project_id is not None:
                stakeholders = self.stakeholder_repository.list_for_project(
                    project_id, organization_id
                )
                self._check_cap(len(stakeholders))
            else:
                stakeholders, total = self.stakeholder_repository.list(
                    organization_id, limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            projects = self._projects_by_id(organization_id, {s.project_id for s in stakeholders})
            return [_stakeholder_row(s, projects) for s in stakeholders]

        if entity_type == ImportEntityType.PROJECT_PRIORITY_SCORE:
            scores: list[ProjectPriorityScore]
            if project_id is not None:
                scores = self.project_priority_score_repository.list_for_project(
                    project_id, organization_id
                )
                self._check_cap(len(scores))
            else:
                scores, total = self.project_priority_score_repository.list_filtered(
                    organization_id, limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            projects = self._projects_by_id(organization_id, {s.project_id for s in scores})
            frameworks = self._frameworks_by_id(organization_id, {s.framework_id for s in scores})
            return [_project_priority_score_row(s, projects, frameworks, fmt) for s in scores]

        # PROJECT_DEPENDENCY — both directions via list_for_project (an
        # edge where this project is either the from or to side), matching
        # the direct API's list_project_dependencies route exactly; the
        # organization-wide fallback reuses list_for_organization, the
        # same method the Dependency Graph view already calls.
        dependencies: list[ProjectDependency]
        if project_id is not None:
            dependencies = self.project_dependency_repository.list_for_project(
                project_id, organization_id
            )
            self._check_cap(len(dependencies))
        else:
            dependencies = self.project_dependency_repository.list_for_organization(
                organization_id
            )
            self._check_cap(len(dependencies))
        projects = self._projects_by_id(
            organization_id,
            {d.from_project_id for d in dependencies} | {d.to_project_id for d in dependencies},
        )
        return [_project_dependency_row(d, projects) for d in dependencies]

    def _serialize(
        self, entity_type: ImportEntityType, fmt: ExportFormat, rows: list[dict[str, object]]
    ) -> bytes:
        if fmt == ExportFormat.JSON:
            return json.dumps(rows, indent=2).encode("utf-8")

        fieldnames = [spec.name for spec in ENTITY_COLUMNS[entity_type]]
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            sanitized = {
                key: sanitize_csv_cell(str(value)) if value is not None else ""
                for key, value in row.items()
            }
            writer.writerow(sanitized)
        return buffer.getvalue().encode("utf-8")
