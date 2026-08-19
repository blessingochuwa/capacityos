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
    in TypeScript, which would drift.

    accessible_team_ids/accessible_project_ids (Phase 11) are this user's
    OWN explicit TeamAccessGrant/ProjectAccessGrant instance ids — default
    empty so every existing call site that doesn't pass them (e.g.
    app/api/v1/users.py's admin list/create/update, which serialize OTHER
    users and have no reason to resolve another user's grants) is
    unaffected. Only meaningful for Manager: Owner/Admin bypass resource
    scoping entirely (role-based, not grant-based — the frontend should
    treat those roles as always-authorized regardless of list contents),
    and Member/Viewer hold no team.write/project.write permission to begin
    with, so an empty list for them isn't a restriction, just accurate."""

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
    accessible_team_ids: list[uuid.UUID] = []
    accessible_project_ids: list[uuid.UUID] = []


def user_to_read(
    user: User,
    *,
    accessible_team_ids: list[uuid.UUID] | None = None,
    accessible_project_ids: list[uuid.UUID] | None = None,
) -> UserRead:
    return UserRead.model_validate(user).model_copy(
        update={
            "permissions": sorted(p.value for p in ROLE_PERMISSIONS[user.role]),
            "accessible_team_ids": accessible_team_ids or [],
            "accessible_project_ids": accessible_project_ids or [],
        }
    )
