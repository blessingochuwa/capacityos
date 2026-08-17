import uuid

from app.core.exceptions import ConflictError, NotFoundError
from app.models.skill import Skill
from app.repositories.skill import SkillRepository
from app.schemas.skill import SkillCreate, SkillRead, SkillUpdate


class SkillService:
    def __init__(self, repository: SkillRepository) -> None:
        self.repository = repository

    def create(self, data: SkillCreate) -> Skill:
        if self.repository.get_by_name(data.name) is not None:
            raise ConflictError(f"A skill named '{data.name}' already exists.")
        skill = Skill(name=data.name, description=data.description, category=data.category)
        return self.repository.add(skill)

    def get(self, skill_id: uuid.UUID) -> Skill:
        skill = self.repository.get(skill_id)
        if skill is None:
            raise NotFoundError("Skill", skill_id)
        return skill

    def get_read(self, skill_id: uuid.UUID) -> SkillRead:
        skill = self.get(skill_id)
        count = self.repository.person_counts([skill.id]).get(skill.id, 0)
        return SkillRead.model_validate(skill).model_copy(update={"person_count": count})

    def list(
        self, *, is_active: bool | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[list[SkillRead], int]:
        items, total = self.repository.list_filtered(
            is_active=is_active, limit=limit, offset=offset
        )
        counts = self.repository.person_counts([skill.id for skill in items])
        return [
            SkillRead.model_validate(skill).model_copy(
                update={"person_count": counts.get(skill.id, 0)}
            )
            for skill in items
        ], total

    def update(self, skill_id: uuid.UUID, data: SkillUpdate) -> Skill:
        skill = self.get(skill_id)
        updates = data.model_dump(exclude_unset=True)

        new_name = updates.get("name")
        if new_name is not None and new_name != skill.name:
            existing = self.repository.get_by_name(new_name)
            if existing is not None and existing.id != skill.id:
                raise ConflictError(f"A skill named '{new_name}' already exists.")

        for field, value in updates.items():
            setattr(skill, field, value)
        self.repository.session.flush()
        return skill

    def deactivate(self, skill_id: uuid.UUID) -> Skill:
        """A soft delete: is_active=False, never a hard DELETE — see
        Skill's docstring for why (PersonSkill/ProjectSkillRequirement
        history preservation)."""
        skill = self.get(skill_id)
        skill.is_active = False
        self.repository.session.flush()
        return skill
