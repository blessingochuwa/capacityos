"""Phase 21 — portfolio snapshots
(docs/adr/0021-portfolio-snapshots.md).

Deliberately its own service, not a method bolted onto
ProjectPriorityScoreService: it reuses that service's rank_portfolio
verbatim (never a second ranking computation) to build the frozen record
this phase persists, without ProjectPriorityScoreService needing to know
snapshots exist at all — the same separation
app/services/scenario_priority.py already established for Phase 20.
"""

import uuid

from app.models.portfolio_snapshot import PortfolioSnapshot
from app.repositories.portfolio_snapshot import PortfolioSnapshotRepository
from app.services.project_priority_score import ProjectPriorityScoreService


class PortfolioSnapshotService:
    """Organization-scoped (Phase 12) — framework_id resolution/validation
    is delegated entirely to ProjectPriorityScoreService.rank_portfolio
    below (raises NotFoundError for a missing or cross-organization
    framework exactly like the live portfolio board already does), rather
    than re-implemented here."""

    def __init__(
        self,
        repository: PortfolioSnapshotRepository,
        score_service: ProjectPriorityScoreService,
    ) -> None:
        self.repository = repository
        self.score_service = score_service

    def create(self, organization_id: uuid.UUID, framework_id: uuid.UUID) -> PortfolioSnapshot:
        """Freezes the CURRENT live ranking
        (ProjectPriorityScoreService.rank_portfolio, unchanged) into a
        standalone, immutable row. Every value visible in `entries` is
        copied out at this moment — a later project rename, re-score, or
        deletion, or a later framework rename, must never change what an
        already-taken snapshot shows (see PortfolioSnapshot's model
        docstring)."""
        framework, ranked = self.score_service.rank_portfolio(organization_id, framework_id)
        entries = [
            {
                "project_id": str(project.id),
                "project_name": project.name,
                "score": str(result.score) if result.score is not None else None,
                "rank": rank,
                "missing_criteria": list(result.missing_criteria),
                "breakdown": {key: str(value) for key, value in result.breakdown.items()},
                "category": result.category.value if result.category is not None else None,
            }
            for project, _score, result, rank in ranked
        ]

        snapshot = self.repository.add(
            PortfolioSnapshot(
                organization_id=organization_id,
                framework_id=framework.id,
                framework_name=framework.name,
                framework_type=framework.framework_type,
                entries=entries,
            )
        )
        return snapshot

    def list(
        self,
        organization_id: uuid.UUID,
        *,
        framework_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[PortfolioSnapshot], int]:
        return self.repository.list_(
            organization_id, framework_id=framework_id, limit=limit, offset=offset
        )
