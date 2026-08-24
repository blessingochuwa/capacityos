import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.prioritization import PriorityScoreResult
from app.models.enums import PrioritizationFrameworkType
from app.models.prioritization_framework import PrioritizationFramework
from app.models.project_priority_score import ProjectPriorityScore

_KEY_PATTERN = re.compile(r"[^a-z0-9]+")


def slugify_criterion_key(name: str) -> str:
    """Derives a stable machine key from a Weighted Scoring criterion's
    display name (e.g. "Business Value" -> "business_value") — RICE's
    criteria never go through this, they use the fixed keys in
    RICE_CRITERION_KEYS."""
    return _KEY_PATTERN.sub("_", name.strip().lower()).strip("_")


class CriterionCreate(BaseModel):
    """Only meaningful for a Weighted Scoring framework — RICE's four
    criteria are seeded automatically by the service and must never be
    supplied here (see PrioritizationFrameworkCreate's docstring)."""

    name: str = Field(min_length=1, max_length=200)
    weight: Decimal = Field(gt=0)


class PrioritizationFrameworkCreate(BaseModel):
    """For framework_type=WEIGHTED, `criteria` must be non-empty — a
    weighted framework with no criteria could never produce a score. For
    framework_type=RICE, `criteria` must be empty — RICE's four criteria
    are fixed and seeded by the service itself (see
    app/domain/prioritization.py::RICE_CRITERION_KEYS); supplying them
    here would suggest they're organization-editable, which they are
    not."""

    name: str = Field(min_length=1, max_length=200)
    framework_type: PrioritizationFrameworkType
    criteria: list[CriterionCreate] = Field(default_factory=list[CriterionCreate])

    @model_validator(mode="after")
    def _check_criteria_match_framework_type(self) -> Self:
        if self.framework_type == PrioritizationFrameworkType.RICE and self.criteria:
            raise ValueError(
                "RICE's criteria are fixed (Reach, Impact, Confidence, Effort) — "
                "do not supply criteria when creating a RICE framework."
            )
        if self.framework_type == PrioritizationFrameworkType.WEIGHTED and not self.criteria:
            raise ValueError("A weighted-scoring framework needs at least one criterion.")
        return self


class PrioritizationFrameworkUpdate(BaseModel):
    """Renaming/deactivating only — v1 does not support editing a
    framework's criteria after creation (see
    docs/PRD-phase-17-prioritization.md's "Recommended v1 slice"): a
    mis-defined Weighted Scoring framework is deactivated and recreated
    rather than edited in place. Deferred, not forgotten — see ADR 0017's
    Consequences."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class CriterionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    name: str
    weight: Decimal | None
    is_editable: bool
    sequence: int


class PrioritizationFrameworkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    framework_type: PrioritizationFrameworkType
    is_active: bool
    criteria: list[CriterionRead]
    created_at: datetime
    updated_at: datetime


def framework_to_read(framework: PrioritizationFramework) -> PrioritizationFrameworkRead:
    return PrioritizationFrameworkRead(
        id=framework.id,
        organization_id=framework.organization_id,
        name=framework.name,
        framework_type=framework.framework_type,
        is_active=framework.is_active,
        criteria=[CriterionRead.model_validate(c) for c in framework.criteria],
        created_at=framework.created_at,
        updated_at=framework.updated_at,
    )


class CriterionValueInput(BaseModel):
    criterion_key: str = Field(min_length=1, max_length=100)
    value: Decimal


class ProjectPriorityScoreCreate(BaseModel):
    """framework_id is in the body (not the path) — a project can be
    scored under any of the organization's active frameworks, so the
    framework isn't implied by the URL the way project_id is."""

    framework_id: uuid.UUID
    values: list[CriterionValueInput] = Field(default_factory=list[CriterionValueInput])
    notes: str | None = Field(default=None, max_length=2000)


class ProjectPriorityScoreUpdate(BaseModel):
    """`values`, when provided, is an UPSERT per criterion_key — each
    submitted value creates or overwrites that one criterion's value; any
    criterion not mentioned keeps its previously recorded value. This
    lets a score be completed incrementally (e.g. "Reach" today,
    "Effort" once estimation is done) rather than requiring every
    criterion to be resent on every edit."""

    values: list[CriterionValueInput] | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ProjectPriorityScoreRead(BaseModel):
    """score/missing_criteria/breakdown are never stored columns — see
    ProjectPriorityScore's model docstring. Built by
    project_priority_score_to_read below, never
    ProjectPriorityScoreRead.model_validate(score) directly, the same
    reason RiskRead's exposure field is built explicitly."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    framework_id: uuid.UUID
    framework_name: str
    framework_type: PrioritizationFrameworkType
    score: Decimal | None
    missing_criteria: list[str]
    breakdown: dict[str, Decimal]
    notes: str | None
    created_at: datetime
    updated_at: datetime


def project_priority_score_to_read(
    score: ProjectPriorityScore, result: PriorityScoreResult
) -> ProjectPriorityScoreRead:
    return ProjectPriorityScoreRead(
        id=score.id,
        project_id=score.project_id,
        framework_id=score.framework_id,
        framework_name=score.framework.name,
        framework_type=score.framework.framework_type,
        score=result.score,
        missing_criteria=list(result.missing_criteria),
        breakdown=result.breakdown,
        notes=score.notes,
        created_at=score.created_at,
        updated_at=score.updated_at,
    )


class PortfolioRankingEntryRead(BaseModel):
    """One project's position in a portfolio ranking. `rank` is None
    exactly when `score` is None (an incomplete score can't be ranked
    against complete ones — it's listed, unranked, rather than silently
    sorted as if it were zero)."""

    project_id: uuid.UUID
    project_name: str
    score: Decimal | None
    rank: int | None
    missing_criteria: list[str]
    breakdown: dict[str, Decimal]


class PortfolioRankingRead(BaseModel):
    framework_id: uuid.UUID
    framework_name: str
    framework_type: PrioritizationFrameworkType
    items: list[PortfolioRankingEntryRead]
