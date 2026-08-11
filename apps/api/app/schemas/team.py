import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class TeamCreate(TeamBase):
    pass


class TeamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class TeamRead(TeamBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
