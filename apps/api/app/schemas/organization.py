import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    """Any authenticated user may create an organization (no permission
    check — see Permission.ORGANIZATION_MANAGE's docstring); the creator
    becomes its Owner in the same transaction (app/services/organization.py),
    so a new organization never starts with zero Owners."""

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")


class OrganizationUpdate(BaseModel):
    """Deliberately excludes slug (treated as an immutable identity key,
    same convention as external_id elsewhere) and is_active (see the
    dedicated deactivate endpoint — a lifecycle action, not a field edit)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
