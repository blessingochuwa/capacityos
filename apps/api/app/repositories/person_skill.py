import uuid

from sqlalchemy import func, select

from app.models.person_skill import PersonSkill
from app.repositories.base import BaseRepository


class PersonSkillRepository(BaseRepository[PersonSkill]):
    """Organization-scoped (Phase 12) — see app/repositories/person.py's
    docstring for the general pattern this follows."""

    model = PersonSkill

    def get(self, id_: uuid.UUID, organization_id: uuid.UUID) -> PersonSkill | None:  # pyright: ignore[reportIncompatibleMethodOverride]
        return self.session.scalar(
            select(PersonSkill).where(
                PersonSkill.id == id_, PersonSkill.organization_id == organization_id
            )
        )

    def list(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0
    ) -> tuple[list[PersonSkill], int]:
        total = (
            self.session.scalar(
                select(func.count())
                .select_from(PersonSkill)
                .where(PersonSkill.organization_id == organization_id)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                select(PersonSkill)
                .where(PersonSkill.organization_id == organization_id)
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def get_by_person_and_skill(
        self, person_id: uuid.UUID, skill_id: uuid.UUID, organization_id: uuid.UUID
    ) -> PersonSkill | None:
        return self.session.scalar(
            select(PersonSkill).where(
                PersonSkill.person_id == person_id,
                PersonSkill.skill_id == skill_id,
                PersonSkill.organization_id == organization_id,
            )
        )

    def list_for_person(
        self, person_id: uuid.UUID, organization_id: uuid.UUID
    ) -> list[PersonSkill]:
        return list(
            self.session.scalars(
                select(PersonSkill).where(
                    PersonSkill.person_id == person_id,
                    PersonSkill.organization_id == organization_id,
                )
            )
        )

    def list_for_people(
        self, person_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[PersonSkill]:
        """Batched — one query for the whole id list, same pattern as
        WorkingScheduleRepository.list_for_people etc."""
        if not person_ids:
            return []
        return list(
            self.session.scalars(
                select(PersonSkill).where(
                    PersonSkill.person_id.in_(person_ids),
                    PersonSkill.organization_id == organization_id,
                )
            )
        )

    def list_for_skill(self, skill_id: uuid.UUID, organization_id: uuid.UUID) -> list[PersonSkill]:
        """Every person with a recorded proficiency in one skill — the
        candidate pool before capacity/proficiency filtering (Phase 7
        qualification). One query, not one-per-person. organization_id
        (Phase 12) is what keeps this candidate pool from ever including
        another organization's people, even though it holds the same
        skill_id-only shape Phase 7 originally gave it."""
        return list(
            self.session.scalars(
                select(PersonSkill).where(
                    PersonSkill.skill_id == skill_id,
                    PersonSkill.organization_id == organization_id,
                )
            )
        )

    def list_for_skills(
        self, skill_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> list[PersonSkill]:
        if not skill_ids:
            return []
        return list(
            self.session.scalars(
                select(PersonSkill).where(
                    PersonSkill.skill_id.in_(skill_ids),
                    PersonSkill.organization_id == organization_id,
                )
            )
        )

    def list_by_pairs(
        self, pairs: list[tuple[uuid.UUID, uuid.UUID]], organization_id: uuid.UUID
    ) -> list[PersonSkill]:
        """Batched lookup for Phase 6 import identity resolution — existing
        (person_id, skill_id) rows for a set of candidate pairs."""
        if not pairs:
            return []
        person_ids = [pair[0] for pair in pairs]
        skill_ids = [pair[1] for pair in pairs]
        candidates = self.session.scalars(
            select(PersonSkill).where(
                PersonSkill.person_id.in_(person_ids),
                PersonSkill.skill_id.in_(skill_ids),
                PersonSkill.organization_id == organization_id,
            )
        )
        pair_set = set(pairs)
        return [row for row in candidates if (row.person_id, row.skill_id) in pair_set]
