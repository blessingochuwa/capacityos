"""Pure tests of the Phase 5 signal classification/derivation layer — no
database, no FastAPI (same discipline as tests/domain/test_capacity.py and
tests/domain/test_scenario.py).
"""

import uuid
from decimal import Decimal

from app.domain.capacity import ProjectPersonDemand
from app.domain.insights import (
    calculate_concentration,
    calculate_imbalance,
    capacity_signal_severity,
    classify_capacity_signal,
    scenario_risk_severity,
    scenario_risk_trend,
)

ZERO = Decimal("0.00")
PERSON_A = uuid.UUID(int=1)
PERSON_B = uuid.UUID(int=2)
PERSON_C = uuid.UUID(int=3)
THRESHOLD = Decimal("1.00")


# ---------------------------------------------------------------------------
# classify_capacity_signal
# ---------------------------------------------------------------------------


def test_over_allocation_takes_precedence_regardless_of_remaining_sign() -> None:
    signal = classify_capacity_signal(
        effective_capacity=Decimal("40.00"),
        remaining_capacity=Decimal("-5.00"),
        over_allocation=Decimal("5.00"),
        period_days=5,
        low_capacity_threshold_per_day=THRESHOLD,
    )
    assert signal == "over_allocation"


def test_zero_remaining_capacity_when_effective_capacity_positive() -> None:
    signal = classify_capacity_signal(
        effective_capacity=Decimal("40.00"),
        remaining_capacity=ZERO,
        over_allocation=ZERO,
        period_days=5,
        low_capacity_threshold_per_day=THRESHOLD,
    )
    assert signal == "zero_remaining_capacity"


def test_zero_remaining_and_zero_effective_capacity_is_not_a_signal() -> None:
    """Mirrors ScenarioCalculationService._risks' existing gate: no capacity
    at all is not itself a signal."""
    signal = classify_capacity_signal(
        effective_capacity=ZERO,
        remaining_capacity=ZERO,
        over_allocation=ZERO,
        period_days=5,
        low_capacity_threshold_per_day=THRESHOLD,
    )
    assert signal is None


def test_low_capacity_at_exact_threshold_boundary() -> None:
    # 5.00h remaining / 5 days = 1.00h/day == threshold -> fires (<=, not <)
    signal = classify_capacity_signal(
        effective_capacity=Decimal("40.00"),
        remaining_capacity=Decimal("5.00"),
        over_allocation=ZERO,
        period_days=5,
        low_capacity_threshold_per_day=THRESHOLD,
    )
    assert signal == "low_capacity"


def test_low_capacity_one_cent_below_threshold_fires() -> None:
    # 4.95h remaining / 5 days = 0.99h/day, one cent below the 1.00h threshold
    signal = classify_capacity_signal(
        effective_capacity=Decimal("40.00"),
        remaining_capacity=Decimal("4.95"),
        over_allocation=ZERO,
        period_days=5,
        low_capacity_threshold_per_day=THRESHOLD,
    )
    assert signal == "low_capacity"


def test_low_capacity_one_cent_above_threshold_does_not_fire() -> None:
    # 5.05h remaining / 5 days = 1.01h/day, one cent above the 1.00h threshold
    signal = classify_capacity_signal(
        effective_capacity=Decimal("40.00"),
        remaining_capacity=Decimal("5.05"),
        over_allocation=ZERO,
        period_days=5,
        low_capacity_threshold_per_day=THRESHOLD,
    )
    assert signal is None


def test_low_capacity_well_above_threshold_does_not_fire() -> None:
    # 10.00h remaining / 5 days = 2.00h/day > 1.00h threshold
    signal = classify_capacity_signal(
        effective_capacity=Decimal("40.00"),
        remaining_capacity=Decimal("10.00"),
        over_allocation=ZERO,
        period_days=5,
        low_capacity_threshold_per_day=THRESHOLD,
    )
    assert signal is None


def test_healthy_capacity_returns_none() -> None:
    signal = classify_capacity_signal(
        effective_capacity=Decimal("40.00"),
        remaining_capacity=Decimal("20.00"),
        over_allocation=ZERO,
        period_days=5,
        low_capacity_threshold_per_day=THRESHOLD,
    )
    assert signal is None


# ---------------------------------------------------------------------------
# Severity mappings
# ---------------------------------------------------------------------------


def test_capacity_signal_severity_mapping() -> None:
    assert capacity_signal_severity("over_allocation") == "critical"
    assert capacity_signal_severity("low_capacity") == "warning"
    assert capacity_signal_severity("zero_remaining_capacity") == "info"


def test_scenario_risk_severity_mapping() -> None:
    assert scenario_risk_severity("over_allocation") == "critical"
    assert scenario_risk_severity("zero_remaining_capacity") == "info"


# ---------------------------------------------------------------------------
# scenario_risk_trend
# ---------------------------------------------------------------------------


def test_over_allocation_trend_worsened_when_scenario_value_higher() -> None:
    assert scenario_risk_trend("over_allocation", Decimal("2.00"), Decimal("6.00")) == "worsened"


def test_over_allocation_trend_improved_when_scenario_value_lower() -> None:
    assert scenario_risk_trend("over_allocation", Decimal("6.00"), Decimal("2.00")) == "improved"


def test_over_allocation_trend_unchanged_when_equal() -> None:
    assert scenario_risk_trend("over_allocation", Decimal("2.00"), Decimal("2.00")) == "unchanged"


def test_zero_remaining_trend_worsened_when_remaining_drops() -> None:
    # Remaining capacity moving toward/through zero is worse.
    result = scenario_risk_trend("zero_remaining_capacity", Decimal("4.00"), Decimal("0.00"))
    assert result == "worsened"


def test_zero_remaining_trend_improved_when_remaining_rises() -> None:
    result = scenario_risk_trend("zero_remaining_capacity", Decimal("0.00"), Decimal("4.00"))
    assert result == "improved"


def test_zero_remaining_trend_unchanged_when_equal() -> None:
    result = scenario_risk_trend("zero_remaining_capacity", Decimal("0.00"), Decimal("0.00"))
    assert result == "unchanged"


# ---------------------------------------------------------------------------
# calculate_concentration
# ---------------------------------------------------------------------------


def test_concentration_returns_none_with_exactly_two_contributors() -> None:
    by_person = [
        ProjectPersonDemand(person_id=PERSON_A, allocated_hours=Decimal("10.00")),
        ProjectPersonDemand(person_id=PERSON_B, allocated_hours=Decimal("10.00")),
    ]
    assert calculate_concentration(by_person) is None


def test_concentration_with_three_contributors_computes_exact_ratio() -> None:
    by_person = [
        ProjectPersonDemand(person_id=PERSON_A, allocated_hours=Decimal("50.00")),
        ProjectPersonDemand(person_id=PERSON_B, allocated_hours=Decimal("30.00")),
        ProjectPersonDemand(person_id=PERSON_C, allocated_hours=Decimal("20.00")),
    ]
    result = calculate_concentration(by_person)
    assert result is not None
    assert result.top_contributor_ids == (PERSON_A, PERSON_B)
    assert result.top_contributor_hours == Decimal("80.00")
    assert result.total_hours == Decimal("100.00")
    assert result.ratio == Decimal("0.8000")


def test_concentration_tie_broken_by_person_id() -> None:
    by_person = [
        ProjectPersonDemand(person_id=PERSON_C, allocated_hours=Decimal("10.00")),
        ProjectPersonDemand(person_id=PERSON_B, allocated_hours=Decimal("10.00")),
        ProjectPersonDemand(person_id=PERSON_A, allocated_hours=Decimal("10.00")),
    ]
    result = calculate_concentration(by_person)
    assert result is not None
    # Equal hours -> ties broken by person_id string ordering.
    assert result.top_contributor_ids == tuple(
        sorted([PERSON_A, PERSON_B, PERSON_C], key=str)[:2]
    )


def test_concentration_returns_none_when_total_is_zero() -> None:
    by_person = [
        ProjectPersonDemand(person_id=PERSON_A, allocated_hours=ZERO),
        ProjectPersonDemand(person_id=PERSON_B, allocated_hours=ZERO),
        ProjectPersonDemand(person_id=PERSON_C, allocated_hours=ZERO),
    ]
    assert calculate_concentration(by_person) is None


def test_concentration_returns_none_for_single_contributor() -> None:
    by_person = [ProjectPersonDemand(person_id=PERSON_A, allocated_hours=Decimal("10.00"))]
    assert calculate_concentration(by_person) is None


# ---------------------------------------------------------------------------
# calculate_imbalance
# ---------------------------------------------------------------------------


def test_imbalance_returns_none_with_one_null_utilization() -> None:
    members = [(PERSON_A, Decimal("1.2000")), (PERSON_B, None)]
    assert calculate_imbalance(members) is None


def test_imbalance_returns_none_when_utilization_equal() -> None:
    members = [(PERSON_A, Decimal("0.8000")), (PERSON_B, Decimal("0.8000"))]
    assert calculate_imbalance(members) is None


def test_imbalance_reports_min_max_spread() -> None:
    members = [(PERSON_A, Decimal("1.2000")), (PERSON_B, Decimal("0.4200"))]
    result = calculate_imbalance(members)
    assert result is not None
    assert result.min_person_id == PERSON_B
    assert result.min_utilization == Decimal("0.4200")
    assert result.max_person_id == PERSON_A
    assert result.max_utilization == Decimal("1.2000")
    assert result.spread == Decimal("0.7800")


def test_imbalance_selects_extremes_among_three_or_more_members() -> None:
    members = [
        (PERSON_A, Decimal("1.2000")),
        (PERSON_B, Decimal("0.4200")),
        (PERSON_C, Decimal("0.9000")),
    ]
    result = calculate_imbalance(members)
    assert result is not None
    assert result.min_person_id == PERSON_B
    assert result.max_person_id == PERSON_A


def test_imbalance_returns_none_when_all_utilization_null() -> None:
    members = [(PERSON_A, None), (PERSON_B, None)]
    assert calculate_imbalance(members) is None
