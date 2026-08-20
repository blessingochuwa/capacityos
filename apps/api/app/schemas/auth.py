import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.authorization import ROLE_PERMISSIONS
from app.models.enums import UserRole, UserStatus
from app.models.organization import Organization
from app.models.organization_membership import OrganizationMembership
from app.models.user import User


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class SwitchOrganizationRequest(BaseModel):
    organization_id: uuid.UUID


class OrganizationSummary(BaseModel):
    """The minimal shape MeRead needs for the frontend's organization
    switcher — id/name/slug, nothing else (not a full OrganizationRead;
    an org's is_active/timestamps are an admin concern, not an
    identity-response concern)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str


class MeRead(BaseModel):
    """The authenticated caller's identity PLUS their organization
    context, for /auth/login, /auth/me, and /auth/switch-organization
    (Phase 12) — replaces the old UserRead-with-role response those three
    routes used through Phase 10/11.

    role/permissions/accessible_team_ids/accessible_project_ids are now
    always relative to active_organization, never global — role is None
    (and permissions/accessible_*_ids are empty) whenever
    active_organization is None, which happens right after login for an
    account with zero or multiple memberships, before an explicit
    POST /auth/switch-organization. The frontend's RequireAuth gate reacts
    to that None directly (see docs/adr/0012-organizations-multi-tenancy.md)
    rather than the backend guessing which organization was meant.

    organizations is every ACTIVE membership's organization, for the
    switcher UI — deliberately not the caller's full account history,
    since a revoked membership's organization shouldn't be selectable.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    status: UserStatus
    person_id: uuid.UUID | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    active_organization: OrganizationSummary | None
    role: UserRole | None
    permissions: list[str] = []
    accessible_team_ids: list[uuid.UUID] = []
    accessible_project_ids: list[uuid.UUID] = []
    organizations: list[OrganizationSummary] = []


def me_to_read(
    user: User,
    *,
    active_organization: Organization | None,
    active_membership: OrganizationMembership | None,
    organizations: list[Organization],
    accessible_team_ids: list[uuid.UUID] | None = None,
    accessible_project_ids: list[uuid.UUID] | None = None,
) -> MeRead:
    return MeRead(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        person_id=user.person_id,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
        active_organization=(
            OrganizationSummary.model_validate(active_organization)
            if active_organization is not None
            else None
        ),
        role=active_membership.role if active_membership is not None else None,
        permissions=(
            sorted(p.value for p in ROLE_PERMISSIONS[active_membership.role])
            if active_membership is not None
            else []
        ),
        accessible_team_ids=accessible_team_ids or [],
        accessible_project_ids=accessible_project_ids or [],
        organizations=[OrganizationSummary.model_validate(org) for org in organizations],
    )
