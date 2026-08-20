from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MembershipStatus, UserRole


class OrganizationMembership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A User's role within one Organization (Phase 12).

    role lived directly on User through Phase 10/11; it moves here because
    one User can legitimately be Owner in one Organization and Viewer in
    another — a single scalar column on User cannot express that. Reuses
    the existing UserRole vocabulary verbatim (Owner/Admin/Manager/Member/
    Viewer) — no second role system. User.email remains the globally
    unique LOGIN identity; membership (not a second account) is how one
    person participates in more than one organization. See
    docs/adr/0012-organizations-multi-tenancy.md.

    status is independent of User.status: User.status governs whether the
    account can log in at all; status here governs whether THIS
    organization currently recognizes the user as a member — a membership
    can be revoked without disabling the account (the user may still
    belong to other organizations).

    Only created_at is meaningfully "added," but updated_at is kept (unlike
    TeamMembership) because role/status both change in place over a
    membership's life, unlike a team membership which is only added or
    removed.
    """

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "organization_id", name="uq_organization_membership_user_org"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="ck_organization_memberships_role",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=UserRole.VIEWER,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(
            MembershipStatus,
            name="ck_organization_memberships_status",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=MembershipStatus.ACTIVE,
    )
