import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_audit_service,
    get_current_membership,
    get_current_user,
    require_csrf,
)
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.logging import request_id_var
from app.domain.authorization import Permission, has_permission
from app.models.enums import AuditAction, AuditOutcome, MembershipStatus, UserRole
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.organization import OrganizationRepository
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.repositories.user import UserRepository
from app.schemas.common import Page
from app.schemas.organization import OrganizationCreate, OrganizationRead, OrganizationUpdate
from app.schemas.organization_membership import (
    MembershipCreate,
    MembershipRead,
    MembershipRoleChange,
    membership_to_read,
)
from app.services.audit import AuditService
from app.services.organization import OrganizationService
from app.services.organization_membership import OrganizationMembershipService

router = APIRouter(prefix="/api/v1/organizations", tags=["organizations"])


def get_organization_service(db: Session = Depends(get_db)) -> OrganizationService:
    return OrganizationService(OrganizationRepository(db), OrganizationMembershipRepository(db))


def get_organization_membership_service(
    db: Session = Depends(get_db),
) -> OrganizationMembershipService:
    return OrganizationMembershipService(OrganizationMembershipRepository(db), UserRepository(db))


def _require_active_organization(
    organization_id: uuid.UUID, membership: OrganizationMembership
) -> None:
    """Every route below acts on a path organization_id, but the only
    authorization boundary this app trusts is the CALLER's own active
    organization (Phase 12 — see get_current_membership's docstring). A
    path id that doesn't match must 404, not 403 — it must look exactly
    like a nonexistent organization to a caller probing other ids."""
    if organization_id != membership.organization_id:
        raise NotFoundError("Organization", organization_id)


def _require_manage(membership: OrganizationMembership, permission: Permission) -> None:
    if not has_permission(membership.role, permission):
        raise ForbiddenError(
            f"You do not have permission to perform this action ({permission.value})."
        )


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------


@router.post(
    "", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_organization(
    data: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> OrganizationRead:
    """Any authenticated user may create an organization — no permission
    check, since there is no existing organization context to check a
    permission within yet (see Permission.ORGANIZATION_MANAGE's
    docstring). The creator becomes its Owner."""
    organization = service.create(data, creator=current_user)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ORGANIZATION_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="organization",
        resource_id=str(organization.id),
        request_id=request_id_var.get(),
        organization_id=organization.id,
    )
    return OrganizationRead.model_validate(organization)


@router.get("/mine", response_model=list[OrganizationRead])
def list_my_organizations(
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
) -> list[OrganizationRead]:
    """No active-organization context required — this is how a caller with
    zero or many memberships discovers what to switch into."""
    organizations = service.list_mine(current_user.id)
    return [OrganizationRead.model_validate(org) for org in organizations]


@router.get("/{organization_id}", response_model=OrganizationRead)
def get_organization(
    organization_id: uuid.UUID,
    membership: OrganizationMembership = Depends(get_current_membership),
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationRead:
    _require_active_organization(organization_id, membership)
    _require_manage(membership, Permission.ORGANIZATION_MANAGE)
    return OrganizationRead.model_validate(service.get(organization_id))


@router.patch(
    "/{organization_id}", response_model=OrganizationRead, dependencies=[Depends(require_csrf)]
)
def update_organization(
    organization_id: uuid.UUID,
    data: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: OrganizationService = Depends(get_organization_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> OrganizationRead:
    _require_active_organization(organization_id, membership)
    _require_manage(membership, Permission.ORGANIZATION_MANAGE)
    organization = service.update(organization_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ORGANIZATION_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="organization",
        resource_id=str(organization_id),
        request_id=request_id_var.get(),
        organization_id=organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return OrganizationRead.model_validate(organization)


@router.post(
    "/{organization_id}/deactivate",
    response_model=OrganizationRead,
    dependencies=[Depends(require_csrf)],
)
def deactivate_organization(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: OrganizationService = Depends(get_organization_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> OrganizationRead:
    _require_active_organization(organization_id, membership)
    _require_manage(membership, Permission.ORGANIZATION_MANAGE)
    # Phase 31: OrganizationService.deactivate now enforces the
    # >= 2-active-Owners safety guard (DomainValidationError -> 422) so a
    # sole Owner cannot deactivate the organization into a state only a
    # direct database edit could recover. See
    # docs/adr/0031-organization-deactivation-safety.md.
    organization = service.deactivate(organization_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ORGANIZATION_DEACTIVATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="organization",
        resource_id=str(organization_id),
        request_id=request_id_var.get(),
        organization_id=organization_id,
    )
    return OrganizationRead.model_validate(organization)


@router.post(
    "/{organization_id}/reactivate",
    response_model=OrganizationRead,
    dependencies=[Depends(require_csrf)],
)
def reactivate_organization(
    organization_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: OrganizationService = Depends(get_organization_service),
    db: Session = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
) -> OrganizationRead:
    """Restore a soft-deactivated organization to `is_active=True`
    (Phase 31 — the recovery half of the deactivation lifecycle).

    Deliberately does NOT depend on `get_current_membership` /
    `_require_active_organization`: the target organization is inactive,
    so the caller has no *active*-organization context for it. Instead —
    exactly like `AuthService.switch_organization` — authorization is
    resolved directly against the caller's own membership in the target
    organization: only an **active Owner membership** may reactivate.

    A caller who isn't a member at all gets 404 (indistinguishable from a
    nonexistent organization — never confirm an org they can't see
    exists, Phase 12). A member who isn't an Owner gets 403. Reactivating
    an already-active organization is an idempotent no-op (200).
    """
    membership = OrganizationMembershipRepository(db).get_by_user_and_org(
        current_user.id, organization_id
    )
    if membership is None or membership.status != MembershipStatus.ACTIVE:
        raise NotFoundError("Organization", organization_id)
    if membership.role != UserRole.OWNER:
        raise ForbiddenError("Only an Owner can reactivate an organization.")

    organization = service.reactivate(organization_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.ORGANIZATION_REACTIVATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="organization",
        resource_id=str(organization_id),
        request_id=request_id_var.get(),
        organization_id=organization_id,
    )
    return OrganizationRead.model_validate(organization)


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------


@router.post(
    "/{organization_id}/memberships",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def add_membership(
    organization_id: uuid.UUID,
    data: MembershipCreate,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: OrganizationMembershipService = Depends(get_organization_membership_service),
    db: Session = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
) -> MembershipRead:
    _require_active_organization(organization_id, membership)
    _require_manage(membership, Permission.MEMBERSHIP_MANAGE)
    new_membership = service.add_member(organization_id, data)
    target_user = UserRepository(db).get(new_membership.user_id)
    assert target_user is not None  # noqa: S101 — just created against this exact user_id
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.MEMBERSHIP_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="organization_membership",
        resource_id=str(new_membership.id),
        request_id=request_id_var.get(),
        organization_id=organization_id,
        metadata={"user_id": str(new_membership.user_id), "role": new_membership.role.value},
    )
    return membership_to_read(new_membership, target_user)


@router.get("/{organization_id}/memberships", response_model=Page[MembershipRead])
def list_memberships(
    organization_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: OrganizationMembershipService = Depends(get_organization_membership_service),
    db: Session = Depends(get_db),
) -> Page[MembershipRead]:
    _require_active_organization(organization_id, membership)
    _require_manage(membership, Permission.MEMBERSHIP_MANAGE)
    items, total = service.list_for_org(organization_id, limit=limit, offset=offset)
    users_by_id = {
        user.id: user for user in UserRepository(db).list_by_ids([m.user_id for m in items])
    }
    return Page[MembershipRead](
        items=[membership_to_read(item, users_by_id[item.user_id]) for item in items],
        total=total,
    )


@router.patch(
    "/{organization_id}/memberships/{user_id}/role",
    response_model=MembershipRead,
    dependencies=[Depends(require_csrf)],
)
def change_membership_role(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    data: MembershipRoleChange,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: OrganizationMembershipService = Depends(get_organization_membership_service),
    db: Session = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
) -> MembershipRead:
    _require_active_organization(organization_id, membership)
    _require_manage(membership, Permission.MEMBERSHIP_MANAGE)
    existing = OrganizationMembershipRepository(db).get_by_user_and_org(user_id, organization_id)
    old_role = existing.role.value if existing is not None else None
    updated = service.change_role(
        organization_id, user_id, data.role, acting_membership=membership
    )
    target_user = UserRepository(db).get(user_id)
    assert target_user is not None  # noqa: S101 — resolved via this exact user_id above
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.MEMBERSHIP_ROLE_CHANGE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="organization_membership",
        resource_id=str(updated.id),
        request_id=request_id_var.get(),
        organization_id=organization_id,
        metadata={"user_id": str(user_id), "role_from": old_role, "role_to": updated.role.value},
    )
    return membership_to_read(updated, target_user)


@router.delete(
    "/{organization_id}/memberships/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def revoke_membership(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: OrganizationMembershipService = Depends(get_organization_membership_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    _require_active_organization(organization_id, membership)
    _require_manage(membership, Permission.MEMBERSHIP_MANAGE)
    service.revoke(organization_id, user_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.MEMBERSHIP_REVOKE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="organization_membership",
        resource_id=str(user_id),
        request_id=request_id_var.get(),
        organization_id=organization_id,
    )


@router.post(
    "/{organization_id}/memberships/{user_id}/reactivate",
    response_model=MembershipRead,
    dependencies=[Depends(require_csrf)],
)
def reactivate_membership(
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: OrganizationMembershipService = Depends(get_organization_membership_service),
    db: Session = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
) -> MembershipRead:
    _require_active_organization(organization_id, membership)
    _require_manage(membership, Permission.MEMBERSHIP_MANAGE)
    updated = service.reactivate(organization_id, user_id)
    target_user = UserRepository(db).get(user_id)
    assert target_user is not None  # noqa: S101 — resolved via this exact user_id above
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.MEMBERSHIP_REACTIVATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="organization_membership",
        resource_id=str(updated.id),
        request_id=request_id_var.get(),
        organization_id=organization_id,
    )
    return membership_to_read(updated, target_user)
