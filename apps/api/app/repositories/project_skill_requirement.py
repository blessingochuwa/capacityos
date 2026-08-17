import uuid

from sqlalchemy import select

from app.models.project_skill_requirement import ProjectSkillRequirement
from app.repositories.base import BaseRepository


class ProjectSkillRequirementRepository(BaseRepository[ProjectSkillRequirement]):
    model = ProjectSkillRequirement

    def get_by_project_and_skill(
        self, project_id: uuid.UUID, skill_id: uuid.UUID
    ) -> ProjectSkillRequirement | None:
        return self.session.scalar(
            select(ProjectSkillRequirement).where(
                ProjectSkillRequirement.project_id == project_id,
                ProjectSkillRequirement.skill_id == skill_id,
            )
        )

    def list_for_project(self, project_id: uuid.UUID) -> list[ProjectSkillRequirement]:
        return list(
            self.session.scalars(
                select(ProjectSkillRequirement)
                .where(ProjectSkillRequirement.project_id == project_id)
                .order_by(ProjectSkillRequirement.created_at)
            )
        )

    def list_for_projects(self, project_ids: list[uuid.UUID]) -> list[ProjectSkillRequirement]:
        """Batched — one query for the whole id list, used by Phase 6 import
        identity resolution instead of one list_for_project call per row."""
        if not project_ids:
            return []
        return list(
            self.session.scalars(
                select(ProjectSkillRequirement).where(
                    ProjectSkillRequirement.project_id.in_(project_ids)
                )
            )
        )

    def list_by_pairs(
        self, pairs: list[tuple[uuid.UUID, uuid.UUID]]
    ) -> list[ProjectSkillRequirement]:
        """Batched lookup for Phase 6 import identity resolution — existing
        (project_id, skill_id) rows for a set of candidate pairs."""
        if not pairs:
            return []
        project_ids = [pair[0] for pair in pairs]
        skill_ids = [pair[1] for pair in pairs]
        candidates = self.session.scalars(
            select(ProjectSkillRequirement).where(
                ProjectSkillRequirement.project_id.in_(project_ids),
                ProjectSkillRequirement.skill_id.in_(skill_ids),
            )
        )
        pair_set = set(pairs)
        return [row for row in candidates if (row.project_id, row.skill_id) in pair_set]
