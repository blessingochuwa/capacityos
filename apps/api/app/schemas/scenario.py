"""Pydantic contracts for Phase 4 scenario planning.

See docs/adr/0004-phase-4-scenario-planning.md for why operation payloads
are a discriminated union rather than an unstructured JSON blob: the union
below is the ONLY way a payload is ever written to ScenarioOperation.payload
(app/models/scenario.py) — a raw dict never reaches the service or domain
layer unvalidated. operation_payload_to_dict/operation_payload_from_dict are
the two conversion points between "validated Pydantic model" and "JSON
column" and are used nowhere else.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.models.enums import ScenarioOperationType, ScenarioStatus
from app.schemas.capacity import ProjectDemandRead

# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


class ScenarioBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    baseline_start_date: date
    baseline_end_date: date
    created_by: str | None = None
    """Free text, not a user reference — CapacityOS has no authentication
    yet (CLAUDE.md §32). See app/models/scenario.py::Scenario docstring."""

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.baseline_end_date < self.baseline_start_date:
            raise ValueError("baseline_end_date cannot precede baseline_start_date")
        return self


class ScenarioCreate(ScenarioBase):
    pass


class ScenarioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: ScenarioStatus | None = None
    baseline_start_date: date | None = None
    baseline_end_date: date | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if (
            self.baseline_start_date is not None
            and self.baseline_end_date is not None
            and self.baseline_end_date < self.baseline_start_date
        ):
            raise ValueError("baseline_end_date cannot precede baseline_start_date")
        return self


class ScenarioRead(ScenarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: ScenarioStatus
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Scenario operation payloads — one Pydantic model per
# app.models.enums.ScenarioOperationType member, matching
# app.domain.scenario's operation dataclasses field-for-field (minus id/
# sequence, which are assigned server-side, not supplied by the client).
# ---------------------------------------------------------------------------


class AddAllocationPayload(BaseModel):
    operation_type: Literal[ScenarioOperationType.ADD_ALLOCATION] = (
        ScenarioOperationType.ADD_ALLOCATION
    )
    person_id: uuid.UUID
    project_id: uuid.UUID
    hours: Decimal = Field(gt=0)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class AdjustAllocationPayload(BaseModel):
    operation_type: Literal[ScenarioOperationType.ADJUST_ALLOCATION] = (
        ScenarioOperationType.ADJUST_ALLOCATION
    )
    allocation_id: uuid.UUID
    hours: Decimal | None = Field(default=None, gt=0)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _check_something_set(self) -> Self:
        if self.hours is None and self.start_date is None and self.end_date is None:
            raise ValueError(
                "adjust_allocation requires at least one of hours, start_date, end_date"
            )
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date cannot precede start_date")
        return self


class RemoveAllocationPayload(BaseModel):
    operation_type: Literal[ScenarioOperationType.REMOVE_ALLOCATION] = (
        ScenarioOperationType.REMOVE_ALLOCATION
    )
    allocation_id: uuid.UUID


class MoveAllocationPayload(BaseModel):
    operation_type: Literal[ScenarioOperationType.MOVE_ALLOCATION] = (
        ScenarioOperationType.MOVE_ALLOCATION
    )
    allocation_id: uuid.UUID
    to_person_id: uuid.UUID
    hours: Decimal | None = Field(default=None, gt=0)
    """None = move the whole allocation; a value = split (see
    app.domain.scenario.MoveAllocationOperation)."""


class ShiftProjectPayload(BaseModel):
    operation_type: Literal[ScenarioOperationType.SHIFT_PROJECT] = (
        ScenarioOperationType.SHIFT_PROJECT
    )
    project_id: uuid.UUID
    day_offset: int


class AvailabilityOverridePayload(BaseModel):
    operation_type: Literal[ScenarioOperationType.AVAILABILITY_OVERRIDE] = (
        ScenarioOperationType.AVAILABILITY_OVERRIDE
    )
    person_id: uuid.UUID
    start_date: date
    end_date: date
    hours: Decimal | None = Field(default=None, ge=0)
    """None = fully unavailable; a value = available that many hours/day."""

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class AvailabilityClearPayload(BaseModel):
    operation_type: Literal[ScenarioOperationType.AVAILABILITY_CLEAR] = (
        ScenarioOperationType.AVAILABILITY_CLEAR
    )
    person_id: uuid.UUID
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


class AddHypotheticalResourcePayload(BaseModel):
    operation_type: Literal[ScenarioOperationType.ADD_HYPOTHETICAL_RESOURCE] = (
        ScenarioOperationType.ADD_HYPOTHETICAL_RESOURCE
    )
    label: str = Field(min_length=1, max_length=200)
    hours_per_week: Decimal = Field(gt=0, le=168)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot precede start_date")
        return self


ScenarioOperationPayload = Annotated[
    AddAllocationPayload
    | AdjustAllocationPayload
    | RemoveAllocationPayload
    | MoveAllocationPayload
    | ShiftProjectPayload
    | AvailabilityOverridePayload
    | AvailabilityClearPayload
    | AddHypotheticalResourcePayload,
    Field(discriminator="operation_type"),
]

_PAYLOAD_ADAPTER: TypeAdapter[Any] = TypeAdapter(ScenarioOperationPayload)


def operation_payload_to_dict(payload: ScenarioOperationPayload) -> dict[str, Any]:
    """The ONLY place a validated payload becomes the JSON stored in
    ScenarioOperation.payload — operation_type is excluded since it already
    has its own column (app/models/scenario.py). mode="json" serializes
    Decimal/date to JSON-safe strings, avoiding float precision loss."""
    return payload.model_dump(mode="json", exclude={"operation_type"})  # type: ignore[union-attr]


def operation_payload_from_dict(
    operation_type: ScenarioOperationType, data: dict[str, Any]
) -> ScenarioOperationPayload:
    """The ONLY place JSON from the database becomes a validated payload
    again — re-injects operation_type (stored in its own column, not in the
    JSON) before validating against the full discriminated union."""
    return _PAYLOAD_ADAPTER.validate_python({**data, "operation_type": operation_type.value})


# ---------------------------------------------------------------------------
# Scenario operations — create/update accept a payload directly (client
# sends operation_type + type-specific fields); read nests the same
# validated payload alongside server-assigned identity/ordering.
# ---------------------------------------------------------------------------

ScenarioOperationCreate = ScenarioOperationPayload
ScenarioOperationUpdate = ScenarioOperationPayload
"""PATCH replaces the whole payload with a newly-validated one of the SAME
operation_type — there is no partial field update of a stored operation.
Changing what KIND of change an operation represents is delete + create,
not PATCH (see docs/adr/0004-phase-4-scenario-planning.md)."""


class ScenarioOperationRead(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID
    operation_type: ScenarioOperationType
    sequence: int
    payload: ScenarioOperationPayload
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Calculation results — baseline/scenario/delta/risks/impact always kept as
# distinct, explicit fields (CLAUDE.md §14/prompt §14), never one opaque blob.
# ---------------------------------------------------------------------------


class AggregateCapacityRead(BaseModel):
    """The same shape as TeamCapacityRead minus team_id — used for the
    scenario's affected-people aggregate, which is a real capacity total
    (computed by the unmodified aggregate_team_capacity) but not literally a
    Team. See app.domain.capacity.aggregate_team_capacity's docstring."""

    start_date: date
    end_date: date
    gross_capacity: Decimal
    unavailable_hours: Decimal
    effective_capacity: Decimal
    allocated_hours: Decimal
    remaining_capacity: Decimal
    utilization: Decimal | None
    over_allocation: Decimal


class PersonCapacitySnapshotRead(BaseModel):
    person_id: uuid.UUID
    label: str
    """Person's display_name, or a hypothetical resource's label — the
    frontend never has to know which kind of id this is to render it."""
    is_hypothetical: bool
    start_date: date
    end_date: date
    gross_capacity: Decimal
    unavailable_hours: Decimal
    effective_capacity: Decimal
    allocated_hours: Decimal
    remaining_capacity: Decimal
    utilization: Decimal | None
    over_allocation: Decimal


class ScenarioSnapshotRead(BaseModel):
    """One side (baseline or scenario) of a calculation — see
    ScenarioResultsRead. Never mixes baseline and scenario numbers in one
    object (prompt §14)."""

    aggregate: AggregateCapacityRead
    people: list[PersonCapacitySnapshotRead]
    projects: list[ProjectDemandRead]


class ScenarioResultsRead(BaseModel):
    scenario: ScenarioRead
    baseline: ScenarioSnapshotRead
    scenario_state: ScenarioSnapshotRead


class MetricDelta[T](BaseModel):
    baseline: T
    scenario: T
    delta: T
    """scenario - baseline. When T is Decimal | None and either side is
    None (no effective capacity to compute utilization from), delta is also
    None rather than a misleading 0 — see AggregateComparisonRead.utilization."""


class AggregateComparisonRead(BaseModel):
    baseline: AggregateCapacityRead
    scenario: AggregateCapacityRead
    utilization: MetricDelta[Decimal | None]
    remaining_capacity: MetricDelta[Decimal]
    over_allocation: MetricDelta[Decimal]
    over_allocated_people: MetricDelta[int]


class PersonCapacityComparisonRead(BaseModel):
    person_id: uuid.UUID
    label: str
    is_hypothetical: bool
    baseline: PersonCapacitySnapshotRead
    scenario: PersonCapacitySnapshotRead
    utilization: MetricDelta[Decimal | None]
    remaining_capacity: MetricDelta[Decimal]
    over_allocation: MetricDelta[Decimal]
    newly_over_allocated: bool
    """baseline over_allocation == 0 and scenario over_allocation > 0 — see
    docs/adr/0004-phase-4-scenario-planning.md ("new risk" vs "risk")."""


class ProjectDemandComparisonRead(BaseModel):
    project_id: uuid.UUID
    baseline: ProjectDemandRead
    scenario: ProjectDemandRead
    allocated_hours: MetricDelta[Decimal]


class RiskRead(BaseModel):
    type: Literal["over_allocation", "zero_remaining_capacity"]
    person_id: uuid.UUID
    label: str
    is_new: bool
    """True when this fact holds in the scenario but did NOT hold in the
    baseline — see PersonCapacityComparisonRead.newly_over_allocated."""
    baseline_value: Decimal
    scenario_value: Decimal


class ImpactRead(BaseModel):
    affected_people: list[uuid.UUID]
    affected_projects: list[uuid.UUID]
    affected_teams: list[uuid.UUID]
    affected_start_date: date | None
    affected_end_date: date | None
    """The min/max date span touched by any operation in the scenario —
    None only when the scenario has no operations yet."""


class ScenarioComparisonRead(BaseModel):
    scenario: ScenarioRead
    aggregate: AggregateComparisonRead
    people: list[PersonCapacityComparisonRead]
    projects: list[ProjectDemandComparisonRead]
    risks: list[RiskRead]
    impact: ImpactRead
