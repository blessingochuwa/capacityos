"""Pure classification/derivation functions for Phase 5 operational insights
(CLAUDE.md §39 Phase 5).

Consumes only numbers already produced by app/domain/capacity.py and
app/domain/scenario.py, plus the one backend-owned LOW_CAPACITY threshold
(see docs/adr/0005-phase-5-operational-insights.md — a deliberate, single-
signal reversal of ADR 0004's "thresholds stay frontend-only" stance). No
new capacity formula is introduced anywhere in this module — every function
here classifies or derives from facts the Phase 2/4 engines already compute.

No SQLAlchemy, no FastAPI, no I/O — same discipline as app/domain/capacity.py
and app/domain/scenario.py.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from app.domain.capacity import HOURS_QUANTUM, UTILIZATION_QUANTUM, ZERO, ProjectPersonDemand


def _quantize_hours(value: Decimal) -> Decimal:
    return value.quantize(HOURS_QUANTUM, rounding=ROUND_HALF_UP)


def _quantize_utilization(value: Decimal) -> Decimal:
    return value.quantize(UTILIZATION_QUANTUM, rounding=ROUND_HALF_UP)


CapacitySignalType = Literal["over_allocation", "zero_remaining_capacity", "low_capacity"]
Severity = Literal["critical", "warning", "info"]
ScenarioRiskType = Literal["over_allocation", "zero_remaining_capacity"]
ScenarioSignalTrend = Literal["worsened", "improved", "unchanged"]


def classify_capacity_signal(
    *,
    effective_capacity: Decimal,
    remaining_capacity: Decimal,
    over_allocation: Decimal,
    period_days: int,
    low_capacity_threshold_per_day: Decimal,
) -> CapacitySignalType | None:
    """Mutually exclusive if/elif chain — same style as
    ScenarioCalculationService._risks, extended with one new tier:

    1. over_allocation > 0                                       -> "over_allocation"
    2. effective_capacity > 0 and remaining_capacity == 0         -> "zero_remaining_capacity"
    3. effective_capacity > 0, remaining_capacity > 0, and
       remaining_capacity/period_days <= threshold                -> "low_capacity"
    4. otherwise                                                  -> None

    remaining_per_day is quantized to HOURS_QUANTUM (same rounding as the
    rest of the engine) before comparison, so a threshold boundary behaves
    the same way "over_allocation > 0" already does — no float drift.

    A person/team with zero effective capacity and zero allocated hours
    (nothing to say about them at all) deliberately returns None rather than
    "zero_remaining_capacity" — that tier requires effective_capacity > 0,
    matching ScenarioCalculationService._risks' existing gate exactly.
    """
    if over_allocation > ZERO:
        return "over_allocation"
    if effective_capacity > ZERO and remaining_capacity == ZERO:
        return "zero_remaining_capacity"
    if effective_capacity > ZERO and remaining_capacity > ZERO:
        remaining_per_day = _quantize_hours(remaining_capacity / Decimal(period_days))
        if remaining_per_day <= low_capacity_threshold_per_day:
            return "low_capacity"
    return None


def capacity_signal_severity(signal_type: CapacitySignalType) -> Severity:
    """over_allocation -> critical (a hard, confirmed fact: promised work
    exceeds available capacity). zero_remaining_capacity -> info (the spec
    is explicit: not automatically bad, a planning signal). low_capacity ->
    warning (the one invented threshold — deliberately weaker than a
    confirmed fact, stronger than an FYI)."""
    if signal_type == "over_allocation":
        return "critical"
    if signal_type == "low_capacity":
        return "warning"
    return "info"


def scenario_risk_severity(risk_type: ScenarioRiskType) -> Severity:
    """Same mapping as capacity_signal_severity's first two tiers, applied to
    RiskRead.type, so scenario deltas and direct signals never disagree on
    what "critical" means for the same underlying fact."""
    return "critical" if risk_type == "over_allocation" else "info"


def scenario_risk_trend(
    risk_type: ScenarioRiskType, baseline_value: Decimal, scenario_value: Decimal
) -> ScenarioSignalTrend:
    """Whether an EXISTING risk (is_new=False) got worse or better between
    baseline and scenario. For over_allocation, a bigger value is worse; for
    zero_remaining_capacity, baseline_value/scenario_value are remaining
    capacity, so a SMALLER value is worse (moving toward/through zero) —
    the two risk types read this comparison in opposite directions, which
    is why the type is a required parameter rather than a bare number
    comparison at the call site."""
    if risk_type == "over_allocation":
        if scenario_value > baseline_value:
            return "worsened"
        if scenario_value < baseline_value:
            return "improved"
        return "unchanged"
    if scenario_value < baseline_value:
        return "worsened"
    if scenario_value > baseline_value:
        return "improved"
    return "unchanged"


@dataclass(frozen=True)
class ConcentrationResult:
    top_contributor_ids: tuple[uuid.UUID, ...]
    top_contributor_hours: Decimal
    total_hours: Decimal
    ratio: Decimal
    """top_contributor_hours / total_hours, quantized like utilization
    (UTILIZATION_QUANTUM) for consistent decimal-place precedent."""


def calculate_concentration(
    by_person: Sequence[ProjectPersonDemand], top_n: int = 2
) -> ConcentrationResult | None:
    """The combined share of a project's allocated hours held by its top_n
    largest contributors. top_n is fixed at 2 (matching the spec's own
    example verbatim) as a REPORTING WINDOW, not a pass/fail cutoff — this
    function always returns a result when there is something non-tautological
    to report, and never gates on a magnitude like "72% is too much" (see
    docs/adr/0005-phase-5-operational-insights.md — only LOW_CAPACITY is an
    invented threshold in this phase).

    Returns None when:
      - fewer than top_n + 1 people have allocated hours (with exactly
        top_n contributors, "top_n's share" is trivially 100% — not a
        signal, just restating the roster)
      - total_hours == 0

    top_contributor_ids sorted by hours descending, ties broken by person_id
    (str) for determinism.
    """
    contributors = [entry for entry in by_person if entry.allocated_hours > ZERO]
    if len(contributors) <= top_n:
        return None
    total_hours = sum((entry.allocated_hours for entry in contributors), ZERO)
    if total_hours <= ZERO:
        return None
    ranked = sorted(
        contributors, key=lambda entry: (-entry.allocated_hours, str(entry.person_id))
    )
    top = ranked[:top_n]
    top_hours = sum((entry.allocated_hours for entry in top), ZERO)
    return ConcentrationResult(
        top_contributor_ids=tuple(entry.person_id for entry in top),
        top_contributor_hours=top_hours,
        total_hours=total_hours,
        ratio=_quantize_utilization(top_hours / total_hours),
    )


@dataclass(frozen=True)
class ImbalanceResult:
    min_utilization: Decimal
    min_person_id: uuid.UUID
    max_utilization: Decimal
    max_person_id: uuid.UUID
    spread: Decimal


def calculate_imbalance(
    members: Sequence[tuple[uuid.UUID, Decimal | None]],
) -> ImbalanceResult | None:
    """members = (person_id, utilization) pairs, e.g. from a team's
    PersonCapacityResult list. Reports the min/max utilization across
    members with non-null utilization.

    Returns None when fewer than 2 members have non-null utilization, or
    when spread == 0 — spread > 0 is an EXISTENCE check (there is literally
    a difference to report), not a magnitude judgment about whether the
    difference is "meaningful" (no invented percentage threshold, per the
    locked decision in docs/adr/0005-phase-5-operational-insights.md).

    Ties for min/max broken by person_id (str) for determinism.
    """
    known = [
        (person_id, utilization) for person_id, utilization in members if utilization is not None
    ]
    if len(known) < 2:
        return None
    min_person_id, min_utilization = min(known, key=lambda pair: (pair[1], str(pair[0])))
    max_person_id, max_utilization = max(known, key=lambda pair: (pair[1], str(pair[0])))
    spread = max_utilization - min_utilization
    if spread <= ZERO:
        return None
    return ImbalanceResult(
        min_utilization=min_utilization,
        min_person_id=min_person_id,
        max_utilization=max_utilization,
        max_person_id=max_person_id,
        spread=_quantize_utilization(spread),
    )


__all__ = [
    "CapacitySignalType",
    "ConcentrationResult",
    "ImbalanceResult",
    "ScenarioRiskType",
    "ScenarioSignalTrend",
    "Severity",
    "calculate_concentration",
    "calculate_imbalance",
    "capacity_signal_severity",
    "classify_capacity_signal",
    "scenario_risk_severity",
    "scenario_risk_trend",
]
