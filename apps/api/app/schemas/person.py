import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import EmploymentStatus


class PersonBase(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    job_title: str | None = Field(default=None, max_length=200)
    timezone: str = Field(default="UTC", max_length=64)
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE


class PersonCreate(PersonBase):
    """display_name is optional on create — PersonService defaults it to
    "{first_name} {last_name}" when omitted (see app/services/person.py)."""

    display_name: str | None = Field(default=None, max_length=200)


class PersonUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str | None = Field(default=None, max_length=200)
    email: EmailStr | None = None
    job_title: str | None = Field(default=None, max_length=200)
    timezone: str | None = Field(default=None, max_length=64)
    employment_status: EmploymentStatus | None = None


class PersonRead(PersonBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    created_at: datetime
    updated_at: datetime
