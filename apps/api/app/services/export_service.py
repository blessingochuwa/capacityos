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
from app.models.project import Project
from app.models.project_skill_requirement import ProjectSkillRequirement
from app.models.skill import Skill
from app.models.team import Team
from app.models.team_membership import TeamMembership
from app.models.working_schedule import WorkingSchedule
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_skill_requirement import ProjectSkillRequirementRepository
from app.repositories.skill import SkillRepository
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


class ExportService:
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
        self.max_rows = max_rows

    def export(
        self,
        entity_type: ImportEntityType,
        fmt: ExportFormat,
        *,
        person_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
    ) -> tuple[bytes, str, str]:
        rows = self._collect_rows(
            entity_type, fmt, person_id=person_id, team_id=team_id, project_id=project_id
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

    def _people_by_id(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, Person]:
        return {person.id: person for person in self.person_repository.list_by_ids(list(ids))}

    def _teams_by_id(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, Team]:
        return {team.id: team for team in self.team_repository.list_by_ids(list(ids))}

    def _projects_by_id(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, Project]:
        return {
            project.id: project for project in self.project_repository.list_by_ids(list(ids))
        }

    def _skills_by_id(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, Skill]:
        return {skill.id: skill for skill in self.skill_repository.list_by_ids(list(ids))}

    def _collect_rows(
        self,
        entity_type: ImportEntityType,
        fmt: ExportFormat,
        *,
        person_id: uuid.UUID | None,
        team_id: uuid.UUID | None,
        project_id: uuid.UUID | None,
    ) -> list[dict[str, object]]:
        if entity_type == ImportEntityType.PERSON:
            items, total = self.person_repository.list(limit=self.max_rows, offset=0)
            self._check_cap(total)
            return [_person_row(person) for person in items]

        if entity_type == ImportEntityType.TEAM:
            items, total = self.team_repository.list(limit=self.max_rows, offset=0)
            self._check_cap(total)
            return [_team_row(team) for team in items]

        if entity_type == ImportEntityType.TEAM_MEMBERSHIP:
            if team_id is not None:
                memberships = self.team_membership_repository.list_for_team(team_id)
                self._check_cap(len(memberships))
            else:
                memberships, total = self.team_membership_repository.list(
                    limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            people = self._people_by_id({m.person_id for m in memberships})
            teams = self._teams_by_id({m.team_id for m in memberships})
            return [_team_membership_row(m, people, teams) for m in memberships]

        if entity_type == ImportEntityType.PROJECT:
            items, total = self.project_repository.list(limit=self.max_rows, offset=0)
            self._check_cap(total)
            return [_project_row(project) for project in items]

        if entity_type == ImportEntityType.ALLOCATION:
            allocations, total = self.allocation_repository.list_filtered(
                person_id=person_id, project_id=project_id, limit=self.max_rows, offset=0
            )
            self._check_cap(total)
            people = self._people_by_id({a.person_id for a in allocations})
            projects = self._projects_by_id({a.project_id for a in allocations})
            return [_allocation_row(a, people, projects) for a in allocations]

        if entity_type == ImportEntityType.WORKING_SCHEDULE:
            if person_id is not None:
                schedules = self.working_schedule_repository.list_for_person(person_id)
                self._check_cap(len(schedules))
            else:
                schedules, total = self.working_schedule_repository.list(
                    limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            people = self._people_by_id({s.person_id for s in schedules})
            return [_working_schedule_row(s, people, fmt) for s in schedules]

        if entity_type == ImportEntityType.AVAILABILITY_EXCEPTION:
            exceptions, total = self.availability_exception_repository.list_filtered(
                person_id=person_id, limit=self.max_rows, offset=0
            )
            self._check_cap(total)
            people = self._people_by_id({e.person_id for e in exceptions})
            return [_availability_exception_row(e, people) for e in exceptions]

        if entity_type == ImportEntityType.SKILL:
            items, total = self.skill_repository.list_filtered(limit=self.max_rows, offset=0)
            self._check_cap(total)
            return [_skill_row(skill) for skill in items]

        if entity_type == ImportEntityType.PERSON_SKILL:
            if person_id is not None:
                person_skills = self.person_skill_repository.list_for_person(person_id)
                self._check_cap(len(person_skills))
            else:
                person_skills, total = self.person_skill_repository.list(
                    limit=self.max_rows, offset=0
                )
                self._check_cap(total)
            people = self._people_by_id({ps.person_id for ps in person_skills})
            skills = self._skills_by_id({ps.skill_id for ps in person_skills})
            return [_person_skill_row(ps, people, skills) for ps in person_skills]

        requirements: list[ProjectSkillRequirement]
        if project_id is not None:
            requirements = self.project_skill_requirement_repository.list_for_project(project_id)
            self._check_cap(len(requirements))
        else:
            requirements, total = self.project_skill_requirement_repository.list(
                limit=self.max_rows, offset=0
            )
            self._check_cap(total)
        projects = self._projects_by_id({r.project_id for r in requirements})
        skills = self._skills_by_id({r.skill_id for r in requirements})
        return [_project_skill_requirement_row(r, projects, skills) for r in requirements]

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
