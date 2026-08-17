import uuid

from sqlalchemy import select

from app.models.person_skill import PersonSkill
from app.repositories.base import BaseRepository


class PersonSkillRepository(BaseRepository[PersonSkill]):
    model = PersonSkill

    def get_by_person_and_skill(
        self, person_id: uuid.UUID, skill_id: uuid.UUID
    ) -> PersonSkill | None:
        return self.session.scalar(
            select(PersonSkill).where(
                PersonSkill.person_id == person_id, PersonSkill.skill_id == skill_id
            )
        )

    def list_for_person(self, person_id: uuid.UUID) -> list[PersonSkill]:
        return list(
            self.session.scalars(
                select(PersonSkill).where(PersonSkill.person_id == person_id)
            )
        )

    def list_for_people(self, person_ids: list[uuid.UUID]) -> list[PersonSkill]:
        """Batched — one query for the whole id list, same pattern as
        WorkingScheduleRepository.list_for_people etc."""
        if not person_ids:
            return []
        return list(
            self.session.scalars(
                select(PersonSkill).where(PersonSkill.person_id.in_(person_ids))
            )
        )

    def list_for_skill(self, skill_id: uuid.UUID) -> list[PersonSkill]:
        """Every person with a recorded proficiency in one skill — the
        candidate pool before capacity/proficiency filtering (Phase 7
        qualification). One query, not one-per-person."""
        return list(
            self.session.scalars(select(PersonSkill).where(PersonSkill.skill_id == skill_id))
        )

    def list_for_skills(self, skill_ids: list[uuid.UUID]) -> list[PersonSkill]:
        if not skill_ids:
            return []
        return list(
            self.session.scalars(
                select(PersonSkill).where(PersonSkill.skill_id.in_(skill_ids))
            )
        )

    def list_by_pairs(self, pairs: list[tuple[uuid.UUID, uuid.UUID]]) -> list[PersonSkill]:
        """Batched lookup for Phase 6 import identity resolution — existing
        (person_id, skill_id) rows for a set of candidate pairs."""
        if not pairs:
            return []
        person_ids = [pair[0] for pair in pairs]
        skill_ids = [pair[1] for pair in pairs]
        candidates = self.session.scalars(
            select(PersonSkill).where(
                PersonSkill.person_id.in_(person_ids), PersonSkill.skill_id.in_(skill_ids)
            )
        )
        pair_set = set(pairs)
        return [row for row in candidates if (row.person_id, row.skill_id) in pair_set]
