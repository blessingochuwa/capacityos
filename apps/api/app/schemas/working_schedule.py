import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkingScheduleEntryCreate(BaseModel):
    weekday: int = Field(ge=0, le=6, description="0=Monday .. 6=Sunday (date.weekday())")
    hours: Decimal = Field(ge=0, le=24)


class WorkingScheduleEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    weekday: int
    hours: Decimal


class WorkingScheduleCreate(BaseModel):
    person_id: uuid.UUID
    effective_start_date: date | None = None
    effective_end_date: date | None = None
    entries: list[WorkingScheduleEntryCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_entries_and_dates(self) -> Self:
        weekdays = [entry.weekday for entry in self.entries]
        if len(weekdays) != len(set(weekdays)):
            raise ValueError("entries must not repeat the same weekday")
        if (
            self.effective_start_date
            and self.effective_end_date
            and self.effective_end_date < self.effective_start_date
        ):
            raise ValueError("effective_end_date cannot precede effective_start_date")
        return self


class WorkingScheduleUpdate(BaseModel):
    """entries, if provided, REPLACES the schedule's full entry set (not a
    merge) — see WorkingScheduleService.update."""

    effective_start_date: date | None = None
    effective_end_date: date | None = None
    entries: list[WorkingScheduleEntryCreate] | None = None

    @model_validator(mode="after")
    def _check_entries_and_dates(self) -> Self:
        if self.entries is not None:
            weekdays = [entry.weekday for entry in self.entries]
            if len(weekdays) != len(set(weekdays)):
                raise ValueError("entries must not repeat the same weekday")
        if (
            self.effective_start_date
            and self.effective_end_date
            and self.effective_end_date < self.effective_start_date
        ):
            raise ValueError("effective_end_date cannot precede effective_start_date")
        return self


class WorkingScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    person_id: uuid.UUID
    effective_start_date: date | None
    effective_end_date: date | None
    created_at: datetime
    updated_at: datetime
    entries: list[WorkingScheduleEntryRead]
