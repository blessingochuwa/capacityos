"""Pure tests of the Phase 7 skill qualification/coverage/concentration
layer — no database, no FastAPI (same discipline as
tests/domain/test_capacity.py and tests/domain/test_insights.py).
"""

import uuid
from decimal import Decimal

from app.domain.skills import (
    PROFICIENCY_RANK,
    QualifiedPerson,
    calculate_skill_concentration,
    calculate_skill_coverage,
    is_qualified,
)
from app.models.enums import SkillProficiency

ZERO = Decimal("0.00")
PERSON_A = uuid.UUID(int=1)
PERSON_B = uuid.UUID(int=2)
PERSON_C = uuid.UUID(int=3)


# ---------------------------------------------------------------------------
# is_qualified / PROFICIENCY_RANK
# ---------------------------------------------------------------------------


def test_proficiency_rank_is_strictly_ordered() -> None:
    ordered = [
        SkillProficiency.BEGINNER,
        SkillProficiency.WORKING,
        SkillProficiency.PROFICIENT,
        SkillProficiency.ADVANCED,
        SkillProficiency.EXPERT,
    ]
    ranks = [PROFICIENCY_RANK[level] for level in ordered]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == len(ranks)


def test_no_minimum_proficiency_always_qualifies() -> None:
    assert is_qualified(SkillProficiency.BEGINNER, None) is True


def test_proficiency_meeting_minimum_qualifies() -> None:
    assert is_qualified(SkillProficiency.ADVANCED, SkillProficiency.WORKING) is True


def test_proficiency_exactly_at_minimum_qualifies() -> None:
    assert is_qualified(SkillProficiency.PROFICIENT, SkillProficiency.PROFICIENT) is True


def test_proficiency_below_minimum_does_not_qualify() -> None:
    assert is_qualified(SkillProficiency.BEGINNER, SkillProficiency.PROFICIENT) is False


# ---------------------------------------------------------------------------
# QualifiedPerson.qualified_available_hours
# ---------------------------------------------------------------------------


def test_qualified_available_hours_clamps_negative_remaining_to_zero() -> None:
    person = QualifiedPerson(
        person_id=PERSON_A, proficiency=SkillProficiency.EXPERT,
        remaining_capacity=Decimal("-8.00"),
    )
    assert person.qualified_available_hours == ZERO


def test_qualified_available_hours_passes_through_positive_remaining() -> None:
    person = QualifiedPerson(
        person_id=PERSON_A, proficiency=SkillProficiency.EXPERT,
        remaining_capacity=Decimal("12.00"),
    )
    assert person.qualified_available_hours == Decimal("12.00")


# ---------------------------------------------------------------------------
# calculate_skill_coverage
# ---------------------------------------------------------------------------


def test_full_coverage() -> None:
    qualified = [
        QualifiedPerson(PERSON_A, SkillProficiency.EXPERT, Decimal("40.00")),
        QualifiedPerson(PERSON_B, SkillProficiency.PROFICIENT, Decimal("40.00")),
    ]
    result = calculate_skill_coverage(Decimal("60.00"), qualified)
    assert result.required_hours == Decimal("60.00")
    assert result.qualified_available_hours == Decimal("80.00")
    assert result.gap_hours == ZERO
    assert result.coverage_ratio > Decimal("1.0")
    assert set(result.qualified_person_ids) == {PERSON_A, PERSON_B}


def test_partial_coverage() -> None:
    qualified = [QualifiedPerson(PERSON_A, SkillProficiency.PROFICIENT, Decimal("20.00"))]
    result = calculate_skill_coverage(Decimal("80.00"), qualified)
    assert result.qualified_available_hours == Decimal("20.00")
    assert result.gap_hours == Decimal("60.00")
    assert result.coverage_ratio == Decimal("0.2500")


def test_zero_qualified_capacity_gives_full_gap() -> None:
    result = calculate_skill_coverage(Decimal("40.00"), [])
    assert result.qualified_available_hours == ZERO
    assert result.gap_hours == Decimal("40.00")
    assert result.coverage_ratio == ZERO
    assert result.qualified_person_ids == ()


def test_over_allocated_qualified_person_contributes_no_hours_to_coverage() -> None:
    """A qualified holder who is already over-committed still appears in
    qualified_person_ids (a real holder of the skill — see
    single_skill_holder) but contributes 0 toward covering the gap."""
    qualified = [QualifiedPerson(PERSON_A, SkillProficiency.EXPERT, Decimal("-5.00"))]
    result = calculate_skill_coverage(Decimal("40.00"), qualified)
    assert result.qualified_available_hours == ZERO
    assert result.gap_hours == Decimal("40.00")
    assert result.qualified_person_ids == (PERSON_A,)


def test_coverage_never_reports_negative_gap() -> None:
    qualified = [QualifiedPerson(PERSON_A, SkillProficiency.EXPERT, Decimal("100.00"))]
    result = calculate_skill_coverage(Decimal("10.00"), qualified)
    assert result.gap_hours == ZERO


# ---------------------------------------------------------------------------
# calculate_skill_concentration
# ---------------------------------------------------------------------------


def test_single_holder_is_reported() -> None:
    qualified = [QualifiedPerson(PERSON_A, SkillProficiency.EXPERT, Decimal("20.00"))]
    result = calculate_skill_concentration(qualified)
    assert result is not None
    assert result.holder_count == 1
    assert result.top_contributor_ids == (PERSON_A,)
    assert result.ratio == Decimal("1.0000")


def test_two_holders_are_reported_as_concentrated() -> None:
    qualified = [
        QualifiedPerson(PERSON_A, SkillProficiency.EXPERT, Decimal("30.00")),
        QualifiedPerson(PERSON_B, SkillProficiency.WORKING, Decimal("10.00")),
    ]
    result = calculate_skill_concentration(qualified, top_n=1)
    assert result is not None
    assert result.holder_count == 2
    assert result.top_contributor_ids == (PERSON_A,)
    assert result.top_contributor_hours == Decimal("30.00")
    assert result.ratio == Decimal("0.7500")


def test_three_or_more_holders_is_not_concentrated() -> None:
    qualified = [
        QualifiedPerson(PERSON_A, SkillProficiency.EXPERT, Decimal("10.00")),
        QualifiedPerson(PERSON_B, SkillProficiency.WORKING, Decimal("10.00")),
        QualifiedPerson(PERSON_C, SkillProficiency.PROFICIENT, Decimal("10.00")),
    ]
    assert calculate_skill_concentration(qualified) is None


def test_zero_holders_with_available_capacity_is_not_concentrated() -> None:
    """Holders with zero/negative qualified_available_hours don't count —
    nothing to report a concentration of."""
    qualified = [QualifiedPerson(PERSON_A, SkillProficiency.EXPERT, Decimal("-5.00"))]
    assert calculate_skill_concentration(qualified) is None


def test_no_holders_is_not_concentrated() -> None:
    assert calculate_skill_concentration([]) is None


def test_concentration_ties_broken_deterministically_by_person_id() -> None:
    qualified = [
        QualifiedPerson(PERSON_B, SkillProficiency.EXPERT, Decimal("10.00")),
        QualifiedPerson(PERSON_A, SkillProficiency.EXPERT, Decimal("10.00")),
    ]
    result_1 = calculate_skill_concentration(qualified, top_n=1)
    result_2 = calculate_skill_concentration(list(reversed(qualified)), top_n=1)
    assert result_1 is not None
    assert result_1.top_contributor_ids == result_2.top_contributor_ids  # type: ignore[union-attr]
    assert result_1.top_contributor_ids == (PERSON_A,)
