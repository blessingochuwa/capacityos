"""Phase 20 — scenario-vs-baseline prioritization comparison
(docs/adr/0020-scenario-priority-comparison.md). Mirrors
app/schemas/prioritization.py's conventions verbatim (CriterionValueInput
shape, category discipline) — this module only adds the scenario-scoped
override and comparison shapes, never a second scoring vocabulary.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import MoscowCategory, PrioritizationFrameworkType
from app.models.scenario_priority_override import ScenarioPriorityOverride


class ScenarioPriorityOverrideCriterionInput(BaseModel):
    criterion_key: str = Field(min_length=1, max_length=100)
    value: Decimal


class ScenarioPriorityOverrideSet(BaseModel):
    """The request body for POST .../priority-overrides — an upsert: a
    second call for the same (project_id, framework_id) pair within this
    scenario replaces the first rather than requiring a separate PATCH
    endpoint (see the ADR's "smallest slice" reasoning). `values` is a
    full replacement of this override's own criterion set (not a merge
    against a PRIOR override), but is itself only ever merged against the
    project's persisted BASELINE values at comparison time — a criterion
    this override doesn't mention still shows the project's real,
    unmodified baseline value in the scenario column, never blank."""

    project_id: uuid.UUID
    framework_id: uuid.UUID
    values: list[ScenarioPriorityOverrideCriterionInput] = Field(
        default_factory=list[ScenarioPriorityOverrideCriterionInput]
    )
    category: MoscowCategory | None = None

    @model_validator(mode="after")
    def _check_something_set(self) -> Self:
        if not self.values and self.category is None:
            raise ValueError(
                "An override must change at least one criterion value or the category."
            )
        return self


class ScenarioPriorityOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scenario_id: uuid.UUID
    project_id: uuid.UUID
    project_name: str
    framework_id: uuid.UUID
    framework_name: str
    framework_type: PrioritizationFrameworkType
    values: dict[str, Decimal]
    category: MoscowCategory | None
    created_at: datetime
    updated_at: datetime


def scenario_priority_override_to_read(
    override: ScenarioPriorityOverride,
) -> ScenarioPriorityOverrideRead:
    return ScenarioPriorityOverrideRead(
        id=override.id,
        scenario_id=override.scenario_id,
        project_id=override.project_id,
        project_name=override.project.name,
        framework_id=override.framework_id,
        framework_name=override.framework.name,
        framework_type=override.framework.framework_type,
        values={key: Decimal(value) for key, value in override.values.items()},
        category=override.category,
        created_at=override.created_at,
        updated_at=override.updated_at,
    )


class ScenarioPriorityProjectComparisonRead(BaseModel):
    """One project's baseline-vs-scenario prioritization comparison.
    `changed` is computed purely from the two computed results
    (score/category/rank) — never inferred from whether an override
    row exists, so a no-op override (one whose values happen to match
    the baseline exactly) correctly reports changed=False rather than
    inventing a change that didn't actually happen."""

    project_id: uuid.UUID
    project_name: str
    has_override: bool

    baseline_score: Decimal | None
    baseline_rank: int | None
    baseline_category: MoscowCategory | None
    baseline_missing_criteria: list[str]
    baseline_breakdown: dict[str, Decimal]

    scenario_score: Decimal | None
    scenario_rank: int | None
    scenario_category: MoscowCategory | None
    scenario_missing_criteria: list[str]
    scenario_breakdown: dict[str, Decimal]

    changed: bool


class ScenarioPriorityComparisonRead(BaseModel):
    """has_changes is true iff at least one project's `changed` is true —
    computed the same way, never guessed, so a scenario with no
    prioritization overrides (or overrides that don't actually move
    anything) explicitly reports "no prioritization change" rather than
    silently omitting the field."""

    scenario_id: uuid.UUID
    framework_id: uuid.UUID
    framework_name: str
    framework_type: PrioritizationFrameworkType
    has_changes: bool
    items: list[ScenarioPriorityProjectComparisonRead]
