import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserStatus
from app.models.user import User


class UserCreate(BaseModel):
    """Admin-only user creation (app/api/v1/users.py) — Phase 10 has no
    open self-registration (CLAUDE.md §25/§27: no fake/uninvited accounts).
    person_id links this account to an existing Person; a user can also be
    created with no link and linked later via UserUpdate.

    role was removed in Phase 12 — creating an account no longer implies
    any role anywhere. A fresh User has no role until someone gives them
    an OrganizationMembership (POST /organizations/{id}/memberships), the
    same way a fresh Person has no team until added to one. See
    docs/adr/0012-organizations-multi-tenancy.md.
    """

    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=200)
    person_id: uuid.UUID | None = None


class UserUpdate(BaseModel):
    """Deliberately excludes password (see ChangePasswordRequest) and, as
    of Phase 12, role entirely — role changes go through
    PATCH /organizations/{org_id}/memberships/{user_id}/role."""

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    status: UserStatus | None = None
    person_id: uuid.UUID | None = None


class UserRead(BaseModel):
    """password_hash is never included here or anywhere else this app
    serializes a User — see docs/adr/0010-authentication-rbac-audit.md.

    role/permissions/accessible_team_ids/accessible_project_ids were
    removed in Phase 12 — none of them are meaningful for a User outside
    an organization context anymore (see MeRead in app/schemas/auth.py for
    the authenticated caller's own organization-scoped view of those).
    This UserRead now describes exactly what a User IS: an account, with
    no role attached, since GET /users deliberately stays a
    cross-organization account directory (Decision 8 — see
    docs/adr/0012-organizations-multi-tenancy.md)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    status: UserStatus
    person_id: uuid.UUID | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


def user_to_read(user: User) -> UserRead:
    return UserRead.model_validate(user)
