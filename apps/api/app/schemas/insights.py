"""Pydantic contracts for Phase 5 operational insights (CLAUDE.md §39 Phase
5). See docs/adr/0005-phase-5-operational-insights.md for the design
rationale.

SignalRead is one flat model — not a discriminated union like
ScenarioOperationPayload (app/schemas/scenario.py). That union exists
because payloads are *executed* by type-specific code
(apply_scenario_operations dispatches per operation_type); signals are only
ever *displayed* in a uniform list, so a union would only cost the frontend
extra type-narrowing for no behavioral benefit. Every field beyond the
common core is nullable and populated only for the signal types documented
on the field itself.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.schemas.scenario import AggregateCapacityRead, AggregateComparisonRead

SignalType = Literal[
    "over_allocation",
    "zero_remaining_capacity",
    "low_capacity",
    "concentration_risk",
    "capacity_imbalance",
    "project_capacity_pressure",
    "scenario_new_risk",
    "scenario_existing_risk",
]
Severity = Literal["critical", "warning", "info"]
EntityType = Literal["person", "team", "project"]


class SignalRead(BaseModel):
    type: SignalType
    severity: Severity
    entity_type: EntityType
    entity_id: uuid.UUID
    entity_label: str
    start_date: date
    end_date: date
    explanation: str
    """A complete, human-readable sentence built server-side — the frontend
    renders this verbatim and never reconstructs it from the numeric fields
    below."""

    # Populated for over_allocation / zero_remaining_capacity / low_capacity
    # / project_capacity_pressure (person, team, or project-aggregate scope):
    effective_capacity: Decimal | None = None
    allocated_hours: Decimal | None = None
    remaining_capacity: Decimal | None = None
    excess_hours: Decimal | None = None
    """== over_allocation; only set when type == "over_allocation" or
    type == "project_capacity_pressure" with an over-allocated aggregate."""
    utilization: Decimal | None = None
    threshold_hours_per_day: Decimal | None = None
    """Only set when type == "low_capacity" — the configured threshold this
    signal crossed, so the frontend never has to know the current server
    config to explain why the signal fired."""

    # Populated only for type == "concentration_risk":
    concentration_ratio: Decimal | None = None
    concentration_person_ids: list[uuid.UUID] | None = None
    concentration_person_labels: list[str] | None = None

    # Populated only for type == "capacity_imbalance":
    min_utilization: Decimal | None = None
    min_utilization_person_id: uuid.UUID | None = None
    min_utilization_person_label: str | None = None
    max_utilization: Decimal | None = None
    max_utilization_person_id: uuid.UUID | None = None
    max_utilization_person_label: str | None = None

    # Populated for project_capacity_pressure / concentration_risk:
    affected_person_ids: list[uuid.UUID] = []

    # Populated only for type == "scenario_new_risk" / "scenario_existing_risk":
    scenario_id: uuid.UUID | None = None
    is_new: bool | None = None
    trend: Literal["worsened", "improved", "unchanged"] | None = None
    """Only meaningful (non-None) for scenario_existing_risk — a brand new
    risk has no prior baseline value to trend against."""
    baseline_value: Decimal | None = None
    scenario_value: Decimal | None = None


class SeverityCounts(BaseModel):
    critical: int
    warning: int
    info: int


class UtilizationPoint(BaseModel):
    person_id: uuid.UUID
    label: str
    utilization: Decimal | None


class ConcentrationAreaRead(BaseModel):
    project_id: uuid.UUID
    project_label: str
    ratio: Decimal
    top_contributor_ids: list[uuid.UUID]
    top_contributor_labels: list[str]


class ProjectPressureRead(BaseModel):
    project_id: uuid.UUID
    project_label: str
    severity: Severity
    demand_hours: Decimal
    available_capacity: Decimal
    remaining_capacity: Decimal


class InsightsSummaryRead(BaseModel):
    team_id: uuid.UUID
    team_label: str
    start_date: date
    end_date: date
    capacity: AggregateCapacityRead
    signal_counts: SeverityCounts
    utilization_distribution: list[UtilizationPoint]
    """Every team member, sorted by utilization descending (nulls last).
    Highest/lowest-N is a frontend array-slice concern, not a second
    invented cutoff on the backend."""
    concentration_areas: list[ConcentrationAreaRead]
    projects_under_pressure: list[ProjectPressureRead]
    scenario_id: uuid.UUID | None = None
    scenario_delta: AggregateComparisonRead | None = None
    scenario_new_risk_count: int = 0
    scenario_existing_risk_count: int = 0
