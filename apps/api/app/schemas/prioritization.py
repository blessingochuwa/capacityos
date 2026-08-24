import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.prioritization import PriorityScoreResult
from app.models.enums import MoscowCategory, PrioritizationFrameworkType, ProjectDependencyType
from app.models.prioritization_framework import PrioritizationFramework
from app.models.project_dependency import ProjectDependency
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


_FIXED_OR_EMPTY_CRITERIA_TYPES = frozenset(
    {
        PrioritizationFrameworkType.RICE,
        PrioritizationFrameworkType.ICE,
        PrioritizationFrameworkType.WSJF,
        PrioritizationFrameworkType.MOSCOW,
    }
)
"""RICE/ICE/WSJF's criteria are fixed by the methodology itself (seeded by
the service — see app/domain/prioritization.py::FIXED_CRITERION_KEYS);
MOSCOW has no criteria at all (see calculate_moscow_result's docstring).
None of the four accept a client-supplied `criteria` list at creation —
only WEIGHTED does."""


class PrioritizationFrameworkCreate(BaseModel):
    """For framework_type=WEIGHTED, `criteria` must be non-empty — a
    weighted framework with no criteria could never produce a score. For
    every other framework_type, `criteria` must be empty — RICE/ICE/WSJF's
    criteria are fixed and seeded by the service itself, and MOSCOW has
    none; supplying them here would suggest they're organization-editable,
    which they are not."""

    name: str = Field(min_length=1, max_length=200)
    framework_type: PrioritizationFrameworkType
    criteria: list[CriterionCreate] = Field(default_factory=list[CriterionCreate])

    @model_validator(mode="after")
    def _check_criteria_match_framework_type(self) -> Self:
        if self.framework_type in _FIXED_OR_EMPTY_CRITERIA_TYPES and self.criteria:
            raise ValueError(
                f"{self.framework_type.value.upper()}'s criteria are fixed by the "
                "methodology itself — do not supply criteria when creating this "
                "framework type."
            )
        if self.framework_type == PrioritizationFrameworkType.WEIGHTED and not self.criteria:
            raise ValueError("A weighted-scoring framework needs at least one criterion.")
        return self


class PrioritizationFrameworkUpdate(BaseModel):
    """Renaming/deactivating only. Editing a framework's criteria after
    creation (Phase 18) is a separate, dedicated set of endpoints — see
    CriterionCreate/CriterionUpdate below — not a bulk field on this
    schema, since RICE/ICE/WSJF/MOSCOW's non-editable criteria must never
    be reachable through a route that looks like a generic PATCH."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


class CriterionUpdate(BaseModel):
    """Rename and/or reweight ONE existing criterion (Phase 18) — only
    ever valid for a criterion with is_editable=True (a Weighted Scoring
    criterion). Attempting this against a RICE/ICE/WSJF criterion is a
    ForbiddenError at the service layer, not a missing feature."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    weight: Decimal | None = Field(default=None, gt=0)


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
    framework isn't implied by the URL the way project_id is.

    `category` (Phase 18) is the MOSCOW-only counterpart to `values` —
    exactly one of the two is meaningful for any given framework_type,
    enforced at the service layer against the linked framework's actual
    type, not here (this schema has no framework loaded yet to check
    against)."""

    framework_id: uuid.UUID
    values: list[CriterionValueInput] = Field(default_factory=list[CriterionValueInput])
    category: MoscowCategory | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ProjectPriorityScoreUpdate(BaseModel):
    """`values`, when provided, is an UPSERT per criterion_key — each
    submitted value creates or overwrites that one criterion's value; any
    criterion not mentioned keeps its previously recorded value. This
    lets a score be completed incrementally (e.g. "Reach" today,
    "Effort" once estimation is done) rather than requiring every
    criterion to be resent on every edit.

    `category` (Phase 18), when provided, replaces the score's current
    MoSCoW category outright — there's no partial-update concept for a
    single categorical value the way there is for a list of criteria."""

    values: list[CriterionValueInput] | None = None
    category: MoscowCategory | None = None
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
    category: MoscowCategory | None
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
        category=result.category,
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
    category: MoscowCategory | None = None


class PortfolioRankingRead(BaseModel):
    framework_id: uuid.UUID
    framework_name: str
    framework_type: PrioritizationFrameworkType
    items: list[PortfolioRankingEntryRead]


class ProjectDependencyCreate(BaseModel):
    """`from_project_id` is implied by the URL path
    (POST /projects/{project_id}/dependencies) — only the other side of
    the edge and its type are supplied in the body, matching
    ProjectSkillRequirement/Risk's "the URL names the owning project"
    convention."""

    to_project_id: uuid.UUID
    dependency_type: ProjectDependencyType


class ProjectDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_project_id: uuid.UUID
    from_project_name: str
    to_project_id: uuid.UUID
    to_project_name: str
    dependency_type: ProjectDependencyType
    created_at: datetime


def project_dependency_to_read(dependency: ProjectDependency) -> ProjectDependencyRead:
    return ProjectDependencyRead(
        id=dependency.id,
        from_project_id=dependency.from_project_id,
        from_project_name=dependency.from_project.name,
        to_project_id=dependency.to_project_id,
        to_project_name=dependency.to_project.name,
        dependency_type=dependency.dependency_type,
        created_at=dependency.created_at,
    )


class DependencyGraphNodeRead(BaseModel):
    """One project as it appears in the organization's dependency graph —
    only the projects that actually participate in at least one edge are
    included (see the service's graph-building logic), not every project
    in the organization."""

    project_id: uuid.UUID
    project_name: str


class DependencyGraphRead(BaseModel):
    """The organization's full dependency graph, flattened to nodes+edges
    for a frontend graph view to render directly — no server-side layout
    is computed, matching CLAUDE.md §29's "no decorative charts" and
    "reuse existing chart tooling" (this isn't a chart at all, just a
    node/edge list)."""

    nodes: list[DependencyGraphNodeRead]
    edges: list[ProjectDependencyRead]
