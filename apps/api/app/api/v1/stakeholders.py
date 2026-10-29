import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, require_permission
from app.core.database import get_db
from app.domain.authorization import Permission
from app.models.enums import (
    StakeholderDecisionAuthority,
    StakeholderInfluence,
    StakeholderInterest,
)
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.stakeholder import StakeholderRepository
from app.schemas.common import Page
from app.schemas.stakeholder import StakeholderRead
from app.services.stakeholder import StakeholderService

router = APIRouter(prefix="/api/v1/stakeholders", tags=["stakeholders"])


def get_stakeholder_service(db: Session = Depends(get_db)) -> StakeholderService:
    return StakeholderService(
        StakeholderRepository(db), ProjectRepository(db), PersonRepository(db)
    )


@router.get("", response_model=Page[StakeholderRead])
def list_organization_stakeholders(
    project_id: uuid.UUID | None = None,
    influence: StakeholderInfluence | None = None,
    interest: StakeholderInterest | None = None,
    decision_authority: StakeholderDecisionAuthority | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.STAKEHOLDER_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: StakeholderService = Depends(get_stakeholder_service),
) -> Page[StakeholderRead]:
    """Phase 48 — the org-wide Stakeholder register: every Stakeholder
    across every Project in the caller's active organization, optionally
    narrowed by project/influence/interest/decision authority. Mirrors
    GET /api/v1/risks (Phase 47) exactly: organization-scoped via
    get_current_membership, never a client-supplied organization id; a
    `project_id` naming a project in another organization simply matches
    no rows (every Stakeholder's own organization_id is independently
    checked, Phase 12) — never a 403/404 that would confirm it exists.
    Reuses Permission.STAKEHOLDER_READ unchanged — already granted to
    every role, identical to GET /projects/{id}/stakeholders."""
    items, total = service.list_for_organization(
        membership.organization_id,
        project_id=project_id,
        influence=influence,
        interest=interest,
        decision_authority=decision_authority,
        limit=limit,
        offset=offset,
    )
    return Page[StakeholderRead](
        items=[StakeholderRead.model_validate(stakeholder) for stakeholder in items],
        total=total,
    )
