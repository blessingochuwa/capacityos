import uuid

from app.core.exceptions import DomainValidationError, NotFoundError
from app.models.working_schedule import WorkingSchedule, WorkingScheduleEntry
from app.repositories.person import PersonRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.working_schedule import WorkingScheduleCreate, WorkingScheduleUpdate


class WorkingScheduleService:
    def __init__(
        self, repository: WorkingScheduleRepository, person_repository: PersonRepository
    ) -> None:
        self.repository = repository
        self.person_repository = person_repository

    def create(self, data: WorkingScheduleCreate) -> WorkingSchedule:
        if self.person_repository.get(data.person_id) is None:
            raise NotFoundError("Person", data.person_id)

        schedule = WorkingSchedule(
            person_id=data.person_id,
            effective_start_date=data.effective_start_date,
            effective_end_date=data.effective_end_date,
            entries=[
                WorkingScheduleEntry(weekday=entry.weekday, hours=entry.hours)
                for entry in data.entries
            ],
        )
        return self.repository.add(schedule)

    def get(self, schedule_id: uuid.UUID) -> WorkingSchedule:
        schedule = self.repository.get(schedule_id)
        if schedule is None:
            raise NotFoundError("WorkingSchedule", schedule_id)
        return schedule

    def list_for_person(self, person_id: uuid.UUID) -> list[WorkingSchedule]:
        if self.person_repository.get(person_id) is None:
            raise NotFoundError("Person", person_id)
        return self.repository.list_for_person(person_id)

    def update(self, schedule_id: uuid.UUID, data: WorkingScheduleUpdate) -> WorkingSchedule:
        schedule = self.get(schedule_id)
        updates = data.model_dump(exclude_unset=True, exclude={"entries"})

        merged_start = updates.get("effective_start_date", schedule.effective_start_date)
        merged_end = updates.get("effective_end_date", schedule.effective_end_date)
        if merged_start and merged_end and merged_end < merged_start:
            raise DomainValidationError("effective_end_date cannot precede effective_start_date")

        for field, value in updates.items():
            setattr(schedule, field, value)

        if data.entries is not None:
            # Flush the clear() before extend(): without this, the unit of
            # work may insert a replacement entry for a given weekday before
            # deleting the old one, tripping the (working_schedule_id,
            # weekday) unique constraint whenever the new entries reuse a
            # weekday from the old set (the common case).
            schedule.entries.clear()
            self.repository.session.flush()
            schedule.entries.extend(
                WorkingScheduleEntry(weekday=entry.weekday, hours=entry.hours)
                for entry in data.entries
            )

        self.repository.session.flush()
        return schedule

    def delete(self, schedule_id: uuid.UUID) -> None:
        self.repository.delete(self.get(schedule_id))
