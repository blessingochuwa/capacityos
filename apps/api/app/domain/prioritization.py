"""Pure scoring functions for Phase 17 prioritization (CLAUDE.md §18).

No SQLAlchemy, no FastAPI, no I/O — same discipline as app/domain/risk.py,
app/domain/insights.py, and app/domain/skills.py. A score is always a pure
function of (framework type, criterion weights, submitted criterion
values) — never persisted, always recomputed at read time, matching
Risk.exposure's "derive, never cache" precedent (see
docs/PRD-phase-17-prioritization.md §6).

v1 supports two framework types (RICE, WEIGHTED) — see
PrioritizationFrameworkType's docstring for why the vocabulary is open but
only these two have a formula implemented so far.
"""

from dataclasses import dataclass
from decimal import Decimal

from app.core.exceptions import DomainValidationError
from app.models.enums import PrioritizationFrameworkType

RICE_CRITERION_KEYS: tuple[str, str, str, str] = ("reach", "impact", "confidence", "effort")
"""RICE's four criteria are fixed by the framework definition itself, not
organization-editable (see PRD §5.1/Open Question 3) — every RICE
framework gets exactly these four PrioritizationCriterion rows, seeded
with is_editable=False, when it is created."""


@dataclass(frozen=True)
class CriterionWeight:
    """One criterion's stable key and its scoring weight — the minimal
    shape calculate_weighted_score needs, decoupled from the ORM row
    (PrioritizationCriterion) so this module stays DB-free."""

    key: str
    weight: Decimal


@dataclass(frozen=True)
class PriorityScoreResult:
    """The complete, explainable result of scoring one project under one
    framework — "no hidden calculations" (the phase brief): every input
    that went into the score is visible in `breakdown`, and a score that
    could not be computed says exactly which criteria are missing rather
    than silently substituting a default."""

    score: Decimal | None
    """None exactly when `missing_criteria` is non-empty — a score is
    never computed from a partial input set (e.g. treating a missing
    value as zero), since that would silently understate a project's
    priority rather than surfacing that more input is needed."""

    missing_criteria: tuple[str, ...]
    breakdown: dict[str, Decimal]
    """criterion key -> submitted value, for every value that WAS
    submitted (even when the score itself is None) — this is what lets
    the Priority Explanation Panel show partial progress."""


def calculate_rice_score(values: dict[str, Decimal]) -> PriorityScoreResult:
    """(Reach x Impact x Confidence) / Effort — the standard RICE formula,
    not a CapacityOS invention. Effort must be strictly positive (division
    by zero, and a zero-effort project is not a meaningful RICE input) —
    rejected as a DomainValidationError, the same business-rule-violation
    class every other cross-field validation in this codebase already
    uses, not a new error type."""
    missing = tuple(key for key in RICE_CRITERION_KEYS if key not in values)
    breakdown = {key: values[key] for key in RICE_CRITERION_KEYS if key in values}
    if missing:
        return PriorityScoreResult(score=None, missing_criteria=missing, breakdown=breakdown)

    effort = values["effort"]
    if effort <= 0:
        raise DomainValidationError("RICE effort must be greater than zero.")

    score = (values["reach"] * values["impact"] * values["confidence"]) / effort
    return PriorityScoreResult(score=score, missing_criteria=(), breakdown=breakdown)


def calculate_weighted_score(
    criteria: list[CriterionWeight], values: dict[str, Decimal]
) -> PriorityScoreResult:
    """Sum(value x weight) across every criterion the organization defined
    for this framework — CLAUDE.md §18: no universal framework is
    prescribed, so the criteria and their weights are entirely
    organization-defined (see PrioritizationCriterion.is_editable).
    Never normalized by total weight — a score is only ever compared
    against other projects scored under the SAME framework instance, so a
    consistent (not necessarily bounded) scale is sufficient, matching the
    PRD's literal stated formula."""
    missing = tuple(c.key for c in criteria if c.key not in values)
    breakdown = {c.key: values[c.key] for c in criteria if c.key in values}
    if missing:
        return PriorityScoreResult(score=None, missing_criteria=missing, breakdown=breakdown)

    score = sum((values[c.key] * c.weight for c in criteria), start=Decimal(0))
    return PriorityScoreResult(score=score, missing_criteria=(), breakdown=breakdown)


def calculate_priority_score(
    framework_type: PrioritizationFrameworkType,
    criteria: list[CriterionWeight],
    values: dict[str, Decimal],
) -> PriorityScoreResult:
    """The single dispatch point every caller (service layer, tests) goes
    through — never an inline if/else on framework_type scattered across
    call sites, matching how has_permission is the one place a role's
    grants are decided."""
    if framework_type == PrioritizationFrameworkType.RICE:
        return calculate_rice_score(values)
    if framework_type == PrioritizationFrameworkType.WEIGHTED:
        return calculate_weighted_score(criteria, values)
    raise DomainValidationError(f"Unsupported prioritization framework type: {framework_type}")


__all__ = [
    "RICE_CRITERION_KEYS",
    "CriterionWeight",
    "PriorityScoreResult",
    "calculate_rice_score",
    "calculate_weighted_score",
    "calculate_priority_score",
]
