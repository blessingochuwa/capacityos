from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SkillProficiency

if TYPE_CHECKING:
    from app.models.person import Person
    from app.models.skill import Skill


class PersonSkill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A person's explicitly recorded proficiency in one skill (Phase 7).

    proficiency is a self-contained, explicitly entered data point — never
    inferred from job title, allocation history, or AI (CLAUDE.md §21/Phase
    7 spec). (person_id, skill_id) is unique: a person has at most one
    active proficiency record per skill (re-assessing a skill means
    updating this row, not adding a second one).
    """

    __tablename__ = "person_skills"
    __table_args__ = (
        UniqueConstraint("person_id", "skill_id", name="uq_person_skill_person_skill"),
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proficiency: Mapped[SkillProficiency] = mapped_column(
        Enum(
            SkillProficiency,
            name="ck_person_skills_proficiency",
            native_enum=False,
            validate_strings=True,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    person: Mapped[Person] = relationship(back_populates="person_skills")
    skill: Mapped[Skill] = relationship(back_populates="person_skills")
