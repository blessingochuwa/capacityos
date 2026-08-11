import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AvailabilityType


class AvailabilityExceptionBase(BaseModel):
    start_date: date
    end_date: date
    availability_type: AvailabilityType
    hours: Decimal | None = Field(
        default=None,
        ge=0,
        le=24,
        description=(
            "None = fully unavailable; a value = hours available per day during the period."
        ),
    )
    notes: str | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class AvailabilityExceptionCreate(AvailabilityExceptionBase):
    person_id: uuid.UUID


class AvailabilityExceptionUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    availability_type: AvailabilityType | None = None
    hours: Decimal | None = Field(default=None, ge=0, le=24)
    notes: str | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class AvailabilityExceptionRead(AvailabilityExceptionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    person_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
