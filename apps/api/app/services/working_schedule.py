import uuid

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.domain.dates import ranges_overlap
from app.models.working_schedule import WorkingSchedule, WorkingScheduleEntry
from app.repositories.person import PersonRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.working_schedule import WorkingScheduleCreate, WorkingScheduleUpdate


class WorkingScheduleService:
    """Organization-scoped (Phase 12) — see app/services/person.py's
    docstring for the general pattern this follows."""

    def __init__(
        self, repository: WorkingScheduleRepository, person_repository: PersonRepository
    ) -> None:
        self.repository = repository
        self.person_repository = person_repository

    def create(self, organization_id: uuid.UUID, data: WorkingScheduleCreate) -> WorkingSchedule:
        if self.person_repository.get(data.person_id, organization_id) is None:
            raise NotFoundError("Person", data.person_id)
        if data.external_id is not None and self.repository.get_by_external_id(
            data.external_id, organization_id
        ):
            raise ConflictError(
                f"A working schedule with external_id {data.external_id} already exists."
            )

        # A person can only have one *normal* working pattern effective on any
        # given date — unlike availability exceptions, two overlapping
        # WorkingSchedules aren't a realistic scenario, they're a data-entry
        # mistake, so this is rejected here rather than resolved later by a
        # tie-break rule in the capacity engine (see
        # docs/adr/0003-phase-2-capacity-engine.md decision #3).
        for existing in self.repository.list_for_person(data.person_id, organization_id):
            if ranges_overlap(
                data.effective_start_date,
                data.effective_end_date,
                existing.effective_start_date,
                existing.effective_end_date,
            ):
                raise DomainValidationError(
                    "effective date range overlaps an existing working schedule for this person"
                )

        schedule = WorkingSchedule(
            organization_id=organization_id,
            person_id=data.person_id,
            effective_start_date=data.effective_start_date,
            effective_end_date=data.effective_end_date,
            external_id=data.external_id,
            entries=[
                WorkingScheduleEntry(weekday=entry.weekday, hours=entry.hours)
                for entry in data.entries
            ],
        )
        return self.repository.add(schedule)

    def get(self, organization_id: uuid.UUID, schedule_id: uuid.UUID) -> WorkingSchedule:
        schedule = self.repository.get(schedule_id, organization_id)
        if schedule is None:
            raise NotFoundError("WorkingSchedule", schedule_id)
        return schedule

    def list_for_person(
        self, organization_id: uuid.UUID, person_id: uuid.UUID
    ) -> list[WorkingSchedule]:
        if self.person_repository.get(person_id, organization_id) is None:
            raise NotFoundError("Person", person_id)
        return self.repository.list_for_person(person_id, organization_id)

    def update(
        self, organization_id: uuid.UUID, schedule_id: uuid.UUID, data: WorkingScheduleUpdate
    ) -> WorkingSchedule:
        schedule = self.get(organization_id, schedule_id)
        updates = data.model_dump(exclude_unset=True, exclude={"entries"})

        merged_start = updates.get("effective_start_date", schedule.effective_start_date)
        merged_end = updates.get("effective_end_date", schedule.effective_end_date)
        if merged_start and merged_end and merged_end < merged_start:
            raise DomainValidationError("effective_end_date cannot precede effective_start_date")

        for existing in self.repository.list_for_person(schedule.person_id, organization_id):
            if existing.id == schedule.id:
                continue
            if ranges_overlap(
                merged_start, merged_end, existing.effective_start_date, existing.effective_end_date
            ):
                raise DomainValidationError(
                    "effective date range overlaps an existing working schedule for this person"
                )

        new_external_id = updates.get("external_id")
        if new_external_id is not None and new_external_id != schedule.external_id:
            existing_match = self.repository.get_by_external_id(new_external_id, organization_id)
            if existing_match is not None and existing_match.id != schedule.id:
                raise ConflictError(
                    f"A working schedule with external_id {new_external_id} already exists."
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

    def delete(self, organization_id: uuid.UUID, schedule_id: uuid.UUID) -> None:
        self.repository.delete(self.get(organization_id, schedule_id))
