"""CRUD and reference validation for Scenario/ScenarioOperation.

Holds no calculation logic (that's app/services/scenario_calculation.py) —
this service's job is exactly what AllocationService's is for Allocation:
existence-check references, enforce the structural business rules Pydantic
can't express alone, and persist. See docs/adr/0004-phase-4-scenario-planning.md
for the validation rules themselves.
"""

import uuid
from collections.abc import Sequence

from app.core.exceptions import DomainValidationError, NotFoundError
from app.models.allocation import Allocation
from app.models.enums import ScenarioOperationType, ScenarioStatus
from app.models.scenario import Scenario, ScenarioOperation
from app.repositories.allocation import AllocationRepository
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.scenario import ScenarioOperationRepository, ScenarioRepository
from app.schemas.scenario import (
    AddAllocationPayload,
    AdjustAllocationPayload,
    AvailabilityClearPayload,
    AvailabilityOverridePayload,
    MoveAllocationPayload,
    RemoveAllocationPayload,
    ScenarioCreate,
    ScenarioOperationPayload,
    ScenarioUpdate,
    ShiftProjectPayload,
    operation_payload_to_dict,
)


class ScenarioService:
    """Organization-scoped (Phase 12) — every method takes organization_id
    as its first argument. Critically, _check_person/_check_project/
    _check_allocation now resolve through organization-scoped repositories,
    so an operation payload referencing another organization's person,
    project, or allocation fails NotFoundError exactly like a nonexistent
    id would — a scenario can never be used to probe or pull in another
    organization's data (see docs/adr/0012-organizations-multi-tenancy.md).
    """

    def __init__(
        self,
        scenario_repository: ScenarioRepository,
        operation_repository: ScenarioOperationRepository,
        person_repository: PersonRepository,
        project_repository: ProjectRepository,
        allocation_repository: AllocationRepository,
    ) -> None:
        self.scenario_repository = scenario_repository
        self.operation_repository = operation_repository
        self.person_repository = person_repository
        self.project_repository = project_repository
        self.allocation_repository = allocation_repository

    # -- Scenario -----------------------------------------------------

    def create(self, organization_id: uuid.UUID, data: ScenarioCreate) -> Scenario:
        scenario = Scenario(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            baseline_start_date=data.baseline_start_date,
            baseline_end_date=data.baseline_end_date,
            created_by=data.created_by,
        )
        return self.scenario_repository.add(scenario)

    def get(self, organization_id: uuid.UUID, scenario_id: uuid.UUID) -> Scenario:
        scenario = self.scenario_repository.get(scenario_id, organization_id)
        if scenario is None:
            raise NotFoundError("Scenario", scenario_id)
        return scenario

    def list(
        self,
        organization_id: uuid.UUID,
        *,
        status: ScenarioStatus | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Scenario], int]:
        return self.scenario_repository.list_filtered(
            organization_id, status=status, limit=limit, offset=offset
        )

    def update(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID, data: ScenarioUpdate
    ) -> Scenario:
        scenario = self.get(organization_id, scenario_id)
        updates = data.model_dump(exclude_unset=True)

        merged_start = updates.get("baseline_start_date", scenario.baseline_start_date)
        merged_end = updates.get("baseline_end_date", scenario.baseline_end_date)
        if merged_end < merged_start:
            raise DomainValidationError("baseline_end_date cannot precede baseline_start_date")

        for field, value in updates.items():
            setattr(scenario, field, value)
        self.scenario_repository.session.flush()
        return scenario

    def delete(self, organization_id: uuid.UUID, scenario_id: uuid.UUID) -> None:
        """Deletes ONLY this scenario and its own operations (cascade via
        the FK — app/models/scenario.py) — never touches Person/Project/
        Allocation/AvailabilityException/WorkingSchedule rows, which this
        scenario may reference but never owns (prompt §29: "deleting a
        scenario should delete only the scenario")."""
        self.scenario_repository.delete(self.get(organization_id, scenario_id))

    # -- Scenario operations -------------------------------------------

    def list_operations(
        self,
        organization_id: uuid.UUID,
        scenario_id: uuid.UUID,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ScenarioOperation], int]:
        self.get(organization_id, scenario_id)
        return self.operation_repository.list_for_scenario_page(
            scenario_id, limit=limit, offset=offset
        )

    def get_operation(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID, operation_id: uuid.UUID
    ) -> ScenarioOperation:
        self.get(organization_id, scenario_id)
        operation = self.operation_repository.get_for_scenario(scenario_id, operation_id)
        if operation is None:
            raise NotFoundError("ScenarioOperation", operation_id)
        return operation

    def create_operation(
        self,
        organization_id: uuid.UUID,
        scenario_id: uuid.UUID,
        payload: ScenarioOperationPayload,
    ) -> ScenarioOperation:
        self.get(organization_id, scenario_id)
        existing = self.operation_repository.list_for_scenario(scenario_id)
        self._validate_payload(organization_id, payload, existing)

        operation = ScenarioOperation(
            scenario_id=scenario_id,
            operation_type=payload.operation_type,
            sequence=self.operation_repository.next_sequence(scenario_id),
            payload=operation_payload_to_dict(payload),
        )
        return self.operation_repository.add(operation)

    def update_operation(
        self,
        organization_id: uuid.UUID,
        scenario_id: uuid.UUID,
        operation_id: uuid.UUID,
        payload: ScenarioOperationPayload,
    ) -> ScenarioOperation:
        operation = self.get_operation(organization_id, scenario_id, operation_id)
        if payload.operation_type != operation.operation_type:
            raise DomainValidationError(
                "Cannot change an operation's type via PATCH — delete it and add a new one "
                f"({operation.operation_type} -> {payload.operation_type})"
            )
        existing = self.operation_repository.list_for_scenario(scenario_id)
        self._validate_payload(
            organization_id, payload, existing, exclude_operation_id=operation_id
        )

        operation.payload = operation_payload_to_dict(payload)
        self.operation_repository.session.flush()
        return operation

    def delete_operation(
        self, organization_id: uuid.UUID, scenario_id: uuid.UUID, operation_id: uuid.UUID
    ) -> None:
        operation = self.get_operation(organization_id, scenario_id, operation_id)
        self.operation_repository.delete(operation)

    # -- Reference validation -------------------------------------------

    def _validate_payload(
        self,
        organization_id: uuid.UUID,
        payload: ScenarioOperationPayload,
        existing_operations: Sequence[ScenarioOperation],
        *,
        exclude_operation_id: uuid.UUID | None = None,
    ) -> None:
        """Existence-checks every id a payload references, scoped to
        organization_id. Real ids are checked against the actual
        repositories; a person_id may also legitimately be a hypothetical
        resource introduced by an earlier add_hypothetical_resource
        operation in the SAME scenario (see
        app/domain/scenario.py::AddHypotheticalResourceOperation) — those
        never exist in the people table by design.
        """
        hypothetical_person_ids = {
            op.id
            for op in existing_operations
            if op.operation_type == ScenarioOperationType.ADD_HYPOTHETICAL_RESOURCE
            and op.id != exclude_operation_id
        }

        if isinstance(payload, AddAllocationPayload):
            self._check_person(organization_id, payload.person_id, hypothetical_person_ids)
            self._check_project(organization_id, payload.project_id)
        elif isinstance(payload, AdjustAllocationPayload | RemoveAllocationPayload):
            self._check_allocation(organization_id, payload.allocation_id)
        elif isinstance(payload, MoveAllocationPayload):
            allocation = self._check_allocation(organization_id, payload.allocation_id)
            self._check_person(organization_id, payload.to_person_id, hypothetical_person_ids)
            if payload.hours is not None and payload.hours > allocation.allocation_hours:
                raise DomainValidationError(
                    f"Cannot move {payload.hours}h from an allocation of "
                    f"{allocation.allocation_hours}h"
                )
        elif isinstance(payload, ShiftProjectPayload):
            self._check_project(organization_id, payload.project_id)
        elif isinstance(payload, AvailabilityOverridePayload | AvailabilityClearPayload):
            self._check_person(organization_id, payload.person_id, hypothetical_person_ids)
        # AddHypotheticalResourcePayload references nothing that exists yet.

    def _check_person(
        self, organization_id: uuid.UUID, person_id: uuid.UUID, hypothetical_ids: set[uuid.UUID]
    ) -> None:
        if person_id in hypothetical_ids:
            return
        if self.person_repository.get(person_id, organization_id) is None:
            raise NotFoundError("Person", person_id)

    def _check_project(self, organization_id: uuid.UUID, project_id: uuid.UUID) -> None:
        if self.project_repository.get(project_id, organization_id) is None:
            raise NotFoundError("Project", project_id)

    def _check_allocation(
        self, organization_id: uuid.UUID, allocation_id: uuid.UUID
    ) -> Allocation:
        allocation = self.allocation_repository.get(allocation_id, organization_id)
        if allocation is None:
            raise NotFoundError("Allocation", allocation_id)
        return allocation
