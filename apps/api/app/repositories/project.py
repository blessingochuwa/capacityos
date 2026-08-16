import uuid

from sqlalchemy import select

from app.models.project import Project
from app.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    model = Project

    def list_by_ids(self, project_ids: list[uuid.UUID]) -> list[Project]:
        """Batched lookup for a known set of ids — mirrors
        PersonRepository.list_by_ids exactly. Used by
        InsightService.get_team_summary to label every project a team's
        people are allocated to, without a query per project."""
        if not project_ids:
            return []
        return list(self.session.scalars(select(Project).where(Project.id.in_(project_ids))))

    def get_by_external_id(self, external_id: str) -> Project | None:
        return self.session.scalar(select(Project).where(Project.external_id == external_id))

    def list_by_external_ids(self, external_ids: list[str]) -> list[Project]:
        """Batched lookup for Phase 6 import identity resolution — one query
        for the whole file's referenced/matched external_ids, not one per
        row (CLAUDE.md §27)."""
        if not external_ids:
            return []
        return list(
            self.session.scalars(select(Project).where(Project.external_id.in_(external_ids)))
        )
