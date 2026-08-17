import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SkillProficiency


class ProjectSkillRequirementCreate(BaseModel):
    """project_id is taken from the URL path
    (POST /projects/{project_id}/skill-requirements), not the body."""

    skill_id: uuid.UUID
    required_hours: Decimal = Field(gt=0)
    minimum_proficiency: SkillProficiency | None = None
    notes: str | None = None


class ProjectSkillRequirementUpdate(BaseModel):
    required_hours: Decimal | None = Field(default=None, gt=0)
    minimum_proficiency: SkillProficiency | None = None
    notes: str | None = None


class ProjectSkillRequirementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    skill_id: uuid.UUID
    required_hours: Decimal
    minimum_proficiency: SkillProficiency | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
