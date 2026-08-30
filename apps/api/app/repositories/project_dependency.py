import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from app.models.enums import ProjectDependencyType
from app.models.project_dependency import ProjectDependency
from app.repositories.base import BaseRepository


class ProjectDependencyRepository(BaseRepository[ProjectDependency]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = ProjectDependency

    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, id_: uuid.UUID, organization_id: uuid.UUID
    ) -> ProjectDependency | None:
        return self.session.scalar(
            select(ProjectDependency)
            .options(
                joinedload(ProjectDependency.from_project),
                joinedload(ProjectDependency.to_project),
            )
            .where(
                ProjectDependency.id == id_,
                ProjectDependency.organization_id == organization_id,
            )
        )

    def get_by_natural_key(
        self,
        from_project_id: uuid.UUID,
        to_project_id: uuid.UUID,
        dependency_type: ProjectDependencyType,
        organization_id: uuid.UUID,
    ) -> ProjectDependency | None:
        return self.session.scalar(
            select(ProjectDependency).where(
                ProjectDependency.from_project_id == from_project_id,
                ProjectDependency.to_project_id == to_project_id,
                ProjectDependency.dependency_type == dependency_type,
                ProjectDependency.organization_id == organization_id,
            )
        )

    def list_for_project(
        self, project_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[ProjectDependency]:
        """Both directions — every edge where this project is either the
        `from` or the `to` side. The service derives which is "outgoing"
        vs. "blocked_by" from each row's from_project_id/to_project_id
        rather than this method picking a direction, since a caller may
        want either view (or both, as list_for_project's caller does)."""
        return list(
            self.session.scalars(
                select(ProjectDependency)
                .options(
                    joinedload(ProjectDependency.from_project),
                    joinedload(ProjectDependency.to_project),
                )
                .where(
                    ProjectDependency.organization_id == organization_id,
                    or_(
                        ProjectDependency.from_project_id == project_id,
                        ProjectDependency.to_project_id == project_id,
                    ),
                )
                .order_by(ProjectDependency.created_at)
            )
        )

    def list_for_projects(
        self, project_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[ProjectDependency]:
        """Batched — every edge where EITHER side is in project_ids, one
        query for the whole id list, used by Phase 37 import identity
        resolution instead of one list_for_project call per row (matches
        ProjectSkillRequirementRepository.list_for_projects)."""
        if not project_ids:
            return []
        return list(
            self.session.scalars(
                select(ProjectDependency).where(
                    ProjectDependency.organization_id == organization_id,
                    or_(
                        ProjectDependency.from_project_id.in_(project_ids),
                        ProjectDependency.to_project_id.in_(project_ids),
                    ),
                )
            )
        )

    def list_for_organization(self, organization_id: uuid.UUID) -> list[ProjectDependency]:
        """Every dependency edge in the organization — used to build the
        Dependency Graph view. Unfiltered by project since a graph is
        inherently a whole-organization view."""
        return list(
            self.session.scalars(
                select(ProjectDependency)
                .options(
                    joinedload(ProjectDependency.from_project),
                    joinedload(ProjectDependency.to_project),
                )
                .where(ProjectDependency.organization_id == organization_id)
                .order_by(ProjectDependency.created_at)
            )
        )

    def list_blocks_edges(self, organization_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """(from_project_id, to_project_id) pairs for every BLOCKS edge in
        the organization — the exact shape app.domain.prioritization.
        detects_cycle expects. Scoped to BLOCKS only, matching
        detects_cycle's own docstring: related/enables don't imply a
        strict ordering, so they're excluded from the cycle check."""
        rows = self.session.execute(
            select(ProjectDependency.from_project_id, ProjectDependency.to_project_id).where(
                ProjectDependency.organization_id == organization_id,
                ProjectDependency.dependency_type == ProjectDependencyType.BLOCKS,
            )
        )
        return [(row.from_project_id, row.to_project_id) for row in rows]
