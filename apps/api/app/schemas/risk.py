import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.risk import RiskExposure, calculate_risk_exposure
from app.models.enums import RiskImpact, RiskProbability, RiskStatus
from app.models.risk import Risk


class RiskCreate(BaseModel):
    """project_id is taken from the URL path
    (POST /projects/{project_id}/risks), not the body."""

    description: str = Field(min_length=1, max_length=2000)
    cause: str | None = Field(default=None, max_length=2000)
    potential_effect: str | None = Field(default=None, max_length=2000)
    probability: RiskProbability = RiskProbability.MEDIUM
    impact: RiskImpact = RiskImpact.MEDIUM
    response: str | None = Field(default=None, max_length=2000)
    owner_person_id: uuid.UUID | None = None
    status: RiskStatus = RiskStatus.OPEN
    review_date: date | None = None


class RiskUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    cause: str | None = Field(default=None, max_length=2000)
    potential_effect: str | None = Field(default=None, max_length=2000)
    probability: RiskProbability | None = None
    impact: RiskImpact | None = None
    response: str | None = Field(default=None, max_length=2000)
    owner_person_id: uuid.UUID | None = None
    status: RiskStatus | None = None
    review_date: date | None = None


class RiskRead(BaseModel):
    """exposure is not a Risk column (see the model's docstring) — always
    computed by risk_to_read below, never populated via from_attributes."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    description: str
    cause: str | None
    potential_effect: str | None
    probability: RiskProbability
    impact: RiskImpact
    exposure: RiskExposure
    response: str | None
    owner_person_id: uuid.UUID | None
    status: RiskStatus
    review_date: date | None
    created_at: datetime
    updated_at: datetime


def risk_to_read(risk: Risk) -> RiskRead:
    """Builds RiskRead explicitly rather than RiskRead.model_validate(risk)
    — exposure has no matching attribute on Risk (see the model's
    docstring), so from_attributes validation would fail on it; every
    other field is a direct passthrough."""
    return RiskRead(
        id=risk.id,
        project_id=risk.project_id,
        description=risk.description,
        cause=risk.cause,
        potential_effect=risk.potential_effect,
        probability=risk.probability,
        impact=risk.impact,
        exposure=calculate_risk_exposure(risk.probability, risk.impact),
        response=risk.response,
        owner_person_id=risk.owner_person_id,
        status=risk.status,
        review_date=risk.review_date,
        created_at=risk.created_at,
        updated_at=risk.updated_at,
    )
