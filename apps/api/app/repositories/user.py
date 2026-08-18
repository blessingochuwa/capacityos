import uuid

from sqlalchemy import func, select

from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def get_by_person_id(self, person_id: uuid.UUID) -> User | None:
        return self.session.scalar(select(User).where(User.person_id == person_id))

    def count_by_role(self, role: UserRole) -> int:
        """Used to enforce "the system must always retain >=1 active
        Owner" (UserService) — counts active users at a given role."""
        return (
            self.session.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == role, User.status == UserStatus.ACTIVE)
            )
            or 0
        )

    def list_filtered(
        self, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[User], int]:
        total = self.session.scalar(select(func.count()).select_from(User)) or 0
        items = list(
            self.session.scalars(select(User).order_by(User.email).limit(limit).offset(offset))
        )
        return items, total
