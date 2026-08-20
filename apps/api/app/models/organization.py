from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """The tenant boundary (Phase 12) — every organization-owned row
    (Person, Team, Project, Allocation, Skill, Scenario, and everything
    that hangs off them) belongs to exactly one Organization via a direct
    organization_id foreign key. See
    docs/adr/0012-organizations-multi-tenancy.md.

    is_active is soft-delete only — an Organization is deactivated, never
    hard-deleted (same convention as Skill.is_active). No billing/
    subscription/plan concept exists here or anywhere in this phase.

    slug is a stable, URL-safe identifier separate from the display name
    (name may change; slug is treated as immutable once set, mirroring how
    external_id is treated as an identity key elsewhere in this codebase).
    """

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
