import uuid
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import ProjectStatus


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.PLANNED
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    """Partial update. Date-range consistency against the *current* stored
    values (not just what's in this payload) is re-checked by
    ProjectService.update — this schema only rejects a payload that is
    self-contradictory on its own."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
