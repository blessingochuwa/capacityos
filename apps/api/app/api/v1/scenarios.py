import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.enums import ScenarioStatus
from app.models.scenario import ScenarioOperation
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.project import ProjectRepository
from app.repositories.scenario import ScenarioOperationRepository, ScenarioRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.common import Page
from app.schemas.scenario import (
    ScenarioComparisonRead,
    ScenarioCreate,
    ScenarioOperationCreate,
    ScenarioOperationRead,
    ScenarioOperationUpdate,
    ScenarioRead,
    ScenarioResultsRead,
    ScenarioUpdate,
    operation_payload_from_dict,
)
from app.services.scenario import ScenarioService
from app.services.scenario_calculation import ScenarioCalculationService

router = APIRouter(prefix="/api/v1/scenarios", tags=["scenarios"])


def get_scenario_service(db: Session = Depends(get_db)) -> ScenarioService:
    return ScenarioService(
        ScenarioRepository(db),
        ScenarioOperationRepository(db),
        PersonRepository(db),
        ProjectRepository(db),
        AllocationRepository(db),
    )


def get_scenario_calculation_service(db: Session = Depends(get_db)) -> ScenarioCalculationService:
    return ScenarioCalculationService(
        ScenarioRepository(db),
        ScenarioOperationRepository(db),
        PersonRepository(db),
        ProjectRepository(db),
        AllocationRepository(db),
        WorkingScheduleRepository(db),
        AvailabilityExceptionRepository(db),
        TeamMembershipRepository(db),
    )


def _operation_to_read(operation: ScenarioOperation) -> ScenarioOperationRead:
    return ScenarioOperationRead(
        id=operation.id,
        scenario_id=operation.scenario_id,
        operation_type=operation.operation_type,
        sequence=operation.sequence,
        payload=operation_payload_from_dict(operation.operation_type, operation.payload),
        created_at=operation.created_at,
        updated_at=operation.updated_at,
    )


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


@router.post("", response_model=ScenarioRead, status_code=status.HTTP_201_CREATED)
def create_scenario(
    data: ScenarioCreate, service: ScenarioService = Depends(get_scenario_service)
) -> ScenarioRead:
    return ScenarioRead.model_validate(service.create(data))


@router.get("", response_model=Page[ScenarioRead])
def list_scenarios(
    status_filter: ScenarioStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ScenarioService = Depends(get_scenario_service),
) -> Page[ScenarioRead]:
    items, total = service.list(status=status_filter, limit=limit, offset=offset)
    return Page[ScenarioRead](
        items=[ScenarioRead.model_validate(item) for item in items], total=total
    )


@router.get("/{scenario_id}", response_model=ScenarioRead)
def get_scenario(
    scenario_id: uuid.UUID, service: ScenarioService = Depends(get_scenario_service)
) -> ScenarioRead:
    return ScenarioRead.model_validate(service.get(scenario_id))


@router.patch("/{scenario_id}", response_model=ScenarioRead)
def update_scenario(
    scenario_id: uuid.UUID,
    data: ScenarioUpdate,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioRead:
    return ScenarioRead.model_validate(service.update(scenario_id, data))


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: uuid.UUID, service: ScenarioService = Depends(get_scenario_service)
) -> None:
    service.delete(scenario_id)


# ---------------------------------------------------------------------------
# Scenario operations
# ---------------------------------------------------------------------------


@router.post(
    "/{scenario_id}/operations",
    response_model=ScenarioOperationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_operation(
    scenario_id: uuid.UUID,
    payload: ScenarioOperationCreate,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioOperationRead:
    return _operation_to_read(service.create_operation(scenario_id, payload))


@router.get("/{scenario_id}/operations", response_model=Page[ScenarioOperationRead])
def list_operations(
    scenario_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: ScenarioService = Depends(get_scenario_service),
) -> Page[ScenarioOperationRead]:
    items, total = service.list_operations(scenario_id, limit=limit, offset=offset)
    return Page[ScenarioOperationRead](
        items=[_operation_to_read(item) for item in items], total=total
    )


@router.patch("/{scenario_id}/operations/{operation_id}", response_model=ScenarioOperationRead)
def update_operation(
    scenario_id: uuid.UUID,
    operation_id: uuid.UUID,
    payload: ScenarioOperationUpdate,
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioOperationRead:
    return _operation_to_read(service.update_operation(scenario_id, operation_id, payload))


@router.delete(
    "/{scenario_id}/operations/{operation_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_operation(
    scenario_id: uuid.UUID,
    operation_id: uuid.UUID,
    service: ScenarioService = Depends(get_scenario_service),
) -> None:
    service.delete_operation(scenario_id, operation_id)


# ---------------------------------------------------------------------------
# Calculation
# ---------------------------------------------------------------------------


@router.post("/{scenario_id}/calculate", response_model=ScenarioResultsRead)
def calculate_scenario(
    scenario_id: uuid.UUID,
    service: ScenarioCalculationService = Depends(get_scenario_calculation_service),
) -> ScenarioResultsRead:
    """Validates every stored operation still resolves against current
    baseline data and returns the same shape GET /results does — see
    docs/adr/0004-phase-4-scenario-planning.md ("no caching"). Exists as an
    explicit action so the frontend never recalculates on every keystroke
    while editing the change list (prompt §13)."""
    return service.results(scenario_id)


@router.get("/{scenario_id}/results", response_model=ScenarioResultsRead)
def get_scenario_results(
    scenario_id: uuid.UUID,
    service: ScenarioCalculationService = Depends(get_scenario_calculation_service),
) -> ScenarioResultsRead:
    return service.results(scenario_id)


@router.get("/{scenario_id}/comparison", response_model=ScenarioComparisonRead)
def get_scenario_comparison(
    scenario_id: uuid.UUID,
    service: ScenarioCalculationService = Depends(get_scenario_calculation_service),
) -> ScenarioComparisonRead:
    return service.comparison(scenario_id)
