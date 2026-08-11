import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import AllocationUnit


class AllocationBase(BaseModel):
    start_date: date
    end_date: date
    allocation_hours: Decimal = Field(ge=0)
    allocation_unit: AllocationUnit = AllocationUnit.TOTAL_HOURS
    notes: str | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class AllocationCreate(AllocationBase):
    person_id: uuid.UUID
    project_id: uuid.UUID


class AllocationUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    allocation_hours: Decimal | None = Field(default=None, ge=0)
    allocation_unit: AllocationUnit | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class AllocationRead(AllocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    person_id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
