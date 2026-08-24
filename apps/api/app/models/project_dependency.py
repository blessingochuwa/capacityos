from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, utcnow
from app.models.enums import ProjectDependencyType

if TYPE_CHECKING:
    from app.models.project import Project


class ProjectDependency(Base, UUIDPrimaryKeyMixin):
    """A directed relationship from one Project to another (Phase 18,
    docs/PRD-phase-17-prioritization.md §7) — `from_project` `blocks`/
    `related`/`enables` `to_project`.

    `blocked_by` is deliberately NOT a stored type — it is always the
    reverse query of `blocks` for the other project (see
    app/services/project_dependency.py::list_for_project), matching
    ProjectAccessGrant's precedent of storing one direction and deriving
    the inverse view rather than storing both and risking them
    disagreeing with each other.

    Created/added or removed only — no "updated_at", matching
    TeamMembership's precedent (a grant-shaped row, not a business entity
    with an editable history — CLAUDE.md's own distinction, echoed in
    ADR 0011's TeamAccessGrant/ProjectAccessGrant design). Deleting either
    project cascades the edge away; there is nothing meaningful left to
    keep once one side is gone (contrast with Risk.owner_person_id's
    SET NULL — a dependency edge has no identity independent of the two
    projects it connects, the way a risk still means something after its
    owner leaves).
    """

    __tablename__ = "project_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "from_project_id",
            "to_project_id",
            "dependency_type",
            name="uq_project_dependency_from_to_type",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    from_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    to_project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dependency_type: Mapped[ProjectDependencyType] = mapped_column(
        Enum(
            ProjectDependencyType,
            name="ck_project_dependencies_dependency_type",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    from_project: Mapped[Project] = relationship(foreign_keys=[from_project_id])
    to_project: Mapped[Project] = relationship(foreign_keys=[to_project_id])
