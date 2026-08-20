from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserStatus

if TYPE_CHECKING:
    from app.models.person import Person


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """An authenticated system actor (Phase 10).

    Deliberately separate from Person, not a subtype or a merge of it — see
    docs/adr/0010-authentication-rbac-audit.md. Person answers "who is being
    planned"; User answers "who is logged in." person_id is a nullable,
    optional link: a User can exist before being linked to a Person, a
    Person can exist with no login account at all (e.g. a contractor tracked
    for capacity only), and a future service/integration identity can be a
    User with no Person, none of which fit if these were the same table.

    email is the LOGIN identity — independent of Person.email even though
    they will usually match for a staffed user linking to their own Person
    row. It remains GLOBALLY unique even after Phase 12 (unlike Person.email,
    which becomes organization-scoped): a user should not need a second
    account to belong to a second organization. failed_login_count/
    locked_until implement the account-lockout brute-force mitigation (see
    the ADR's threat model); both are reset to 0/None on a successful login.

    role does NOT live here (moved to OrganizationMembership in Phase 12 —
    see docs/adr/0012-organizations-multi-tenancy.md): one User can be
    Owner in one Organization and Viewer in another, which a single scalar
    column on this table cannot express. User carries only account-level
    state — identity, credentials, lockout, account status — never
    anything role/permission-shaped.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="ck_users_status",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("people.id", ondelete="SET NULL"), unique=True, index=True
    )
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    person: Mapped[Person | None] = relationship()
