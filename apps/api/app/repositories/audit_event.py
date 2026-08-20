import uuid
from datetime import datetime

from sqlalchemy import func, select

from app.models.audit_event import AuditEvent
from app.repositories.base import BaseRepository


class AuditEventRepository(BaseRepository[AuditEvent]):
    model = AuditEvent

    def list_filtered(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AuditEvent], int]:
        stmt = select(AuditEvent).where(AuditEvent.organization_id == organization_id)
        if actor_user_id is not None:
            stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
        if action is not None:
            stmt = stmt.where(AuditEvent.action == action)
        if resource_type is not None:
            stmt = stmt.where(AuditEvent.resource_type == resource_type)
        if start is not None:
            stmt = stmt.where(AuditEvent.timestamp >= start)
        if end is not None:
            stmt = stmt.where(AuditEvent.timestamp <= end)

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.session.scalars(
                stmt.order_by(AuditEvent.timestamp.desc()).limit(limit).offset(offset)
            )
        )
        return items, total
