"""Pure tests of the Phase 13 risk exposure/classification layer — no
database, no FastAPI (same discipline as tests/domain/test_skills.py and
tests/domain/test_insights.py).
"""

from datetime import date, timedelta

import pytest

from app.domain.risk import calculate_risk_exposure, classify_risk_signal
from app.models.enums import RiskImpact, RiskProbability, RiskStatus

TODAY = date(2026, 8, 20)
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


# ---------------------------------------------------------------------------
# calculate_risk_exposure — full 3x3 matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("probability", "impact", "expected"),
    [
        (RiskProbability.LOW, RiskImpact.LOW, "low"),
        (RiskProbability.LOW, RiskImpact.MEDIUM, "low"),
        (RiskProbability.LOW, RiskImpact.HIGH, "medium"),
        (RiskProbability.MEDIUM, RiskImpact.LOW, "low"),
        (RiskProbability.MEDIUM, RiskImpact.MEDIUM, "medium"),
        (RiskProbability.MEDIUM, RiskImpact.HIGH, "high"),
        (RiskProbability.HIGH, RiskImpact.LOW, "medium"),
        (RiskProbability.HIGH, RiskImpact.MEDIUM, "high"),
        (RiskProbability.HIGH, RiskImpact.HIGH, "high"),
    ],
)
def test_calculate_risk_exposure_matrix(
    probability: RiskProbability, impact: RiskImpact, expected: str
) -> None:
    assert calculate_risk_exposure(probability, impact) == expected


# ---------------------------------------------------------------------------
# classify_risk_signal
# ---------------------------------------------------------------------------


def test_high_exposure_open_risk_signals_high_exposure() -> None:
    assert (
        classify_risk_signal(
            exposure="high", status=RiskStatus.OPEN, review_date=None, today=TODAY
        )
        == "risk_high_exposure"
    )


def test_high_exposure_mitigating_risk_still_signals_high_exposure() -> None:
    assert (
        classify_risk_signal(
            exposure="high", status=RiskStatus.MITIGATING, review_date=None, today=TODAY
        )
        == "risk_high_exposure"
    )


def test_closed_risk_never_signals_even_at_high_exposure() -> None:
    assert (
        classify_risk_signal(
            exposure="high", status=RiskStatus.CLOSED, review_date=YESTERDAY, today=TODAY
        )
        is None
    )


def test_overdue_review_signals_when_exposure_is_not_high() -> None:
    assert (
        classify_risk_signal(
            exposure="medium", status=RiskStatus.OPEN, review_date=YESTERDAY, today=TODAY
        )
        == "risk_review_overdue"
    )


def test_high_exposure_takes_priority_over_overdue_review() -> None:
    """A risk can only ever report one signal — the more urgent fact wins."""
    assert (
        classify_risk_signal(
            exposure="high", status=RiskStatus.OPEN, review_date=YESTERDAY, today=TODAY
        )
        == "risk_high_exposure"
    )


def test_review_due_today_is_not_yet_overdue() -> None:
    assert (
        classify_risk_signal(
            exposure="low", status=RiskStatus.OPEN, review_date=TODAY, today=TODAY
        )
        is None
    )


def test_review_due_in_future_does_not_signal() -> None:
    assert (
        classify_risk_signal(
            exposure="medium", status=RiskStatus.MONITORING, review_date=TOMORROW, today=TODAY
        )
        is None
    )


def test_no_review_date_and_low_exposure_never_signals() -> None:
    assert (
        classify_risk_signal(
            exposure="low", status=RiskStatus.OPEN, review_date=None, today=TODAY
        )
        is None
    )


def test_medium_exposure_alone_does_not_signal() -> None:
    """Existence-gate, not a magnitude judgment — only "high" exposure and
    an overdue review are worth flagging, matching every other Phase 5/7
    signal's philosophy (no invented percentage/magnitude threshold)."""
    assert (
        classify_risk_signal(
            exposure="medium", status=RiskStatus.OPEN, review_date=None, today=TODAY
        )
        is None
    )
