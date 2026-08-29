import uuid

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.core.security import hash_password
from app.models.enums import UserStatus
from app.models.user import User
from app.repositories.person import PersonRepository
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """User account management (Phase 10, revised Phase 12) — CRUD for the
    account/login identity only. Role and the Owner-escalation/last-Owner
    invariants moved to OrganizationMembershipService, since role is no
    longer a property of a User but of a User's membership in one
    Organization (see docs/adr/0012-organizations-multi-tenancy.md). A
    freshly created User has no role anywhere until an
    OrganizationMembership grants one.

    get/list remain deliberately unscoped — GET /users stays a global
    directory of accounts (Decision 8: the access-grant admin UI's
    "invite an existing user" flow searches all accounts by email, not
    just the acting organization's), unchanged from Phase 10/11. create/
    update take organization_id ONLY to validate an optional person_id
    link, since Person itself became organization-scoped in Phase 12 —
    a User's login identity stays global even though the Person it may
    link to belongs to exactly one organization.

    Phase 15: update() closes ADR 0012's other known gap — disabling a
    User whose account is the last active Owner of one of its
    organizations. See UserRepository.disable_if_safe and
    docs/adr/0015-last-owner-invariant.md.
    """

    def __init__(self, repository: UserRepository, person_repository: PersonRepository) -> None:
        self.repository = repository
        self.person_repository = person_repository

    def create(self, organization_id: uuid.UUID, data: UserCreate) -> User:
        if self.repository.get_by_email(data.email) is not None:
            raise ConflictError(f"A user with email '{data.email}' already exists.")
        if data.person_id is not None:
            if self.person_repository.get(data.person_id, organization_id) is None:
                raise NotFoundError("Person", data.person_id)
            if self.repository.get_by_person_id(data.person_id) is not None:
                raise ConflictError("This Person is already linked to a user account.")

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            display_name=data.display_name,
            person_id=data.person_id,
        )
        return self.repository.add(user)

    def get(self, user_id: uuid.UUID) -> User:
        user = self.repository.get(user_id)
        if user is None:
            raise NotFoundError("User", user_id)
        return user

    def list(
        self,
        *,
        q: str | None = None,
        status: UserStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[User], int]:
        return self.repository.list_filtered(q=q, status=status, limit=limit, offset=offset)

    def update(self, organization_id: uuid.UUID, user_id: uuid.UUID, data: UserUpdate) -> User:
        user = self.get(user_id)
        updates = data.model_dump(exclude_unset=True)

        new_person_id = updates.get("person_id")
        if new_person_id is not None and new_person_id != user.person_id:
            if self.person_repository.get(new_person_id, organization_id) is None:
                raise NotFoundError("Person", new_person_id)
            existing = self.repository.get_by_person_id(new_person_id)
            if existing is not None and existing.id != user.id:
                raise ConflictError("This Person is already linked to a user account.")

        disabling = (
            updates.get("status") == UserStatus.DISABLED and user.status != UserStatus.DISABLED
        )
        for field, value in updates.items():
            if field == "status" and disabling:
                continue  # applied atomically below, guarded by the last-owner invariant
            setattr(user, field, value)
        self.repository.session.flush()

        if disabling:
            if not self.repository.disable_if_safe(user_id):
                raise DomainValidationError(
                    "Cannot disable this user — they are the last remaining active "
                    "Owner of at least one organization they belong to."
                )
            self.repository.session.refresh(user)

        return user
