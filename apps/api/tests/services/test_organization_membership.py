"""OrganizationMembershipService (Phase 12, hardened Phase 15) — the
per-organization last-Owner invariant across change_role/revoke. Phase 15
replaced the old read-then-check-then-write shape with an atomic guarded
UPDATE (see app/repositories/organization_membership.py's change_role_if_safe/
revoke_if_safe); this file exercises the resulting behavior at the service
layer, including the multi-organization isolation and disabled-account
semantics ADR 0015 documents. See tests/api/test_last_owner_concurrency.py
for the concurrency-specific coverage (real file-backed SQLite, genuinely
concurrent threads) that a single in-memory session can't exercise."""

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import DomainValidationError, ForbiddenError, NotFoundError
from app.models.enums import MembershipStatus, UserRole, UserStatus
from app.models.organization import Organization
from app.repositories.organization_membership import OrganizationMembershipRepository
from app.repositories.user import UserRepository
from app.services.organization_membership import OrganizationMembershipService
from tests.factories import make_organization, make_organization_membership, make_user


def _service(session: Session) -> OrganizationMembershipService:
    return OrganizationMembershipService(
        OrganizationMembershipRepository(session), UserRepository(session)
    )


# ---------------------------------------------------------------------------
# change_role — last-owner invariant
# ---------------------------------------------------------------------------


def test_can_demote_an_owner_when_another_owner_exists(
    db_session: Session, organization: Organization
) -> None:
    owner1 = make_user(db_session, email="owner1@example.com")
    owner1_membership = make_organization_membership(
        db_session, user=owner1, organization=organization, role=UserRole.OWNER
    )
    owner2 = make_user(db_session, email="owner2@example.com")
    make_organization_membership(
        db_session, user=owner2, organization=organization, role=UserRole.OWNER
    )

    service = _service(db_session)
    updated = service.change_role(
        organization.id, owner1.id, UserRole.ADMIN, acting_membership=owner1_membership
    )
    assert updated.role == UserRole.ADMIN


def test_cannot_demote_the_last_remaining_owner(
    db_session: Session, organization: Organization
) -> None:
    owner = make_user(db_session, email="sole-owner@example.com")
    owner_membership = make_organization_membership(
        db_session, user=owner, organization=organization, role=UserRole.OWNER
    )

    service = _service(db_session)
    with pytest.raises(DomainValidationError):
        service.change_role(
            organization.id, owner.id, UserRole.ADMIN, acting_membership=owner_membership
        )
    # The invariant blocked the write — the row must be unchanged.
    assert (
        OrganizationMembershipRepository(db_session)
        .get_by_user_and_org(owner.id, organization.id)
        .role  # type: ignore[union-attr]
        == UserRole.OWNER
    )


def test_three_owners_demoting_two_sequentially_succeeds_then_third_blocked(
    db_session: Session, organization: Organization
) -> None:
    owners = [
        make_user(db_session, email=f"owner{i}@example.com") for i in range(3)
    ]
    memberships = [
        make_organization_membership(
            db_session, user=owner, organization=organization, role=UserRole.OWNER
        )
        for owner in owners
    ]

    service = _service(db_session)
    service.change_role(
        organization.id, owners[0].id, UserRole.ADMIN, acting_membership=memberships[0]
    )
    service.change_role(
        organization.id, owners[1].id, UserRole.ADMIN, acting_membership=memberships[1]
    )
    with pytest.raises(DomainValidationError):
        service.change_role(
            organization.id, owners[2].id, UserRole.ADMIN, acting_membership=memberships[2]
        )


def test_non_owner_admin_cannot_grant_or_change_owner_admin_roles(
    db_session: Session, organization: Organization
) -> None:
    owner = make_user(db_session, email="owner@example.com")
    make_organization_membership(
        db_session, user=owner, organization=organization, role=UserRole.OWNER
    )
    admin = make_user(db_session, email="admin@example.com")
    admin_membership = make_organization_membership(
        db_session, user=admin, organization=organization, role=UserRole.ADMIN
    )
    member = make_user(db_session, email="member@example.com")
    make_organization_membership(
        db_session, user=member, organization=organization, role=UserRole.MEMBER
    )

    service = _service(db_session)
    with pytest.raises(ForbiddenError):
        service.change_role(
            organization.id, member.id, UserRole.ADMIN, acting_membership=admin_membership
        )


def test_change_role_for_unknown_membership_raises_not_found(
    db_session: Session, organization: Organization
) -> None:
    owner = make_user(db_session, email="owner@example.com")
    owner_membership = make_organization_membership(
        db_session, user=owner, organization=organization, role=UserRole.OWNER
    )
    stranger = make_user(db_session, email="stranger@example.com")

    service = _service(db_session)
    with pytest.raises(NotFoundError):
        service.change_role(
            organization.id, stranger.id, UserRole.MEMBER, acting_membership=owner_membership
        )


# ---------------------------------------------------------------------------
# revoke — last-owner invariant
# ---------------------------------------------------------------------------


def test_can_revoke_one_of_multiple_owners(
    db_session: Session, organization: Organization
) -> None:
    owner1 = make_user(db_session, email="owner1@example.com")
    make_organization_membership(
        db_session, user=owner1, organization=organization, role=UserRole.OWNER
    )
    owner2 = make_user(db_session, email="owner2@example.com")
    make_organization_membership(
        db_session, user=owner2, organization=organization, role=UserRole.OWNER
    )

    service = _service(db_session)
    updated = service.revoke(organization.id, owner1.id)
    assert updated.status == MembershipStatus.REVOKED


def test_cannot_revoke_the_last_remaining_owner(
    db_session: Session, organization: Organization
) -> None:
    owner = make_user(db_session, email="sole-owner@example.com")
    make_organization_membership(
        db_session, user=owner, organization=organization, role=UserRole.OWNER
    )

    service = _service(db_session)
    with pytest.raises(DomainValidationError):
        service.revoke(organization.id, owner.id)
    membership = OrganizationMembershipRepository(db_session).get_by_user_and_org(
        owner.id, organization.id
    )
    assert membership is not None
    assert membership.status == MembershipStatus.ACTIVE


def test_revoking_a_non_owner_membership_always_succeeds(
    db_session: Session, organization: Organization
) -> None:
    owner = make_user(db_session, email="owner@example.com")
    make_organization_membership(
        db_session, user=owner, organization=organization, role=UserRole.OWNER
    )
    member = make_user(db_session, email="member@example.com")
    make_organization_membership(
        db_session, user=member, organization=organization, role=UserRole.MEMBER
    )

    service = _service(db_session)
    updated = service.revoke(organization.id, member.id)
    assert updated.status == MembershipStatus.REVOKED


# ---------------------------------------------------------------------------
# Multi-organization isolation
# ---------------------------------------------------------------------------


def test_demoting_the_sole_owner_of_one_organization_does_not_touch_another(
    db_session: Session,
) -> None:
    org_a = make_organization(db_session, name="Org A")
    org_b = make_organization(db_session, name="Org B")
    owner_a = make_user(db_session, email="owner-a@example.com")
    make_organization_membership(db_session, user=owner_a, organization=org_a, role=UserRole.OWNER)
    owner_b = make_user(db_session, email="owner-b@example.com")
    owner_b_membership = make_organization_membership(
        db_session, user=owner_b, organization=org_b, role=UserRole.OWNER
    )

    service = _service(db_session)
    # Org B has its own sole Owner — demoting them must be blocked
    # independently of Org A's state, never by inspecting Org A at all.
    with pytest.raises(DomainValidationError):
        service.change_role(
            org_b.id, owner_b.id, UserRole.ADMIN, acting_membership=owner_b_membership
        )
    # Org A's sole Owner remains completely untouched.
    membership_a = OrganizationMembershipRepository(db_session).get_by_user_and_org(
        owner_a.id, org_a.id
    )
    assert membership_a is not None
    assert membership_a.role == UserRole.OWNER


def test_a_user_can_be_owner_of_one_org_and_member_of_another(
    db_session: Session,
) -> None:
    org_a = make_organization(db_session, name="Org A")
    org_b = make_organization(db_session, name="Org B")
    user = make_user(db_session, email="multi-org@example.com")
    make_organization_membership(db_session, user=user, organization=org_a, role=UserRole.OWNER)
    make_organization_membership(db_session, user=user, organization=org_b, role=UserRole.MEMBER)

    service = _service(db_session)
    # Changing this user's MEMBER role in Org B never even evaluates Org A's
    # ownership — a plain non-Owner role change is unrestricted.
    updated = service.revoke(org_b.id, user.id)
    assert updated.status == MembershipStatus.REVOKED
    membership_a = OrganizationMembershipRepository(db_session).get_by_user_and_org(
        user.id, org_a.id
    )
    assert membership_a is not None
    assert membership_a.role == UserRole.OWNER
    assert membership_a.status == MembershipStatus.ACTIVE


# ---------------------------------------------------------------------------
# Disabled-account semantics (ADR 0015)
# ---------------------------------------------------------------------------


def test_a_disabled_owners_membership_does_not_count_toward_the_invariant(
    db_session: Session, organization: Organization
) -> None:
    """Owner1's account is already disabled (User.status=disabled) while
    their OrganizationMembership row is still role=Owner/status=active.
    AuthService.resolve_session/login already refuse to authenticate a
    disabled account, so Owner1 cannot actually exercise Owner authority —
    demoting the org's only OTHER, working Owner must therefore be blocked
    exactly as if Owner1's membership didn't exist. See
    docs/adr/0015-last-owner-invariant.md."""
    disabled_owner = make_user(
        db_session, email="disabled-owner@example.com", status=UserStatus.DISABLED
    )
    make_organization_membership(
        db_session, user=disabled_owner, organization=organization, role=UserRole.OWNER
    )
    working_owner = make_user(db_session, email="working-owner@example.com")
    working_owner_membership = make_organization_membership(
        db_session, user=working_owner, organization=organization, role=UserRole.OWNER
    )

    service = _service(db_session)
    with pytest.raises(DomainValidationError):
        service.change_role(
            organization.id,
            working_owner.id,
            UserRole.ADMIN,
            acting_membership=working_owner_membership,
        )


def test_count_active_owners_excludes_disabled_accounts(
    db_session: Session, organization: Organization
) -> None:
    disabled_owner = make_user(
        db_session, email="disabled-owner@example.com", status=UserStatus.DISABLED
    )
    make_organization_membership(
        db_session, user=disabled_owner, organization=organization, role=UserRole.OWNER
    )
    working_owner = make_user(db_session, email="working-owner@example.com")
    make_organization_membership(
        db_session, user=working_owner, organization=organization, role=UserRole.OWNER
    )

    repository = OrganizationMembershipRepository(db_session)
    assert repository.count_active_owners(organization.id) == 1
