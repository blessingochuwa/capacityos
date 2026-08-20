import uuid

from sqlalchemy import func, select

from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = Project

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> Project | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(Project).where(Project.id == id_, Project.organization_id == organization_id)
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[Project], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(Project)
                .where(Project.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(Project)
                .where(Project.organization_id == organization_id)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def list_by_ids(
        self, project_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[Project]:
        """Batched lookup for a known set of ids — mirrors
        PersonRepository.list_by_ids exactly. Used by
        InsightService.get_team_summary to label every project a team's
        people are allocated to, without a query per project."""
        if not project_ids:
            return []
        return list(
            self.session.scalars(
                select(Project).where(
                    Project.id.in_(project_ids), Project.organization_id == organization_id
                )
            )
        )

    def get_by_external_id(self, external_id: str, organization_id: uuid.UUID) -> Project | None:
        return self.session.scalar(
            select(Project).where(
                Project.external_id == external_id, Project.organization_id == organization_id
            )
        )

    def list_by_external_ids(
        self, external_ids: list[str], organization_id: uuid.UUID
    ) -> list[Project]:
        """Batched lookup for Phase 6 import identity resolution — one query
        for the whole file's referenced/matched external_ids, not one per
        row (CLAUDE.md §27)."""
        if not external_ids:
            return []
        return list(
            self.session.scalars(
                select(Project).where(
                    Project.external_id.in_(external_ids),
                    Project.organization_id == organization_id,
                )
            )
        )
