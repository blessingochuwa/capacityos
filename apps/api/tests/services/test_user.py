"""UserService (Phase 10, revised Phase 12, hardened Phase 15). Phase 15
closes ADR 0012's other known last-owner gap: disabling a User account that
holds the sole active Owner membership of one or more organizations. See
docs/adr/0015-last-owner-invariant.md. Concurrency-specific coverage against
a real file-backed database lives in
tests/api/test_last_owner_concurrency.py."""

import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import DomainValidationError
from app.models.enums import UserRole, UserStatus
from app.models.organization import Organization
from app.models.user import User
from app.repositories.person import PersonRepository
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate
from app.services.user import UserService
from tests.factories import make_organization, make_organization_membership, make_user


def _service(session: Session) -> UserService:
    return UserService(UserRepository(session), PersonRepository(session))


def _owner(session: Session, organization: Organization, *, email: str) -> User:
    user = make_user(session, email=email)
    make_organization_membership(session, user=user, organization=organization, role=UserRole.OWNER)
    return user


def _member(session: Session, organization: Organization, *, email: str) -> User:
    user = make_user(session, email=email)
    make_organization_membership(
        session, user=user, organization=organization, role=UserRole.MEMBER
    )
    return user


def _disabled_owner(session: Session, organization: Organization, *, email: str) -> User:
    user = make_user(session, email=email, status=UserStatus.DISABLED)
    make_organization_membership(
        session, user=user, organization=organization, role=UserRole.OWNER
    )
    return user


def test_disabling_a_non_owner_succeeds(db_session: Session, organization: Organization) -> None:
    _owner(db_session, organization, email="owner@example.com")
    member = _member(db_session, organization, email="member@example.com")

    updated = _service(db_session).update(
        organization.id, member.id, UserUpdate(status=UserStatus.DISABLED)
    )
    assert updated.status == UserStatus.DISABLED


def test_disabling_an_owner_with_another_working_owner_present_succeeds(
    db_session: Session, organization: Organization
) -> None:
    owner1 = _owner(db_session, organization, email="owner1@example.com")
    _owner(db_session, organization, email="owner2@example.com")

    updated = _service(db_session).update(
        organization.id, owner1.id, UserUpdate(status=UserStatus.DISABLED)
    )
    assert updated.status == UserStatus.DISABLED


def test_disabling_the_final_owner_is_rejected(
    db_session: Session, organization: Organization
) -> None:
    owner = _owner(db_session, organization, email="sole-owner@example.com")

    with pytest.raises(DomainValidationError):
        _service(db_session).update(
            organization.id, owner.id, UserUpdate(status=UserStatus.DISABLED)
        )

    refreshed = UserRepository(db_session).get(owner.id)
    assert refreshed is not None
    assert refreshed.status == UserStatus.ACTIVE


def test_disabling_a_user_who_owns_multiple_organizations_checks_every_one(
    db_session: Session,
) -> None:
    """User A: sole Owner of Org A, sole Owner of Org B, Member of Org C.
    Disabling User A must be rejected — it would leave BOTH Org A and Org B
    ownerless — and must leave every organization's membership state
    completely unchanged (not partially applied)."""
    org_a = make_organization(db_session, name="Org A")
    org_b = make_organization(db_session, name="Org B")
    org_c = make_organization(db_session, name="Org C")
    user = make_user(db_session, email="multi-owner@example.com")
    make_organization_membership(db_session, user=user, organization=org_a, role=UserRole.OWNER)
    make_organization_membership(db_session, user=user, organization=org_b, role=UserRole.OWNER)
    make_organization_membership(db_session, user=user, organization=org_c, role=UserRole.MEMBER)

    with pytest.raises(DomainValidationError):
        _service(db_session).update(org_a.id, user.id, UserUpdate(status=UserStatus.DISABLED))

    refreshed = UserRepository(db_session).get(user.id)
    assert refreshed is not None
    assert refreshed.status == UserStatus.ACTIVE


def test_disabling_a_user_who_owns_one_org_but_has_a_co_owner_in_another_succeeds(
    db_session: Session,
) -> None:
    """User A: Owner of Org A (with a co-Owner, so safe) and merely a
    Member of Org B — nothing blocks disabling. Contrast with the
    sole-Owner-of-a-second-org case above, which IS blocked."""
    org_a = make_organization(db_session, name="Org A")
    org_b = make_organization(db_session, name="Org B")
    user = make_user(db_session, email="safe-owner@example.com")
    make_organization_membership(db_session, user=user, organization=org_a, role=UserRole.OWNER)
    co_owner = make_user(db_session, email="co-owner@example.com")
    make_organization_membership(db_session, user=co_owner, organization=org_a, role=UserRole.OWNER)
    make_organization_membership(db_session, user=user, organization=org_b, role=UserRole.MEMBER)

    updated = _service(db_session).update(
        org_a.id, user.id, UserUpdate(status=UserStatus.DISABLED)
    )
    assert updated.status == UserStatus.DISABLED


def test_disabling_an_already_disabled_user_is_idempotent(
    db_session: Session, organization: Organization
) -> None:
    """A sole Owner who is somehow already disabled (pre-existing data, or
    a second identical request) can be "disabled" again without error —
    nothing about the org's ownership situation gets worse."""
    owner = _disabled_owner(db_session, organization, email="sole-owner@example.com")

    updated = _service(db_session).update(
        organization.id, owner.id, UserUpdate(status=UserStatus.DISABLED)
    )
    assert updated.status == UserStatus.DISABLED


def test_re_enabling_a_user_is_never_blocked_by_the_invariant(
    db_session: Session, organization: Organization
) -> None:
    owner = _disabled_owner(db_session, organization, email="sole-owner@example.com")

    updated = _service(db_session).update(
        organization.id, owner.id, UserUpdate(status=UserStatus.ACTIVE)
    )
    assert updated.status == UserStatus.ACTIVE


def test_a_blocked_disable_leaves_the_whole_request_unchanged_after_rollback(
    db_session: Session, organization: Organization
) -> None:
    """A combined PATCH (display_name + status=disabled) that trips the
    invariant must not leave a half-applied user once the surrounding
    request transaction rolls back — app/core/database.py::get_db() always
    rolls back the WHOLE request on any exception a service raises
    mid-request, so a real API call never persists a partial update
    regardless of what UserService.update flushed internally before
    raising. This test reproduces that same rollback explicitly, since a
    bare db_session (unlike get_db()) doesn't do it automatically."""
    owner = _owner(db_session, organization, email="sole-owner@example.com")
    owner.display_name = "Original Name"
    db_session.flush()
    db_session.commit()

    with pytest.raises(DomainValidationError):
        _service(db_session).update(
            organization.id,
            owner.id,
            UserUpdate(display_name="Renamed Owner", status=UserStatus.DISABLED),
        )
    db_session.rollback()

    refreshed = UserRepository(db_session).get(owner.id)
    assert refreshed is not None
    assert refreshed.status == UserStatus.ACTIVE
    assert refreshed.display_name == "Original Name"
