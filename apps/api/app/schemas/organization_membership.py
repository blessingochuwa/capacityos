import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.enums import MembershipStatus, UserRole
from app.models.organization_membership import OrganizationMembership
from app.models.user import User


class MembershipCreate(BaseModel):
    """Adds an EXISTING user (found by email — Phase 10's get_by_email
    precedent) as a member of the acting organization. No invitation/email
    delivery and no side-effect account creation (CLAUDE.md §26: no fake
    functionality) — if no account exists for this email, the request
    fails with NotFoundError, same as referencing any other nonexistent
    resource."""

    email: EmailStr
    role: UserRole = UserRole.VIEWER


class MembershipRoleChange(BaseModel):
    role: UserRole


class MembershipRead(BaseModel):
    """Composed from both the OrganizationMembership row and its User (see
    membership_to_read below) — a membership on its own is just ids/role/
    status, but the organization admin UI needs the member's email/
    display_name to be useful, exactly as UserRead needed permissions
    computed rather than stored."""

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    email: EmailStr
    display_name: str
    role: UserRole
    status: MembershipStatus
    created_at: datetime
    updated_at: datetime


def membership_to_read(membership: OrganizationMembership, user: User) -> MembershipRead:
    return MembershipRead(
        id=membership.id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        email=user.email,
        display_name=user.display_name,
        role=membership.role,
        status=membership.status,
        created_at=membership.created_at,
        updated_at=membership.updated_at,
    )
