"""Pure tests of the Phase 17 prioritization scoring layer — no database,
no FastAPI (same discipline as tests/domain/test_risk.py and
tests/domain/test_skills.py).
"""

from decimal import Decimal

import pytest

from app.core.exceptions import DomainValidationError
from app.domain.prioritization import (
    CriterionWeight,
    PriorityScoreResult,
    calculate_ice_score,
    calculate_moscow_result,
    calculate_priority_score,
    calculate_rice_score,
    calculate_weighted_score,
    calculate_wsjf_score,
    detects_cycle,
    rank_priority_results,
    validate_category_for_framework_type,
)
from app.models.enums import MoscowCategory, PrioritizationFrameworkType

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


# ---------------------------------------------------------------------------
# calculate_ice_score (Phase 18)
# ---------------------------------------------------------------------------


def test_ice_score_is_average_of_impact_confidence_ease() -> None:
    result = calculate_ice_score(
        {"impact": Decimal(8), "confidence": Decimal(7), "ease": Decimal(6)}
    )
    assert result.score == Decimal(21) / Decimal(3)
    assert result.missing_criteria == ()


def test_ice_score_is_none_with_missing_criteria() -> None:
    result = calculate_ice_score({"impact": Decimal(8)})
    assert result.score is None
    assert set(result.missing_criteria) == {"confidence", "ease"}
    assert result.breakdown == {"impact": Decimal(8)}


# ---------------------------------------------------------------------------
# calculate_wsjf_score (Phase 18)
# ---------------------------------------------------------------------------


def test_wsjf_score_is_cost_of_delay_divided_by_job_size() -> None:
    result = calculate_wsjf_score(
        {
            "business_value": Decimal(8),
            "time_criticality": Decimal(5),
            "risk_reduction_opportunity_enablement": Decimal(3),
            "job_size": Decimal(4),
        }
    )
    assert result.score == Decimal(16) / Decimal(4)
    assert result.missing_criteria == ()


def test_wsjf_score_rejects_zero_job_size() -> None:
    with pytest.raises(DomainValidationError):
        calculate_wsjf_score(
            {
                "business_value": Decimal(8),
                "time_criticality": Decimal(5),
                "risk_reduction_opportunity_enablement": Decimal(3),
                "job_size": Decimal(0),
            }
        )


def test_wsjf_score_is_none_with_missing_criteria() -> None:
    result = calculate_wsjf_score({"business_value": Decimal(8)})
    assert result.score is None
    assert set(result.missing_criteria) == {
        "time_criticality",
        "risk_reduction_opportunity_enablement",
        "job_size",
    }


# ---------------------------------------------------------------------------
# calculate_moscow_result (Phase 18)
# ---------------------------------------------------------------------------


def test_moscow_result_never_produces_a_numeric_score() -> None:
    result = calculate_moscow_result(MoscowCategory.MUST)
    assert result.score is None
    assert result.category == MoscowCategory.MUST
    assert result.missing_criteria == ()
    assert result.breakdown == {}


def test_moscow_result_with_no_category_is_still_score_none() -> None:
    result = calculate_moscow_result(None)
    assert result.score is None
    assert result.category is None


def test_dispatch_routes_moscow_to_the_moscow_result() -> None:
    result = calculate_priority_score(
        PrioritizationFrameworkType.MOSCOW, [], {}, category=MoscowCategory.SHOULD
    )
    assert result.score is None
    assert result.category == MoscowCategory.SHOULD


def test_dispatch_routes_ice_to_the_ice_formula() -> None:
    result = calculate_priority_score(
        PrioritizationFrameworkType.ICE,
        [],
        {"impact": Decimal(9), "confidence": Decimal(9), "ease": Decimal(9)},
    )
    assert result.score == Decimal(9)


def test_dispatch_routes_wsjf_to_the_wsjf_formula() -> None:
    result = calculate_priority_score(
        PrioritizationFrameworkType.WSJF,
        [],
        {
            "business_value": Decimal(2),
            "time_criticality": Decimal(2),
            "risk_reduction_opportunity_enablement": Decimal(2),
            "job_size": Decimal(3),
        },
    )
    assert result.score == Decimal(2)


# ---------------------------------------------------------------------------
# detects_cycle (Phase 18)
# ---------------------------------------------------------------------------


def test_detects_cycle_true_for_direct_self_loop() -> None:
    assert detects_cycle([], ("a", "a")) is True


def test_detects_cycle_true_when_new_edge_closes_a_loop() -> None:
    # a -> b -> c already exists; adding c -> a would close the cycle.
    existing = [("a", "b"), ("b", "c")]
    assert detects_cycle(existing, ("c", "a")) is True


def test_detects_cycle_false_when_no_path_back_exists() -> None:
    existing = [("a", "b"), ("b", "c")]
    assert detects_cycle(existing, ("a", "d")) is False


def test_detects_cycle_false_for_disjoint_edges() -> None:
    existing = [("x", "y")]
    assert detects_cycle(existing, ("a", "b")) is False


def test_detects_cycle_false_for_a_reverse_edge_with_no_existing_edges() -> None:
    assert detects_cycle([], ("a", "b")) is False


def test_detects_cycle_true_for_immediate_reverse_edge() -> None:
    # a -> b already exists; adding b -> a is a 2-node cycle.
    assert detects_cycle([("a", "b")], ("b", "a")) is True


# ---------------------------------------------------------------------------
# rank_priority_results (Phase 20)
# ---------------------------------------------------------------------------


def _result(score: Decimal | None, category: MoscowCategory | None = None) -> PriorityScoreResult:
    return PriorityScoreResult(score=score, missing_criteria=(), breakdown={}, category=category)


def test_rank_priority_results_orders_by_score_descending() -> None:
    entries = [("low", _result(Decimal(10))), ("high", _result(Decimal(1000)))]
    ranked = rank_priority_results(entries)
    assert [key for key, _, _ in ranked] == ["high", "low"]
    assert [rank for _, _, rank in ranked] == [1, 2]


def test_rank_priority_results_puts_missing_score_last_and_unranked() -> None:
    entries = [
        ("complete", _result(Decimal(1))),
        ("incomplete", _result(None)),
    ]
    ranked = rank_priority_results(entries)
    assert [key for key, _, _ in ranked] == ["complete", "incomplete"]
    incomplete_rank = next(rank for key, _, rank in ranked if key == "incomplete")
    assert incomplete_rank is None


def test_rank_priority_results_ranks_a_moscow_result_last_and_unranked() -> None:
    """A MOSCOW result's score is always None (categorical, never
    numeric) — it must be ranked exactly like an incomplete numeric
    score, never sorted as if None meant zero."""
    entries = [
        ("numeric", _result(Decimal(5))),
        ("moscow", _result(None, category=MoscowCategory.MUST)),
    ]
    ranked = rank_priority_results(entries)
    assert [key for key, _, _ in ranked] == ["numeric", "moscow"]
    moscow_rank = next(rank for key, _, rank in ranked if key == "moscow")
    assert moscow_rank is None


def test_rank_priority_results_empty_input() -> None:
    assert rank_priority_results([]) == []


# ---------------------------------------------------------------------------
# validate_category_for_framework_type (Phase 20 extraction)
# ---------------------------------------------------------------------------


def test_validate_category_allows_moscow_with_category() -> None:
    validate_category_for_framework_type(PrioritizationFrameworkType.MOSCOW, MoscowCategory.MUST)


def test_validate_category_allows_none_for_any_framework() -> None:
    validate_category_for_framework_type(PrioritizationFrameworkType.RICE, None)


def test_validate_category_rejects_category_for_non_moscow_framework() -> None:
    with pytest.raises(DomainValidationError):
        validate_category_for_framework_type(PrioritizationFrameworkType.RICE, MoscowCategory.MUST)
