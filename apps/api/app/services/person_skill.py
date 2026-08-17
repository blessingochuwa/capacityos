import uuid

from app.core.exceptions import ConflictError, DomainValidationError, NotFoundError
from app.models.person_skill import PersonSkill
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.skill import SkillRepository
from app.schemas.person_skill import PersonSkillCreate, PersonSkillUpdate


class PersonSkillService:
    def __init__(
        self,
        repository: PersonSkillRepository,
        person_repository: PersonRepository,
        skill_repository: SkillRepository,
    ) -> None:
        self.repository = repository
        self.person_repository = person_repository
        self.skill_repository = skill_repository

    def add(self, person_id: uuid.UUID, data: PersonSkillCreate) -> PersonSkill:
        if self.person_repository.get(person_id) is None:
            raise NotFoundError("Person", person_id)
        skill = self.skill_repository.get(data.skill_id)
        if skill is None:
            raise NotFoundError("Skill", data.skill_id)
        if not skill.is_active:
            raise DomainValidationError(f"Skill '{skill.name}' is not active.")
        if self.repository.get_by_person_and_skill(person_id, data.skill_id) is not None:
            raise ConflictError("This person already has a recorded proficiency for this skill.")

        person_skill = PersonSkill(
            person_id=person_id,
            skill_id=data.skill_id,
            proficiency=data.proficiency,
            notes=data.notes,
        )
        return self.repository.add(person_skill)

    def list_for_person(self, person_id: uuid.UUID) -> list[PersonSkill]:
        if self.person_repository.get(person_id) is None:
            raise NotFoundError("Person", person_id)
        return self.repository.list_for_person(person_id)

    def update(
        self, person_id: uuid.UUID, person_skill_id: uuid.UUID, data: PersonSkillUpdate
    ) -> PersonSkill:
        person_skill = self._get_owned(person_id, person_skill_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(person_skill, field, value)
        self.repository.session.flush()
        return person_skill

    def remove(self, person_id: uuid.UUID, person_skill_id: uuid.UUID) -> None:
        person_skill = self._get_owned(person_id, person_skill_id)
        self.repository.delete(person_skill)

    def _get_owned(self, person_id: uuid.UUID, person_skill_id: uuid.UUID) -> PersonSkill:
        person_skill = self.repository.get(person_skill_id)
        if person_skill is None or person_skill.person_id != person_id:
            raise NotFoundError("PersonSkill", person_skill_id)
        return person_skill
