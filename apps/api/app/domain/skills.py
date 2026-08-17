"""Pure classification/derivation functions for Phase 7 skills & bottleneck
analysis (CLAUDE.md §39 Phase 7).

Consumes only numbers the Phase 2 capacity engine already computes
(remaining_capacity, via app/services/planning_facts.py::load_people_facts +
app/domain/capacity.py::calculate_period_capacity) plus explicitly recorded
PersonSkill/ProjectSkillRequirement facts. No new capacity formula, no
second engine — the same discipline as app/domain/insights.py. Proficiency
is never inferred (not from job title, not from allocation history, not by
AI) — see docs/adr/0007-phase-7-skills-bottleneck-analysis.md.

No SQLAlchemy, no FastAPI, no I/O.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.domain.capacity import HOURS_QUANTUM, UTILIZATION_QUANTUM, ZERO
from app.models.enums import SkillProficiency

PROFICIENCY_RANK: dict[SkillProficiency, int] = {
    SkillProficiency.BEGINNER: 1,
    SkillProficiency.WORKING: 2,
    SkillProficiency.PROFICIENT: 3,
    SkillProficiency.ADVANCED: 4,
    SkillProficiency.EXPERT: 5,
}
"""The single place proficiency ordering is defined — see SkillProficiency's
docstring. Every comparison in this module goes through this table, never
enum declaration order or string comparison."""


def _quantize_hours(value: Decimal) -> Decimal:
    return value.quantize(HOURS_QUANTUM, rounding=ROUND_HALF_UP)


def _quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(UTILIZATION_QUANTUM, rounding=ROUND_HALF_UP)


def is_qualified(
    person_proficiency: SkillProficiency, minimum_proficiency: SkillProficiency | None
) -> bool:
    """minimum_proficiency=None means any recorded proficiency in the skill
    qualifies (see ProjectSkillRequirement docstring)."""
    if minimum_proficiency is None:
        return True
    return PROFICIENCY_RANK[person_proficiency] >= PROFICIENCY_RANK[minimum_proficiency]


@dataclass(frozen=True)
class QualifiedPerson:
    person_id: uuid.UUID
    proficiency: SkillProficiency
    remaining_capacity: Decimal
    """The person's real, unclamped remaining_capacity for the queried
    period (Phase 2 fact) — can be negative (over-allocated)."""

    @property
    def qualified_available_hours(self) -> Decimal:
        """max(remaining_capacity, 0) — a Phase 7 derived quantity, not a
        redefinition of Phase 2's remaining_capacity. An over-committed
        qualified person still counts as a holder of the skill (see
        single_skill_holder/skill_concentration below) but contributes no
        spare hours toward covering a requirement."""
        return max(self.remaining_capacity, ZERO)


@dataclass(frozen=True)
class SkillCoverageResult:
    required_hours: Decimal
    qualified_available_hours: Decimal
    coverage_ratio: Decimal
    gap_hours: Decimal
    qualified_person_ids: tuple[uuid.UUID, ...]
    """Every qualified holder, regardless of whether they have spare
    capacity — this is the population single_skill_holder/
    skill_concentration classify, since a fully-booked sole holder is still
    a single point of failure."""


def calculate_skill_coverage(
    required_hours: Decimal, qualified_people: Sequence[QualifiedPerson]
) -> SkillCoverageResult:
    """required_hours is enforced > 0 at the model layer (Project
    SkillRequirement), so coverage_ratio is always defined — no
    division-by-zero guard needed here."""
    qualified_available = _quantize_hours(
        sum((person.qualified_available_hours for person in qualified_people), ZERO)
    )
    gap = _quantize_hours(max(required_hours - qualified_available, ZERO))
    ratio = _quantize_ratio(qualified_available / required_hours)
    return SkillCoverageResult(
        required_hours=required_hours,
        qualified_available_hours=qualified_available,
        coverage_ratio=ratio,
        gap_hours=gap,
        qualified_person_ids=tuple(person.person_id for person in qualified_people),
    )


@dataclass(frozen=True)
class SkillConcentrationResult:
    holder_count: int
    top_contributor_ids: tuple[uuid.UUID, ...]
    top_contributor_hours: Decimal
    total_hours: Decimal
    ratio: Decimal


def calculate_skill_concentration(
    qualified_people: Sequence[QualifiedPerson], top_n: int = 1
) -> SkillConcentrationResult | None:
    """Reports how a skill's qualified AVAILABLE capacity is distributed
    among its holders. Gated on holder_count in {1, 2} — an EXISTENCE
    condition (there are structurally few enough holders that this is
    worth surfacing at all), never a magnitude/percentage threshold, same
    discipline as app/domain/insights.py::calculate_concentration.

    Deliberately not a generalization of insights.calculate_concentration:
    that function is keyed on ProjectPersonDemand (allocated hours to a
    project); this one is keyed on qualified capacity for a skill — a
    different fact about a different population. Coupling the two would
    make either module depend on a shape it doesn't otherwise need.

    Returns None when zero holders have any qualified available capacity,
    or when more than 2 do (not structurally concentrated).
    """
    contributors = [
        person for person in qualified_people if person.qualified_available_hours > ZERO
    ]
    if not contributors or len(contributors) > 2:
        return None
    total = _quantize_hours(sum((p.qualified_available_hours for p in contributors), ZERO))
    if total <= ZERO:
        return None
    ranked = sorted(
        contributors, key=lambda p: (-p.qualified_available_hours, str(p.person_id))
    )
    top = ranked[:top_n]
    top_hours = _quantize_hours(sum((p.qualified_available_hours for p in top), ZERO))
    return SkillConcentrationResult(
        holder_count=len(contributors),
        top_contributor_ids=tuple(p.person_id for p in top),
        top_contributor_hours=top_hours,
        total_hours=total,
        ratio=_quantize_ratio(top_hours / total),
    )


__all__ = [
    "PROFICIENCY_RANK",
    "QualifiedPerson",
    "SkillConcentrationResult",
    "SkillCoverageResult",
    "calculate_skill_concentration",
    "calculate_skill_coverage",
    "is_qualified",
]
