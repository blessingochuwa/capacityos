import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TeamMembershipCreate(BaseModel):
    """team_id is taken from the URL path (POST /teams/{team_id}/members),
    not the body — only the person being added needs to be specified."""

    person_id: uuid.UUID


class TeamMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    person_id: uuid.UUID
    team_id: uuid.UUID
    created_at: datetime
