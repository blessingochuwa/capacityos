"""Pure scoring functions for Phase 17/18 prioritization (CLAUDE.md §18).

No SQLAlchemy, no FastAPI, no I/O — same discipline as app/domain/risk.py,
app/domain/insights.py, and app/domain/skills.py. A score is always a pure
function of (framework type, criterion weights, submitted criterion
values) — never persisted, always recomputed at read time, matching
Risk.exposure's "derive, never cache" precedent (see
docs/PRD-phase-17-prioritization.md §6).

Phase 18 completes the framework set CLAUDE.md §18 names: RICE, ICE, WSJF,
Weighted Scoring, and MoSCoW. MoSCoW is deliberately NOT a numeric formula
at all — see calculate_moscow_result's docstring — matching CLAUDE.md
§17's "do not create scores that imply false precision," generalized here
exactly as Risk/Stakeholder already applied it.

Phase 18 also adds dependency-graph cycle detection (detects_cycle) — a
second, unrelated pure-function concern that happens to live in this
module because docs/PRD-phase-17-prioritization.md §7 scoped the
dependency graph as part of the Prioritization feature area, not because
it shares any formula logic with scoring.

Phase 20 adds rank_priority_results — the single ranking rule every
portfolio/comparison view in this codebase must use (extracted from
ProjectPriorityScoreService.rank_portfolio, which now calls this
function instead of sorting inline), so a project's rank can never
disagree between the live portfolio board and the new scenario-vs-
baseline comparison (docs/adr/0020-scenario-priority-comparison.md).
"""

from dataclasses import dataclass
from decimal import Decimal

from app.core.exceptions import DomainValidationError
from app.models.enums import MoscowCategory, PrioritizationFrameworkType

RICE_CRITERION_KEYS: tuple[str, str, str, str] = ("reach", "impact", "confidence", "effort")
"""RICE's four criteria are fixed by the framework definition itself, not
organization-editable (see PRD §5.1/Open Question 3) — every RICE
framework gets exactly these four PrioritizationCriterion rows, seeded
with is_editable=False, when it is created."""

ICE_CRITERION_KEYS: tuple[str, str, str] = ("impact", "confidence", "ease")
"""ICE's three criteria, fixed the same way RICE's are (Phase 18)."""

WSJF_CRITERION_KEYS: tuple[str, str, str, str] = (
    "business_value",
    "time_criticality",
    "risk_reduction_opportunity_enablement",
    "job_size",
)
"""WSJF's four criteria (Phase 18) — "Risk Reduction / Opportunity
Enablement" is SAFe's own single combined criterion, not two separate
ones CapacityOS split apart; splitting it would be inventing structure
the standard framework doesn't have."""

FIXED_CRITERION_KEYS: dict[PrioritizationFrameworkType, tuple[str, ...]] = {
    PrioritizationFrameworkType.RICE: RICE_CRITERION_KEYS,
    PrioritizationFrameworkType.ICE: ICE_CRITERION_KEYS,
    PrioritizationFrameworkType.WSJF: WSJF_CRITERION_KEYS,
}
"""The three framework types whose criteria are fixed-by-definition and
seeded automatically (app/services/prioritization_framework.py) — RICE,
ICE, and WSJF each name their own criteria verbatim in the established
methodology; only WEIGHTED lets an organization define its own, and
MOSCOW defines none at all (see calculate_moscow_result)."""


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
    """None exactly when `missing_criteria` is non-empty, OR when the
    framework is MOSCOW (which never produces a number at all — see
    `category` below). A score is never computed from a partial input
    set (e.g. treating a missing value as zero), since that would
    silently understate a project's priority rather than surfacing that
    more input is needed."""

    missing_criteria: tuple[str, ...]
    breakdown: dict[str, Decimal]
    """criterion key -> submitted value, for every value that WAS
    submitted (even when the score itself is None) — this is what lets
    the Priority Explanation Panel show partial progress. Always empty
    for MOSCOW, which has no criteria at all."""

    category: MoscowCategory | None = None
    """Populated only for a MOSCOW-framework score — see
    calculate_moscow_result. None for every other framework type."""


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


def calculate_ice_score(values: dict[str, Decimal]) -> PriorityScoreResult:
    """(Impact + Confidence + Ease) / 3 — the standard growth-hacking ICE
    average (Impact/Confidence/Ease each typically scored 1-10). Chosen
    over a product (Impact x Confidence x Ease) because the average is the
    more common convention for ICE specifically — unlike RICE, which is
    always a product by definition. Documented explicitly since ICE's
    exact combination rule is less universally fixed than RICE's or
    WSJF's (see docs/adr/0018-prioritization-frameworks-and-dependencies.md)."""
    missing = tuple(key for key in ICE_CRITERION_KEYS if key not in values)
    breakdown = {key: values[key] for key in ICE_CRITERION_KEYS if key in values}
    if missing:
        return PriorityScoreResult(score=None, missing_criteria=missing, breakdown=breakdown)

    score = (values["impact"] + values["confidence"] + values["ease"]) / Decimal(3)
    return PriorityScoreResult(score=score, missing_criteria=(), breakdown=breakdown)


def calculate_wsjf_score(values: dict[str, Decimal]) -> PriorityScoreResult:
    """(Business Value + Time Criticality + Risk Reduction/Opportunity
    Enablement) / Job Size — SAFe's own WSJF formula (Cost of Delay /
    Job Size, where Cost of Delay is itself the sum of the first three
    criteria). Job Size must be strictly positive, the same
    division-by-zero/meaningless-zero-size reasoning as RICE's Effort."""
    missing = tuple(key for key in WSJF_CRITERION_KEYS if key not in values)
    breakdown = {key: values[key] for key in WSJF_CRITERION_KEYS if key in values}
    if missing:
        return PriorityScoreResult(score=None, missing_criteria=missing, breakdown=breakdown)

    job_size = values["job_size"]
    if job_size <= 0:
        raise DomainValidationError("WSJF job size must be greater than zero.")

    cost_of_delay = (
        values["business_value"]
        + values["time_criticality"]
        + values["risk_reduction_opportunity_enablement"]
    )
    score = cost_of_delay / job_size
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


def calculate_moscow_result(category: MoscowCategory | None) -> PriorityScoreResult:
    """MoSCoW is deliberately categorical, never numeric — CLAUDE.md §17's
    "do not create scores that imply false precision" applies here exactly
    as it does to Risk: forcing Must/Should/Could/Won't onto an invented
    numeric scale (e.g. "Must=4, Should=3...") would be exactly the false
    precision that rule forbids. A MOSCOW-framework score has no criteria
    at all (PrioritizationFramework.criteria is empty for framework_type=
    MOSCOW — see the service's seeding logic) — its only input is the
    category itself, so `missing_criteria`/`breakdown` are always empty
    here; "missing" for MoSCoW means category is None, surfaced by the
    caller checking `result.category is None`, not by this function
    inventing a synthetic missing-criteria entry for a criterion that was
    never defined."""
    return PriorityScoreResult(score=None, missing_criteria=(), breakdown={}, category=category)


def calculate_priority_score(
    framework_type: PrioritizationFrameworkType,
    criteria: list[CriterionWeight],
    values: dict[str, Decimal],
    *,
    category: MoscowCategory | None = None,
) -> PriorityScoreResult:
    """The single dispatch point every caller (service layer, tests) goes
    through — never an inline if/else on framework_type scattered across
    call sites, matching how has_permission is the one place a role's
    grants are decided."""
    if framework_type == PrioritizationFrameworkType.RICE:
        return calculate_rice_score(values)
    if framework_type == PrioritizationFrameworkType.ICE:
        return calculate_ice_score(values)
    if framework_type == PrioritizationFrameworkType.WSJF:
        return calculate_wsjf_score(values)
    if framework_type == PrioritizationFrameworkType.WEIGHTED:
        return calculate_weighted_score(criteria, values)
    if framework_type == PrioritizationFrameworkType.MOSCOW:
        return calculate_moscow_result(category)
    raise DomainValidationError(f"Unsupported prioritization framework type: {framework_type}")


def detects_cycle(
    existing_edges: list[tuple[str, str]], new_edge: tuple[str, str]
) -> bool:
    """True if adding `new_edge` (from, to) to the existing set of
    `blocks` edges would create a directed cycle — a DFS reachability
    check from the new edge's `to` node back to its `from` node (if `to`
    can already reach `from` through existing edges, adding `from -> to`
    closes a cycle). IDs are passed as plain strings (not uuid.UUID) so
    this stays a trivial, dependency-free graph algorithm independent of
    how the caller represents an id.

    Only `blocks` edges are checked — `related`/`enables` don't imply a
    strict ordering the way `blocks` does (see ProjectDependencyType's
    docstring), so a graph mixing all three edge types isn't meaningful
    to cycle-check; the caller passes only `blocks` edges in."""
    from_id, to_id = new_edge
    if from_id == to_id:
        return True  # a self-edge is a trivial 1-node cycle

    adjacency: dict[str, list[str]] = {}
    for edge_from, edge_to in existing_edges:
        adjacency.setdefault(edge_from, []).append(edge_to)

    visited: set[str] = set()
    stack = [to_id]
    while stack:
        node = stack.pop()
        if node == from_id:
            return True
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency.get(node, []))
    return False


def validate_category_for_framework_type(
    framework_type: PrioritizationFrameworkType, category: MoscowCategory | None
) -> None:
    """`category` is only ever meaningful for a MOSCOW framework — see
    calculate_moscow_result's docstring. Supplying it against any other
    framework_type is rejected rather than silently ignored, since a
    caller who set it clearly expected it to matter. Shared by
    ProjectPriorityScoreService (a persisted score's category) and, since
    Phase 20, ScenarioPriorityService (a scenario override's hypothetical
    category) — the same rule, not a second copy of it."""
    if category is not None and framework_type != PrioritizationFrameworkType.MOSCOW:
        raise DomainValidationError(
            f"'category' is only meaningful for a MOSCOW framework, not "
            f"{framework_type.value.upper()}."
        )


def rank_priority_results[K](
    entries: list[tuple[K, PriorityScoreResult]],
) -> list[tuple[K, PriorityScoreResult, int | None]]:
    """Sorts by score descending — a result with no score (missing
    criteria, OR a MOSCOW result, which never has one at all — see
    calculate_moscow_result's docstring) is ranked last, unranked
    (rank=None), never sorted as if a missing/categorical input were the
    lowest possible number. `entries` may carry any caller-chosen key
    (a project id, or a (project id, "baseline"/"scenario") pair) — this
    function only ever looks at the PriorityScoreResult half of each
    entry, so it is exactly as valid for ranking a scenario's hypothetical
    results as it is for the live portfolio board."""
    ordered = sorted(
        entries, key=lambda entry: (entry[1].score is None, -(entry[1].score or Decimal(0)))
    )
    return [
        (key, result, rank if result.score is not None else None)
        for rank, (key, result) in enumerate(ordered, start=1)
    ]


__all__ = [
    "FIXED_CRITERION_KEYS",
    "ICE_CRITERION_KEYS",
    "RICE_CRITERION_KEYS",
    "WSJF_CRITERION_KEYS",
    "CriterionWeight",
    "PriorityScoreResult",
    "calculate_ice_score",
    "calculate_moscow_result",
    "calculate_priority_score",
    "calculate_rice_score",
    "calculate_weighted_score",
    "calculate_wsjf_score",
    "detects_cycle",
    "rank_priority_results",
    "validate_category_for_framework_type",
]
