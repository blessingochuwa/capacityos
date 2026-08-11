import uuid

from sqlalchemy import select

from app.models.working_schedule import WorkingSchedule
from app.repositories.base import BaseRepository


class WorkingScheduleRepository(BaseRepository[WorkingSchedule]):
    model = WorkingSchedule

    def list_for_person(self, person_id: uuid.UUID) -> list[WorkingSchedule]:
        return list(
            self.session.scalars(
                select(WorkingSchedule).where(WorkingSchedule.person_id == person_id)
            )
        )
