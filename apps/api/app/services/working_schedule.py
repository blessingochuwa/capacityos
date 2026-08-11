import uuid
from datetime import date

from app.core.exceptions import DomainValidationError, NotFoundError
from app.models.working_schedule import WorkingSchedule, WorkingScheduleEntry
from app.repositories.person import PersonRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.working_schedule import WorkingScheduleCreate, WorkingScheduleUpdate


def _ranges_overlap(
    start_a: date | None, end_a: date | None, start_b: date | None, end_b: date | None
) -> bool:
    """Whether two nullable [start, end] ranges overlap. None on either end of
    a range means unbounded in that direction (see WorkingSchedule.effective_*)."""
    a_starts_before_b_ends = start_a is None or end_b is None or start_a <= end_b
    b_starts_before_a_ends = start_b is None or end_a is None or start_b <= end_a
    return a_starts_before_b_ends and b_starts_before_a_ends


class WorkingScheduleService:
    def __init__(
        self, repository: WorkingScheduleRepository, person_repository: PersonRepository
    ) -> None:
        self.repository = repository
        self.person_repository = person_repository

    def create(self, data: WorkingScheduleCreate) -> WorkingSchedule:
        if self.person_repository.get(data.person_id) is None:
            raise NotFoundError("Person", data.person_id)

        # A person can only have one *normal* working pattern effective on any
        # given date — unlike availability exceptions, two overlapping
        # WorkingSchedules aren't a realistic scenario, they're a data-entry
        # mistake, so this is rejected here rather than resolved later by a
        # tie-break rule in the capacity engine (see
        # docs/adr/0003-phase-2-capacity-engine.md decision #3).
        for existing in self.repository.list_for_person(data.person_id):
            if _ranges_overlap(
                data.effective_start_date,
                data.effective_end_date,
                existing.effective_start_date,
                existing.effective_end_date,
            ):
                raise DomainValidationError(
                    "effective date range overlaps an existing working schedule for this person"
                )

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

        for existing in self.repository.list_for_person(schedule.person_id):
            if existing.id == schedule.id:
                continue
            if _ranges_overlap(
                merged_start, merged_end, existing.effective_start_date, existing.effective_end_date
            ):
                raise DomainValidationError(
                    "effective date range overlaps an existing working schedule for this person"
                )

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
