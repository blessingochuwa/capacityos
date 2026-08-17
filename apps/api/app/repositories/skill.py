import uuid

from sqlalchemy import func, select

from app.models.person_skill import PersonSkill
from app.models.skill import Skill
from app.repositories.base import BaseRepository


class SkillRepository(BaseRepository[Skill]):
    model = Skill

    def get_by_name(self, name: str) -> Skill | None:
        return self.session.scalar(select(Skill).where(Skill.name == name))

    def list_by_names(self, names: list[str]) -> list[Skill]:
        """Batched lookup for Phase 6 import identity resolution."""
        if not names:
            return []
        return list(self.session.scalars(select(Skill).where(Skill.name.in_(names))))

    def list_by_ids(self, ids: list[uuid.UUID]) -> list[Skill]:
        if not ids:
            return []
        return list(self.session.scalars(select(Skill).where(Skill.id.in_(ids))))

    def list_filtered(
        self, *, is_active: bool | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[list[Skill], int]:
        stmt = select(Skill)
        if is_active is not None:
            stmt = stmt.where(Skill.is_active == is_active)

        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = list(
            self.session.scalars(stmt.order_by(Skill.name).limit(limit).offset(offset))
        )
        return items, total

    def person_counts(self, skill_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Number of PersonSkill rows per skill, one GROUP BY query for the
        whole batch — never one COUNT per skill in a list response loop."""
        if not skill_ids:
            return {}
        rows = self.session.execute(
            select(PersonSkill.skill_id, func.count())
            .where(PersonSkill.skill_id.in_(skill_ids))
            .group_by(PersonSkill.skill_id)
        ).all()
        return {skill_id: count for skill_id, count in rows}
