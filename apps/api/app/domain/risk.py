"""Pure classification/derivation functions for Phase 13 risk management
(CLAUDE.md §17).

No SQLAlchemy, no FastAPI, no I/O — same discipline as app/domain/insights.py
and app/domain/skills.py. Exposure is never persisted (see Risk's model
docstring) — it is always derived here from the two stored facts
(probability, impact) via an explicit lookup table, never a multiplication
or formula, per CLAUDE.md §17: "Do not create risk scores that imply false
precision."
"""

from datetime import date
from typing import Literal

from app.models.enums import RiskImpact, RiskProbability, RiskStatus

RiskExposure = Literal["low", "medium", "high"]
RiskSignalType = Literal["risk_high_exposure", "risk_review_overdue"]

_EXPOSURE_MATRIX: dict[tuple[RiskProbability, RiskImpact], RiskExposure] = {
    (RiskProbability.LOW, RiskImpact.LOW): "low",
    (RiskProbability.LOW, RiskImpact.MEDIUM): "low",
    (RiskProbability.LOW, RiskImpact.HIGH): "medium",
    (RiskProbability.MEDIUM, RiskImpact.LOW): "low",
    (RiskProbability.MEDIUM, RiskImpact.MEDIUM): "medium",
    (RiskProbability.MEDIUM, RiskImpact.HIGH): "high",
    (RiskProbability.HIGH, RiskImpact.LOW): "medium",
    (RiskProbability.HIGH, RiskImpact.MEDIUM): "high",
    (RiskProbability.HIGH, RiskImpact.HIGH): "high",
}
"""The single place probability×impact becomes exposure — an explicit 3x3
lookup, not a multiplication, matching PROFICIENCY_RANK's explicit-table
precedent in app/domain/skills.py. Every (probability, impact) pair is
listed so a missing entry is a KeyError at test time, not a silent None."""


def calculate_risk_exposure(probability: RiskProbability, impact: RiskImpact) -> RiskExposure:
    return _EXPOSURE_MATRIX[(probability, impact)]


def classify_risk_signal(
    *,
    exposure: RiskExposure,
    status: RiskStatus,
    review_date: date | None,
    today: date,
) -> RiskSignalType | None:
    """Mutually exclusive if/elif chain — same style as
    classify_capacity_signal (app/domain/insights.py):

    1. status == CLOSED                          -> None (no longer live)
    2. exposure == "high"                        -> "risk_high_exposure"
    3. review_date is in the past                -> "risk_review_overdue"
    4. otherwise                                  -> None

    A CLOSED risk never signals regardless of exposure or a stale
    review_date — closing a risk is the explicit "this is no longer live"
    action, and a signal system that kept flagging closed risks would
    train users to ignore it (existence-gate philosophy, not a magnitude
    judgment — see docs/adr/0005-phase-5-operational-insights.md).

    High exposure takes priority over an overdue review: a risk can only
    ever report ONE signal, and an unmanaged high-exposure risk is the
    more urgent fact of the two when both are true at once.

    review_date == today is NOT yet overdue (strict `<`, matching how
    UserSession.expires_at <= now is the expiry boundary elsewhere in this
    codebase — a review due today still has today to be actioned).
    """
    if status == RiskStatus.CLOSED:
        return None
    if exposure == "high":
        return "risk_high_exposure"
    if review_date is not None and review_date < today:
        return "risk_review_overdue"
    return None


__all__ = [
    "RiskExposure",
    "RiskSignalType",
    "calculate_risk_exposure",
    "classify_risk_signal",
]
