import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    StakeholderDecisionAuthority,
    StakeholderInfluence,
    StakeholderInterest,
)


class StakeholderCreate(BaseModel):
    """project_id is taken from the URL path
    (POST /projects/{project_id}/stakeholders), not the body."""

    name: str = Field(min_length=1, max_length=200)
    person_id: uuid.UUID | None = None
    role: str = Field(min_length=1, max_length=200)
    influence: StakeholderInfluence = StakeholderInfluence.MEDIUM
    interest: StakeholderInterest = StakeholderInterest.MEDIUM
    decision_authority: StakeholderDecisionAuthority = StakeholderDecisionAuthority.INFORMED
    communication_needs: str | None = Field(default=None, max_length=2000)


class StakeholderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    person_id: uuid.UUID | None = None
    role: str | None = Field(default=None, min_length=1, max_length=200)
    influence: StakeholderInfluence | None = None
    interest: StakeholderInterest | None = None
    decision_authority: StakeholderDecisionAuthority | None = None
    communication_needs: str | None = Field(default=None, max_length=2000)


class StakeholderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    person_id: uuid.UUID | None
    role: str
    influence: StakeholderInfluence
    interest: StakeholderInterest
    decision_authority: StakeholderDecisionAuthority
    communication_needs: str | None
    created_at: datetime
    updated_at: datetime
