import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamAccessGrantCreate(BaseModel):
    """team_id is taken from the URL path (POST /teams/{team_id}/access-grants),
    not the body — only the user being granted access needs to be specified."""

    user_id: uuid.UUID


class TeamAccessGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    team_id: uuid.UUID
    granted_by_user_id: uuid.UUID | None
    created_at: datetime


class ProjectAccessGrantCreate(BaseModel):
    user_id: uuid.UUID


class ProjectAccessGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    granted_by_user_id: uuid.UUID | None
    created_at: datetime
