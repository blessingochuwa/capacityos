import uuid

from sqlalchemy import select

from app.models.project_access_grant import ProjectAccessGrant
from app.repositories.base import BaseRepository


class ProjectAccessGrantRepository(BaseRepository[ProjectAccessGrant]):
    model = ProjectAccessGrant

    def get_by_user_and_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> ProjectAccessGrant | None:
        return self.session.scalar(
            select(ProjectAccessGrant).where(
                ProjectAccessGrant.user_id == user_id, ProjectAccessGrant.project_id == project_id
            )
        )

    def exists(self, user_id: uuid.UUID, project_id: uuid.UUID) -> bool:
        return self.get_by_user_and_project(user_id, project_id) is not None

    def list_for_project(self, project_id: uuid.UUID) -> list[ProjectAccessGrant]:
        return list(
            self.session.scalars(
                select(ProjectAccessGrant)
                .where(ProjectAccessGrant.project_id == project_id)
                .order_by(ProjectAccessGrant.created_at)
            )
        )

    def list_for_user(self, user_id: uuid.UUID) -> list[ProjectAccessGrant]:
        return list(
            self.session.scalars(
                select(ProjectAccessGrant)
                .where(ProjectAccessGrant.user_id == user_id)
                .order_by(ProjectAccessGrant.created_at)
            )
        )
