from sqlalchemy import delete, select

from app.models.session import UserSession
from app.repositories.base import BaseRepository


class UserSessionRepository(BaseRepository[UserSession]):
    model = UserSession

    def get_by_token_hash(self, token_hash: str) -> UserSession | None:
        return self.session.scalar(
            select(UserSession).where(UserSession.token_hash == token_hash)
        )

    def delete_by_token_hash(self, token_hash: str) -> None:
        self.session.execute(delete(UserSession).where(UserSession.token_hash == token_hash))
        self.session.flush()
