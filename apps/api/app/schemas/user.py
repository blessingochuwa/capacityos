import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.authorization import ROLE_PERMISSIONS
from app.models.enums import UserRole, UserStatus
from app.models.user import User


class UserCreate(BaseModel):
    """Admin-only user creation (app/api/v1/users.py) — Phase 10 has no
    open self-registration (CLAUDE.md §25/§27: no fake/uninvited accounts).
    person_id links this account to an existing Person; a user can also be
    created with no link and linked later via UserUpdate."""

    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=200)
    role: UserRole = UserRole.VIEWER
    person_id: uuid.UUID | None = None


class UserUpdate(BaseModel):
    """Deliberately excludes role (see UserRoleChange — a role change has
    its own audit action and Owner-invariant checks) and password (see
    ChangePasswordRequest)."""

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    status: UserStatus | None = None
    person_id: uuid.UUID | None = None


class UserRoleChange(BaseModel):
    role: UserRole


class UserRead(BaseModel):
    """password_hash is never included here or anywhere else this app
    serializes a User — see docs/adr/0010-authentication-rbac-audit.md.

    permissions is always this USER's own current grants (from
    app.domain.authorization.ROLE_PERMISSIONS), populated by
    user_to_read() below — never client-supplied, never stored. The
    backend remains the authorization boundary regardless (every route
    re-checks require_permission independently); this field exists purely
    so the frontend can gate UI affordances from one authoritative source
    instead of hand-maintaining a second copy of the role/permission table
    in TypeScript, which would drift."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    status: UserStatus
    role: UserRole
    person_id: uuid.UUID | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    permissions: list[str] = []


def user_to_read(user: User) -> UserRead:
    return UserRead.model_validate(user).model_copy(
        update={"permissions": sorted(p.value for p in ROLE_PERMISSIONS[user.role])}
    )
