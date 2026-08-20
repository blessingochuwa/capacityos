import uuid

from sqlalchemy import func, select

from app.models.project_skill_requirement import ProjectSkillRequirement
from app.repositories.base import BaseRepository


class ProjectSkillRequirementRepository(BaseRepository[ProjectSkillRequirement]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = ProjectSkillRequirement

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> ProjectSkillRequirement | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(ProjectSkillRequirement).where(
                ProjectSkillRequirement.id == id_,
                ProjectSkillRequirement.organization_id == organization_id,
            )
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[ProjectSkillRequirement], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(ProjectSkillRequirement)
                .where(ProjectSkillRequirement.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(ProjectSkillRequirement)
                .where(ProjectSkillRequirement.organization_id == organization_id)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def get_by_project_and_skill(
        self, project_id: uuid.UUID, skill_id: uuid.UUID, organization_id: uuid.UUID
    ) -> ProjectSkillRequirement | None:
        return self.session.scalar(
            select(ProjectSkillRequirement).where(
                ProjectSkillRequirement.project_id == project_id,
                ProjectSkillRequirement.skill_id == skill_id,
                ProjectSkillRequirement.organization_id == organization_id,
            )
        )

    def list_for_project(
        self, project_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[ProjectSkillRequirement]:
        return list(
            self.session.scalars(
                select(ProjectSkillRequirement)
                .where(
                    ProjectSkillRequirement.project_id == project_id,
                    ProjectSkillRequirement.organization_id == organization_id,
                )
                .order_by(ProjectSkillRequirement.created_at)
            )
        )

    def list_for_projects(
        self, project_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[ProjectSkillRequirement]:
        """Batched — one query for the whole id list, used by Phase 6 import
        identity resolution instead of one list_for_project call per row."""
        if not project_ids:
            return []
        return list(
            self.session.scalars(
                select(ProjectSkillRequirement).where(
                    ProjectSkillRequirement.project_id.in_(project_ids),
                    ProjectSkillRequirement.organization_id == organization_id,
                )
            )
        )

    def list_by_pairs(
        self, pairs: list[tuple[uuid.UUID, uuid.UUID]], organization_id: uuid.UUID
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
                ProjectSkillRequirement.organization_id == organization_id,
            )
        )
        pair_set = set(pairs)
        return [row for row in candidates if (row.project_id, row.skill_id) in pair_set]
