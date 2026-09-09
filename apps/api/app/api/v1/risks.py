import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, require_permission
from app.core.database import get_db
from app.domain.authorization import Permission
from app.domain.risk import RiskExposure
from app.models.enums import RiskStatus
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.risk import RiskRepository
from app.schemas.common import Page
from app.schemas.risk import RiskRead, risk_to_read
from app.services.risk import RiskService

router = APIRouter(prefix="/api/v1/risks", tags=["risks"])


def get_risk_service(db: Session = Depends(get_db)) -> RiskService:
    return RiskService(RiskRepository(db), ProjectRepository(db), PersonRepository(db))


@router.get("", response_model=Page[RiskRead])
def list_organization_risks(
    project_id: uuid.UUID | None = None,
    status: RiskStatus | None = None,
    exposure: RiskExposure | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.RISK_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: RiskService = Depends(get_risk_service),
) -> Page[RiskRead]:
    """Phase 47 — the org-wide Risk register: every Risk across every
    Project in the caller's active organization, optionally narrowed by
    project/status/exposure. Organization-scoped via get_current_membership
    exactly like every other org-wide route (audit, users) — a `project_id`
    filter naming a project in another organization simply matches no rows
    (every Risk's own organization_id is independently checked, Phase 12),
    it never 403s or otherwise confirms that project's existence. Reuses
    Permission.RISK_READ unchanged — already granted to every role,
    identical to the existing per-project GET /projects/{id}/risks route."""
    items, total = service.list_for_organization(
        membership.organization_id,
        project_id=project_id,
        status=status,
        exposure=exposure,
        limit=limit,
        offset=offset,
    )
    return Page[RiskRead](items=[risk_to_read(risk) for risk in items], total=total)
