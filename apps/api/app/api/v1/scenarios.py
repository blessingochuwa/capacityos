import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_audit_service, get_current_membership, require_csrf, require_permission
from app.core.database import get_db
from app.core.logging import request_id_var
from app.domain.authorization import Permission
from app.models.enums import AuditAction, AuditOutcome, ScenarioStatus
from app.models.organization_membership import OrganizationMembership
from app.models.scenario import ScenarioOperation
from app.models.user import User
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
from app.services.audit import AuditService
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


@router.post(
    "", response_model=ScenarioRead, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_scenario(
    data: ScenarioCreate,
    current_user: User = Depends(require_permission(Permission.SCENARIO_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioService = Depends(get_scenario_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ScenarioRead:
    scenario = service.create(membership.organization_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.SCENARIO_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="scenario",
        resource_id=str(scenario.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return ScenarioRead.model_validate(scenario)


@router.get("", response_model=Page[ScenarioRead])
def list_scenarios(
    status_filter: ScenarioStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.SCENARIO_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioService = Depends(get_scenario_service),
) -> Page[ScenarioRead]:
    items, total = service.list(
        membership.organization_id, status=status_filter, limit=limit, offset=offset
    )
    return Page[ScenarioRead](
        items=[ScenarioRead.model_validate(item) for item in items], total=total
    )


@router.get("/{scenario_id}", response_model=ScenarioRead)
def get_scenario(
    scenario_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.SCENARIO_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioService = Depends(get_scenario_service),
) -> ScenarioRead:
    return ScenarioRead.model_validate(service.get(membership.organization_id, scenario_id))


@router.patch("/{scenario_id}", response_model=ScenarioRead, dependencies=[Depends(require_csrf)])
def update_scenario(
    scenario_id: uuid.UUID,
    data: ScenarioUpdate,
    current_user: User = Depends(require_permission(Permission.SCENARIO_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioService = Depends(get_scenario_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ScenarioRead:
    scenario = service.update(membership.organization_id, scenario_id, data)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.SCENARIO_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="scenario",
        resource_id=str(scenario.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={"fields": sorted(data.model_dump(exclude_unset=True).keys())},
    )
    return ScenarioRead.model_validate(scenario)


@router.delete(
    "/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)]
)
def delete_scenario(
    scenario_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.SCENARIO_DELETE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioService = Depends(get_scenario_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete(membership.organization_id, scenario_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.SCENARIO_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="scenario",
        resource_id=str(scenario_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )


# ---------------------------------------------------------------------------
# Scenario operations
# ---------------------------------------------------------------------------


@router.post(
    "/{scenario_id}/operations",
    response_model=ScenarioOperationRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
def create_operation(
    scenario_id: uuid.UUID,
    payload: ScenarioOperationCreate,
    current_user: User = Depends(require_permission(Permission.SCENARIO_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioService = Depends(get_scenario_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ScenarioOperationRead:
    operation = service.create_operation(membership.organization_id, scenario_id, payload)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.SCENARIO_OPERATION_CREATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="scenario_operation",
        resource_id=str(operation.id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
        metadata={
            "scenario_id": str(scenario_id),
            "operation_type": operation.operation_type.value,
        },
    )
    return _operation_to_read(operation)


@router.get("/{scenario_id}/operations", response_model=Page[ScenarioOperationRead])
def list_operations(
    scenario_id: uuid.UUID,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: User = Depends(require_permission(Permission.SCENARIO_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioService = Depends(get_scenario_service),
) -> Page[ScenarioOperationRead]:
    items, total = service.list_operations(
        membership.organization_id, scenario_id, limit=limit, offset=offset
    )
    return Page[ScenarioOperationRead](
        items=[_operation_to_read(item) for item in items], total=total
    )


@router.patch(
    "/{scenario_id}/operations/{operation_id}", response_model=ScenarioOperationRead,
    dependencies=[Depends(require_csrf)],
)
def update_operation(
    scenario_id: uuid.UUID,
    operation_id: uuid.UUID,
    payload: ScenarioOperationUpdate,
    current_user: User = Depends(require_permission(Permission.SCENARIO_WRITE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioService = Depends(get_scenario_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> ScenarioOperationRead:
    operation = service.update_operation(
        membership.organization_id, scenario_id, operation_id, payload
    )
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.SCENARIO_OPERATION_UPDATE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="scenario_operation",
        resource_id=str(operation_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )
    return _operation_to_read(operation)


@router.delete(
    "/{scenario_id}/operations/{operation_id}", status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
def delete_operation(
    scenario_id: uuid.UUID,
    operation_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.SCENARIO_DELETE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioService = Depends(get_scenario_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> None:
    service.delete_operation(membership.organization_id, scenario_id, operation_id)
    audit_service.record(
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        action=AuditAction.SCENARIO_OPERATION_DELETE,
        outcome=AuditOutcome.SUCCESS,
        resource_type="scenario_operation",
        resource_id=str(operation_id),
        request_id=request_id_var.get(),
        organization_id=membership.organization_id,
    )


# ---------------------------------------------------------------------------
# Calculation — read-only (never writes a stored result, see
# docs/adr/0004-phase-4-scenario-planning.md), no audit event
# ---------------------------------------------------------------------------


@router.post("/{scenario_id}/calculate", response_model=ScenarioResultsRead)
def calculate_scenario(
    scenario_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.SCENARIO_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioCalculationService = Depends(get_scenario_calculation_service),
) -> ScenarioResultsRead:
    """Validates every stored operation still resolves against current
    baseline data and returns the same shape GET /results does — see
    docs/adr/0004-phase-4-scenario-planning.md ("no caching"). Exists as an
    explicit action so the frontend never recalculates on every keystroke
    while editing the change list (prompt §13)."""
    return service.results(membership.organization_id, scenario_id)


@router.get("/{scenario_id}/results", response_model=ScenarioResultsRead)
def get_scenario_results(
    scenario_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.SCENARIO_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioCalculationService = Depends(get_scenario_calculation_service),
) -> ScenarioResultsRead:
    return service.results(membership.organization_id, scenario_id)


@router.get("/{scenario_id}/comparison", response_model=ScenarioComparisonRead)
def get_scenario_comparison(
    scenario_id: uuid.UUID,
    _: User = Depends(require_permission(Permission.SCENARIO_READ)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: ScenarioCalculationService = Depends(get_scenario_calculation_service),
) -> ScenarioComparisonRead:
    return service.comparison(membership.organization_id, scenario_id)
