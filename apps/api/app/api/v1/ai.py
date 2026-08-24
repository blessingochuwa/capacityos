from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_membership, require_permission
from app.api.v1.capacity import get_capacity_service
from app.api.v1.insights import get_insight_service
from app.api.v1.scenarios import get_scenario_calculation_service
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domain.authorization import Permission
from app.integrations.ai.anthropic_provider import AnthropicAIProvider
from app.integrations.ai.base import AIProvider
from app.integrations.ai.mock import MockAIProvider
from app.models.organization_membership import OrganizationMembership
from app.models.user import User
from app.repositories.allocation import AllocationRepository
from app.repositories.availability_exception import AvailabilityExceptionRepository
from app.repositories.person import PersonRepository
from app.repositories.person_skill import PersonSkillRepository
from app.repositories.prioritization_framework import PrioritizationFrameworkRepository
from app.repositories.project import ProjectRepository
from app.repositories.project_priority_score import ProjectPriorityScoreRepository
from app.repositories.project_skill_requirement import ProjectSkillRequirementRepository
from app.repositories.skill import SkillRepository
from app.repositories.team import TeamRepository
from app.repositories.team_membership import TeamMembershipRepository
from app.repositories.working_schedule import WorkingScheduleRepository
from app.schemas.ai import (
    AIAskRequest,
    AIExplainPriorityRequest,
    AIExplainScenarioRequest,
    AIExplainSignalRequest,
    AIResponseEnvelope,
    AIStatusRead,
    AISummaryRequest,
)
from app.services.ai_context import AIContextBuilder
from app.services.ai_service import AIService
from app.services.project_priority_score import ProjectPriorityScoreService
from app.services.skill_capacity import SkillCapacityService

router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


def _build_provider(settings: Settings) -> tuple[AIProvider | None, str]:
    """None means "AI unavailable" — a first-class, expected state, never an
    error (CLAUDE.md §21/Phase 8 spec §5/§32). Only "anthropic" with a
    non-empty key constructs a real provider; anything else (including a
    misconfigured "anthropic" with no key) degrades to unavailable rather
    than raising at request time."""
    if settings.ai_provider == "anthropic" and settings.anthropic_api_key:
        return (
            AnthropicAIProvider(
                api_key=settings.anthropic_api_key,
                model=settings.ai_model,
                timeout_seconds=settings.ai_request_timeout_seconds,
            ),
            "anthropic",
        )
    if settings.ai_provider == "mock":
        return MockAIProvider(), "mock"
    return None, settings.ai_provider


def get_ai_service(
    db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> AIService:
    provider, provider_name = _build_provider(settings)
    context_builder = AIContextBuilder(
        capacity_service=get_capacity_service(db),
        insight_service=get_insight_service(db, settings),
        scenario_calculation_service=get_scenario_calculation_service(db),
        skill_capacity_service=SkillCapacityService(
            PersonSkillRepository(db),
            SkillRepository(db),
            PersonRepository(db),
            ProjectRepository(db),
            ProjectSkillRequirementRepository(db),
            TeamRepository(db),
            TeamMembershipRepository(db),
            WorkingScheduleRepository(db),
            AvailabilityExceptionRepository(db),
            AllocationRepository(db),
        ),
        priority_score_service=ProjectPriorityScoreService(
            ProjectPriorityScoreRepository(db),
            ProjectRepository(db),
            PrioritizationFrameworkRepository(db),
        ),
        person_repository=PersonRepository(db),
        team_repository=TeamRepository(db),
        project_repository=ProjectRepository(db),
    )
    return AIService(
        context_builder=context_builder,
        provider=provider,
        provider_name=provider_name,
        model_name=settings.ai_model,
        max_output_tokens=settings.ai_max_output_tokens,
    )


@router.get("/status", response_model=AIStatusRead)
def get_ai_status(
    _: User = Depends(require_permission(Permission.AI_USE)),
    service: AIService = Depends(get_ai_service),
) -> AIStatusRead:
    """Read-only capability check — no generation happens here, so the
    frontend can decide whether to show AI affordances at all without
    triggering an expensive call (spec §18: no AI call on page load)."""
    return service.status()


@router.post("/summary", response_model=AIResponseEnvelope)
def post_ai_summary(
    data: AISummaryRequest,
    _: User = Depends(require_permission(Permission.AI_USE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AIService = Depends(get_ai_service),
) -> AIResponseEnvelope:
    return service.summarize(
        membership.organization_id,
        data.scope.entity_type,
        data.scope.entity_id,
        data.start_date,
        data.end_date,
    )


@router.post("/explain-signal", response_model=AIResponseEnvelope)
def post_ai_explain_signal(
    data: AIExplainSignalRequest,
    _: User = Depends(require_permission(Permission.AI_USE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AIService = Depends(get_ai_service),
) -> AIResponseEnvelope:
    return service.explain_signal(
        membership.organization_id,
        data.scope.entity_type,
        data.scope.entity_id,
        data.signal_type,
        data.start_date,
        data.end_date,
    )


@router.post("/explain-scenario", response_model=AIResponseEnvelope)
def post_ai_explain_scenario(
    data: AIExplainScenarioRequest,
    _: User = Depends(require_permission(Permission.AI_USE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AIService = Depends(get_ai_service),
) -> AIResponseEnvelope:
    return service.explain_scenario(membership.organization_id, data.scenario_id)


@router.post("/explain-priority", response_model=AIResponseEnvelope)
def post_ai_explain_priority(
    data: AIExplainPriorityRequest,
    _: User = Depends(require_permission(Permission.AI_USE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AIService = Depends(get_ai_service),
) -> AIResponseEnvelope:
    return service.explain_priority(membership.organization_id, data.project_id, data.score_id)


@router.post("/ask", response_model=AIResponseEnvelope)
def post_ai_ask(
    data: AIAskRequest,
    _: User = Depends(require_permission(Permission.AI_USE)),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: AIService = Depends(get_ai_service),
) -> AIResponseEnvelope:
    return service.ask(
        membership.organization_id,
        data.scope.entity_type,
        data.scope.entity_id,
        data.start_date,
        data.end_date,
        data.question,
    )
