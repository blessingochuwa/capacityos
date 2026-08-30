import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.project_priority_score import ProjectPriorityScore
from app.repositories.base import BaseRepository

_EAGER_LOAD = (
    selectinload(ProjectPriorityScore.values),
    selectinload(ProjectPriorityScore.framework),
)
"""Every read of a score needs its values (to compute the score) and its
framework (to know framework_type and weights) — loaded eagerly here so
the service layer never triggers a lazy-load N+1 while building a
portfolio ranking (CLAUDE.md §27)."""


class ProjectPriorityScoreRepository(BaseRepository[ProjectPriorityScore]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = ProjectPriorityScore

    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, id_: uuid.UUID, organization_id: uuid.UUID
    ) -> ProjectPriorityScore | None:
        return self.session.scalar(
            select(ProjectPriorityScore)
            .options(*_EAGER_LOAD)
            .where(
                ProjectPriorityScore.id == id_,
                ProjectPriorityScore.organization_id == organization_id,
            )
        )

    def get_by_project_and_framework(
        self, project_id: uuid.UUID, framework_id: uuid.UUID, organization_id: uuid.UUID
    ) -> ProjectPriorityScore | None:
        return self.session.scalar(
            select(ProjectPriorityScore)
            .options(*_EAGER_LOAD)
            .where(
                ProjectPriorityScore.project_id == project_id,
                ProjectPriorityScore.framework_id == framework_id,
                ProjectPriorityScore.organization_id == organization_id,
            )
        )

    def list_for_project(
        self, project_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[ProjectPriorityScore]:
        return list(
            self.session.scalars(
                select(ProjectPriorityScore)
                .options(*_EAGER_LOAD)
                .where(
                    ProjectPriorityScore.project_id == project_id,
                    ProjectPriorityScore.organization_id == organization_id,
                )
                .order_by(ProjectPriorityScore.created_at)
            )
        )

    def list_filtered(
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[ProjectPriorityScore], int]:
        """Org-wide, paginated — Phase 36 import/export's "no project_id
        filter given" fallback, matching Skill/Risk/Stakeholder's
        list()/list_filtered() shape."""
        stmt = select(ProjectPriorityScore).where(
            ProjectPriorityScore.organization_id == organization_id
        )
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.session.scalars(
                stmt.options(*_EAGER_LOAD)
                .order_by(ProjectPriorityScore.created_at)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def list_for_projects(
        self, project_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[ProjectPriorityScore]:
        """Batched — one query for the whole id list, used by Phase 36
        import identity resolution instead of one list_for_project call
        per row (matches ProjectSkillRequirementRepository.list_for_projects)."""
        if not project_ids:
            return []
        return list(
            self.session.scalars(
                select(ProjectPriorityScore)
                .options(*_EAGER_LOAD)
                .where(
                    ProjectPriorityScore.project_id.in_(project_ids),
                    ProjectPriorityScore.organization_id == organization_id,
                )
            )
        )

    def list_for_framework(
        self, framework_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[ProjectPriorityScore]:
        """Every project currently scored under this framework — the input
        set app/services/prioritization.py::rank_portfolio ranks. A
        project never scored under this framework simply has no row here
        and is absent from the ranking, rather than appearing with an
        invented default score."""
        return list(
            self.session.scalars(
                select(ProjectPriorityScore)
                .options(*_EAGER_LOAD, selectinload(ProjectPriorityScore.project))
                .where(
                    ProjectPriorityScore.framework_id == framework_id,
                    ProjectPriorityScore.organization_id == organization_id,
                )
            )
        )
