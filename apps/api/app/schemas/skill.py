import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SkillBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None


class SkillRead(SkillBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    person_count: int = 0
    """The number of people currently holding this skill (any proficiency).
    Computed by SkillRepository.list_with_person_counts — one batched query,
    never one COUNT per skill (CLAUDE.md §19/Phase 7 performance)."""
