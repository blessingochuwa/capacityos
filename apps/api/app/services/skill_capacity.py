"""Orchestrates skill-aware capacity/coverage on top of the existing Phase 2
capacity engine (CLAUDE.md §39 Phase 7).

No second capacity engine: remaining_capacity for every person considered
here comes from app/domain/capacity.py::calculate_period_capacity via the
same batched app/services/planning_facts.py::load_people_facts helper
CapacityService and InsightService already use. This module's only job is
qualification (app/domain/skills.py) and assembling the response shapes —
see docs/adr/0007-phase-7-skills-bottleneck-analysis.md.
"""

import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal

from app.core.exceptions import DomainValidationError, NotFoundError
from app.domain.capacity import ZERO, calculate_period_capacity
from app.domain.skills import (
    QualifiedPerson,
    calculate_skill_coverage,
    is_qualified,
)
from app.models.person_skill import PersonSkill
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
from app.schemas.skill_capacity import (
    ProjectSkillCoverageRead,
    QualifiedPersonRead,
    SkillCoverageRead,
    TeamSkillCapacityEntryRead,
    TeamSkillCapacityRead,
)
from app.services.capacity import MAX_RANGE_DAYS
from app.services.planning_facts import load_people_facts


class SkillCapacityService:
    def __init__(
        self,
        person_skill_repository: PersonSkillRepository,
        skill_repository: SkillRepository,
        person_repository: PersonRepository,
        project_repository: ProjectRepository,
        project_skill_requirement_repository: ProjectSkillRequirementRepository,
        team_repository: TeamRepository,
        team_membership_repository: TeamMembershipRepository,
        schedule_repository: WorkingScheduleRepository,
        availability_repository: AvailabilityExceptionRepository,
        allocation_repository: AllocationRepository,
    ) -> None:
        self.person_skill_repository = person_skill_repository
        self.skill_repository = skill_repository
        self.person_repository = person_repository
        self.project_repository = project_repository
        self.project_skill_requirement_repository = project_skill_requirement_repository
        self.team_repository = team_repository
        self.team_membership_repository = team_membership_repository
        self.schedule_repository = schedule_repository
        self.availability_repository = availability_repository
        self.allocation_repository = allocation_repository

    def _validate_range(self, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise DomainValidationError("end_date cannot precede start_date")
        if (end_date - start_date).days + 1 > MAX_RANGE_DAYS:
            raise DomainValidationError(f"date range cannot exceed {MAX_RANGE_DAYS} days")

    def _remaining_capacity_by_person(
        self,
        organization_id: uuid.UUID,
        person_ids: list[uuid.UUID],
        start_date: date,
        end_date: date,
    ) -> dict[uuid.UUID, Decimal]:
        facts_by_person = load_people_facts(
            self.schedule_repository,
            self.availability_repository,
            self.allocation_repository,
            person_ids,
            start_date,
            end_date,
            organization_id,
        )
        results: dict[uuid.UUID, Decimal] = {}
        for person_id, facts in facts_by_person.items():
            result = calculate_period_capacity(
                start_date,
                end_date,
                list(facts.schedules),
                list(facts.exceptions),
                list(facts.allocations),
            )
            results[person_id] = result.remaining_capacity
        return results

    def get_project_skill_coverage(
        self, organization_id: uuid.UUID, project_id: uuid.UUID, start_date: date, end_date: date
    ) -> ProjectSkillCoverageRead:
        self._validate_range(start_date, end_date)
        project = self.project_repository.get(project_id, organization_id)
        if project is None:
            raise NotFoundError("Project", project_id)

        requirements = self.project_skill_requirement_repository.list_for_project(
            project_id, organization_id
        )
        skill_ids = [requirement.skill_id for requirement in requirements]
        skills_by_id = {
            skill.id: skill
            for skill in self.skill_repository.list_by_ids(skill_ids, organization_id)
        }
        # organization_id here is what keeps this "candidate pool" scoped to
        # this organization's people only — Phase 7 originally called this
        # pool "org-wide" meaning "every holder of the skill," which before
        # Phase 12 meant globally unscoped across the whole table.
        person_skills = self.person_skill_repository.list_for_skills(skill_ids, organization_id)
        person_skills_by_skill: dict[uuid.UUID, list[PersonSkill]] = defaultdict(list)
        for row in person_skills:
            person_skills_by_skill[row.skill_id].append(row)

        all_person_ids = sorted({row.person_id for row in person_skills}, key=str)
        remaining_by_person = self._remaining_capacity_by_person(
            organization_id, all_person_ids, start_date, end_date
        )
        person_labels = self._person_labels(all_person_ids, organization_id)

        coverage_entries: list[SkillCoverageRead] = []
        for requirement in requirements:
            skill = skills_by_id.get(requirement.skill_id)
            if skill is None or not skill.is_active:
                continue
            qualified = [
                QualifiedPerson(
                    person_id=row.person_id,
                    proficiency=row.proficiency,
                    remaining_capacity=remaining_by_person.get(row.person_id, ZERO),
                )
                for row in person_skills_by_skill.get(requirement.skill_id, [])
                if is_qualified(row.proficiency, requirement.minimum_proficiency)
            ]
            result = calculate_skill_coverage(requirement.required_hours, qualified)
            coverage_entries.append(
                SkillCoverageRead(
                    requirement_id=requirement.id,
                    skill_id=requirement.skill_id,
                    skill_label=skill.name,
                    required_hours=requirement.required_hours,
                    minimum_proficiency=requirement.minimum_proficiency,
                    qualified_available_hours=result.qualified_available_hours,
                    coverage_ratio=result.coverage_ratio,
                    gap_hours=result.gap_hours,
                    qualified_people=[
                        QualifiedPersonRead(
                            person_id=person.person_id,
                            person_label=person_labels.get(person.person_id, "Unknown"),
                            proficiency=person.proficiency,
                            qualified_available_hours=person.qualified_available_hours,
                        )
                        for person in qualified
                    ],
                )
            )

        return ProjectSkillCoverageRead(
            project_id=project_id,
            project_label=project.name,
            start_date=start_date,
            end_date=end_date,
            requirements=coverage_entries,
        )

    def get_team_skill_capacity(
        self, organization_id: uuid.UUID, team_id: uuid.UUID, start_date: date, end_date: date
    ) -> TeamSkillCapacityRead:
        self._validate_range(start_date, end_date)
        team = self.team_repository.get(team_id, organization_id)
        if team is None:
            raise NotFoundError("Team", team_id)

        member_ids = [
            membership.person_id
            for membership in self.team_membership_repository.list_for_team(
                team_id, organization_id
            )
        ]
        person_skills = self.person_skill_repository.list_for_people(member_ids, organization_id)
        skills_by_id = {
            skill.id: skill
            for skill in self.skill_repository.list_by_ids(
                sorted({row.skill_id for row in person_skills}, key=str), organization_id
            )
        }
        person_skills_by_skill: dict[uuid.UUID, list[PersonSkill]] = defaultdict(list)
        for row in person_skills:
            if skills_by_id.get(row.skill_id) is not None and skills_by_id[row.skill_id].is_active:
                person_skills_by_skill[row.skill_id].append(row)

        remaining_by_person = self._remaining_capacity_by_person(
            organization_id, member_ids, start_date, end_date
        )
        person_labels = self._person_labels(member_ids, organization_id)

        entries: list[TeamSkillCapacityEntryRead] = []
        for skill_id, rows in sorted(
            person_skills_by_skill.items(), key=lambda pair: skills_by_id[pair[0]].name
        ):
            skill = skills_by_id[skill_id]
            qualified = [
                QualifiedPerson(
                    person_id=row.person_id,
                    proficiency=row.proficiency,
                    remaining_capacity=remaining_by_person.get(row.person_id, ZERO),
                )
                for row in rows
            ]
            total_hours = sum((person.qualified_available_hours for person in qualified), ZERO)
            entries.append(
                TeamSkillCapacityEntryRead(
                    skill_id=skill_id,
                    skill_label=skill.name,
                    qualified_available_hours=total_hours,
                    qualified_people=[
                        QualifiedPersonRead(
                            person_id=person.person_id,
                            person_label=person_labels.get(person.person_id, "Unknown"),
                            proficiency=person.proficiency,
                            qualified_available_hours=person.qualified_available_hours,
                        )
                        for person in qualified
                    ],
                )
            )

        return TeamSkillCapacityRead(
            team_id=team_id,
            team_label=team.name,
            start_date=start_date,
            end_date=end_date,
            skills=entries,
        )

    def _person_labels(
        self, person_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> dict[uuid.UUID, str]:
        return {
            person.id: person.display_name
            for person in self.person_repository.list_by_ids(person_ids, organization_id)
        }
