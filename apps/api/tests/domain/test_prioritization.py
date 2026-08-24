"""Pure tests of the Phase 17 prioritization scoring layer — no database,
no FastAPI (same discipline as tests/domain/test_risk.py and
tests/domain/test_skills.py).
"""

from decimal import Decimal

import pytest

from app.core.exceptions import DomainValidationError
from app.domain.prioritization import (
    CriterionWeight,
    calculate_priority_score,
    calculate_rice_score,
    calculate_weighted_score,
)
from app.models.enums import PrioritizationFrameworkType

# ---------------------------------------------------------------------------
# calculate_rice_score
# ---------------------------------------------------------------------------


def test_rice_score_is_reach_times_impact_times_confidence_divided_by_effort() -> None:
    result = calculate_rice_score(
        {
            "reach": Decimal(1000),
            "impact": Decimal(2),
            "confidence": Decimal("0.8"),
            "effort": Decimal(4),
        }
    )
    assert result.score == Decimal(1000) * 2 * Decimal("0.8") / 4
    assert result.missing_criteria == ()


def test_rice_score_rejects_zero_effort() -> None:
    with pytest.raises(DomainValidationError):
        calculate_rice_score(
            {
                "reach": Decimal(1000),
                "impact": Decimal(2),
                "confidence": Decimal("0.8"),
                "effort": Decimal(0),
            }
        )


def test_rice_score_rejects_negative_effort() -> None:
    with pytest.raises(DomainValidationError):
        calculate_rice_score(
            {
                "reach": Decimal(1000),
                "impact": Decimal(2),
                "confidence": Decimal("0.8"),
                "effort": Decimal(-1),
            }
        )


def test_rice_score_is_none_with_missing_criteria() -> None:
    result = calculate_rice_score({"reach": Decimal(1000), "impact": Decimal(2)})
    assert result.score is None
    assert set(result.missing_criteria) == {"confidence", "effort"}
    assert result.breakdown == {"reach": Decimal(1000), "impact": Decimal(2)}


def test_rice_score_with_no_inputs_reports_all_four_missing() -> None:
    result = calculate_rice_score({})
    assert result.score is None
    assert set(result.missing_criteria) == {"reach", "impact", "confidence", "effort"}
    assert result.breakdown == {}


def test_rice_score_ignores_unrelated_keys_in_breakdown() -> None:
    """An unrecognized key in the submitted values (e.g. a stray key from
    a different framework) is simply not part of RICE's breakdown — the
    caller (service layer) is responsible for rejecting unknown criterion
    keys before they ever reach this pure function; this function's job
    is only to combine the four keys it actually knows about."""
    result = calculate_rice_score(
        {
            "reach": Decimal(1000),
            "impact": Decimal(2),
            "confidence": Decimal("0.8"),
            "effort": Decimal(4),
            "something_else": Decimal(99),
        }
    )
    assert result.score is not None
    assert "something_else" not in result.breakdown


# ---------------------------------------------------------------------------
# calculate_weighted_score
# ---------------------------------------------------------------------------


def test_weighted_score_is_sum_of_value_times_weight() -> None:
    criteria = [
        CriterionWeight(key="business_value", weight=Decimal(3)),
        CriterionWeight(key="urgency", weight=Decimal(2)),
    ]
    result = calculate_weighted_score(
        criteria, {"business_value": Decimal(8), "urgency": Decimal(5)}
    )
    assert result.score == Decimal(8) * 3 + Decimal(5) * 2
    assert result.missing_criteria == ()


def test_weighted_score_is_none_with_missing_criteria() -> None:
    criteria = [
        CriterionWeight(key="business_value", weight=Decimal(3)),
        CriterionWeight(key="urgency", weight=Decimal(2)),
    ]
    result = calculate_weighted_score(criteria, {"business_value": Decimal(8)})
    assert result.score is None
    assert result.missing_criteria == ("urgency",)
    assert result.breakdown == {"business_value": Decimal(8)}


def test_weighted_score_with_a_single_criterion() -> None:
    criteria = [CriterionWeight(key="value", weight=Decimal(1))]
    result = calculate_weighted_score(criteria, {"value": Decimal(7)})
    assert result.score == Decimal(7)


def test_weighted_score_with_no_criteria_and_no_values_is_zero() -> None:
    """An edge case, not a realistic framework (the schema layer requires
    at least one criterion for a Weighted Scoring framework) — included
    so the pure function's behavior at the boundary is explicit rather
    than accidental."""
    result = calculate_weighted_score([], {})
    assert result.score == Decimal(0)
    assert result.missing_criteria == ()


# ---------------------------------------------------------------------------
# calculate_priority_score — the dispatch point
# ---------------------------------------------------------------------------


def test_dispatch_routes_rice_to_the_rice_formula() -> None:
    result = calculate_priority_score(
        PrioritizationFrameworkType.RICE,
        [],
        {
            "reach": Decimal(100),
            "impact": Decimal(1),
            "confidence": Decimal(1),
            "effort": Decimal(1),
        },
    )
    assert result.score == Decimal(100)


def test_dispatch_routes_weighted_to_the_weighted_formula() -> None:
    criteria = [CriterionWeight(key="value", weight=Decimal(2))]
    result = calculate_priority_score(
        PrioritizationFrameworkType.WEIGHTED, criteria, {"value": Decimal(5)}
    )
    assert result.score == Decimal(10)
