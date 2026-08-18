import uuid

from app.core.exceptions import ConflictError, DomainValidationError, ForbiddenError, NotFoundError
from app.core.security import hash_password
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.person import PersonRepository
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate

_ESCALATED_ROLES = frozenset({UserRole.OWNER, UserRole.ADMIN})


class UserService:
    """User account management (Phase 10) — CRUD plus the Owner-escalation
    and last-Owner invariants. See docs/adr/0010-authentication-rbac-audit.md.

    change_role takes an explicit acting_user parameter — the one
    deliberate exception to this codebase's "services never take an actor"
    convention (see the ADR's Implementation Plan), because the check IS
    the business rule (who is allowed to grant an Owner/Admin role), not
    audit logging. The last-active-Owner invariant (both here in update()
    for a status change and in change_role() for a role change) depends
    only on the target user and the system's current Owner count, never on
    who's acting, so it needs no actor parameter."""

    def __init__(self, repository: UserRepository, person_repository: PersonRepository) -> None:
        self.repository = repository
        self.person_repository = person_repository

    def create(self, data: UserCreate) -> User:
        if self.repository.get_by_email(data.email) is not None:
            raise ConflictError(f"A user with email '{data.email}' already exists.")
        if data.person_id is not None:
            if self.person_repository.get(data.person_id) is None:
                raise NotFoundError("Person", data.person_id)
            if self.repository.get_by_person_id(data.person_id) is not None:
                raise ConflictError("This Person is already linked to a user account.")

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            display_name=data.display_name,
            role=data.role,
            person_id=data.person_id,
        )
        return self.repository.add(user)

    def get(self, user_id: uuid.UUID) -> User:
        user = self.repository.get(user_id)
        if user is None:
            raise NotFoundError("User", user_id)
        return user

    def list(self, *, limit: int = 100, offset: int = 0) -> tuple[list[User], int]:
        return self.repository.list_filtered(limit=limit, offset=offset)

    def update(self, user_id: uuid.UUID, data: UserUpdate) -> User:
        user = self.get(user_id)
        updates = data.model_dump(exclude_unset=True)

        new_person_id = updates.get("person_id")
        if new_person_id is not None and new_person_id != user.person_id:
            if self.person_repository.get(new_person_id) is None:
                raise NotFoundError("Person", new_person_id)
            existing = self.repository.get_by_person_id(new_person_id)
            if existing is not None and existing.id != user.id:
                raise ConflictError("This Person is already linked to a user account.")

        new_status = updates.get("status")
        if (
            new_status is not None
            and new_status != user.status
            and user.role == UserRole.OWNER
            and new_status != UserStatus.ACTIVE
            and self.repository.count_by_role(UserRole.OWNER) <= 1
        ):
            raise DomainValidationError(
                "Cannot disable the last remaining Owner account."
            )

        for field, value in updates.items():
            setattr(user, field, value)
        self.repository.session.flush()
        return user

    def change_role(self, user_id: uuid.UUID, new_role: UserRole, *, acting_user: User) -> User:
        user = self.get(user_id)

        if (
            user.role in _ESCALATED_ROLES or new_role in _ESCALATED_ROLES
        ) and acting_user.role != UserRole.OWNER:
            raise ForbiddenError("Only an Owner can grant or change an Owner/Admin role.")

        if (
            user.role == UserRole.OWNER
            and new_role != UserRole.OWNER
            and self.repository.count_by_role(UserRole.OWNER) <= 1
        ):
            raise DomainValidationError("Cannot demote the last remaining Owner.")

        user.role = new_role
        self.repository.session.flush()
        return user
