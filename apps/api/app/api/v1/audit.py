import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_audit_service, require_permission
from app.domain.authorization import Permission
from app.models.user import User
from app.schemas.audit import AuditEventRead
from app.schemas.common import Page
from app.services.audit import AuditService

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


@router.get("", response_model=Page[AuditEventRead])
def list_audit_events(
    actor_user_id: uuid.UUID | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.AUDIT_READ)),
    service: AuditService = Depends(get_audit_service),
) -> Page[AuditEventRead]:
    items, total = service.list(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
    )
    return Page[AuditEventRead](
        items=[AuditEventRead.model_validate(item) for item in items], total=total
    )
