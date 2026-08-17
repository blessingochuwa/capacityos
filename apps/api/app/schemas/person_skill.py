import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SkillProficiency


class PersonSkillCreate(BaseModel):
    """person_id is taken from the URL path (POST /people/{person_id}/skills),
    not the body — matches TeamMembershipCreate's convention."""

    skill_id: uuid.UUID
    proficiency: SkillProficiency
    notes: str | None = Field(default=None, max_length=2000)


class PersonSkillUpdate(BaseModel):
    proficiency: SkillProficiency | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PersonSkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    person_id: uuid.UUID
    skill_id: uuid.UUID
    proficiency: SkillProficiency
    notes: str | None
    created_at: datetime
    updated_at: datetime
