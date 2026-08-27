"""Pydantic contracts for Phase 8's AI insight layer (CLAUDE.md §39 Phase 8).

AIModelOutput is the exact shape requested from the model via structured
output (Anthropic's `messages.parse(output_format=AIModelOutput)`) — see
app/integrations/ai/anthropic_provider.py. AIService adds provenance
filtering and generation metadata on top of it to produce AIInsightResponse,
the shape actually returned to the frontend. See
docs/adr/0008-phase-8-ai-insight-layer.md.
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AISourceReferenceType(StrEnum):
    SIGNAL = "signal"
    CAPACITY = "capacity"
    SCENARIO = "scenario"
    SKILL_COVERAGE = "skill_coverage"
    PRIORITY_SCORE = "priority_score"
    SNAPSHOT_COMPARISON = "snapshot_comparison"
    SCENARIO_PRIORITY_COMPARISON = "scenario_priority_comparison"


class AISourceReference(BaseModel):
    type: AISourceReferenceType
    entity_id: str
    """A string, not a UUID — this field is filled in by the model from the
    ids it was shown in its context (see AIInsightContext.known_references),
    then validated against that same allow-list. Never trust it as a real
    UUID until AIService confirms the match."""
    description: str
    """A short human-readable pointer to what this reference is, e.g.
    "Backend Development skill gap on Payments Rebuild"."""


class AIConfidence(StrEnum):
    """Never a numeric probability — CLAUDE.md/Phase 8 spec §10 is explicit
    that an LLM logit is not a calibrated reliability metric. These are
    categories the model chooses to convey how directly its context
    supports a claim, not a statistic."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AIClaim(BaseModel):
    text: str
    source_references: list[AISourceReference] = []


class AIRecommendation(BaseModel):
    recommendation: str
    """Always phrased as a suggestion for the user to consider, never an
    instruction to act — enforced by the system prompt (CLAUDE.md §21/Phase
    8 spec §11), not by this schema."""
    rationale: str
    source_references: list[AISourceReference] = []
    assumptions: list[str] = []


class AIModelOutput(BaseModel):
    summary: str
    key_findings: list[AIClaim] = []
    risks: list[AIClaim] = []
    recommendations: list[AIRecommendation] = []
    confidence: AIConfidence


class AIInsightResponse(AIModelOutput):
    generated_at: datetime
    provider: str
    model: str


class AIResponseStatus(StrEnum):
    OK = "ok"
    """A response was generated and grounded successfully."""
    UNAVAILABLE = "unavailable"
    """No provider is configured (Settings.ai_provider == "none", or
    "anthropic" with no API key) — an expected, first-class state, not an
    error. HTTP 200: the deterministic system keeps working regardless."""
    ERROR = "error"
    """A provider is configured but the request failed (timeout, rate
    limit, malformed structured output). Also HTTP 200 — a soft-fail UI
    state, not an API contract violation; the caller should show the
    deterministic facts and let the user retry."""


class AIResponseEnvelope(BaseModel):
    status: AIResponseStatus
    response: AIInsightResponse | None = None
    message: str | None = None
    """Human-readable explanation for the unavailable/error states — never
    a raw provider error message or stack trace (CLAUDE.md §27)."""


class AIScope(BaseModel):
    entity_type: str = Field(pattern="^(person|team|project)$")
    entity_id: uuid.UUID


class AISummaryRequest(BaseModel):
    scope: AIScope
    start_date: date
    end_date: date


class AIExplainSignalRequest(BaseModel):
    scope: AIScope
    signal_type: str
    start_date: date
    end_date: date


class AIExplainScenarioRequest(BaseModel):
    scenario_id: uuid.UUID


class AIExplainPriorityRequest(BaseModel):
    """Addressed the same way every other ProjectPriorityScore route is
    (project_id + score_id) — see app/api/v1/prioritization.py — rather
    than by framework_id, since a project may hold at most one score per
    framework and the score itself is the concrete thing being explained."""

    project_id: uuid.UUID
    score_id: uuid.UUID


class AIExplainSnapshotComparisonRequest(BaseModel):
    """Addressed by the same (from_snapshot_id, to_snapshot_id) pair
    GET /api/v1/prioritization/snapshots/compare already takes (Phase 22)
    — the comparison being explained is the one that pair identifies,
    never a separately-stored comparison id (none exists; the comparison
    itself is never persisted, see docs/adr/0022)."""

    from_snapshot_id: uuid.UUID
    to_snapshot_id: uuid.UUID


class AIExplainScenarioPriorityComparisonRequest(BaseModel):
    """Addressed by the same (scenario_id, framework_id) pair
    GET /api/v1/scenarios/{scenario_id}/priority-comparison?framework_id=
    already takes (Phase 20) — the comparison being explained is the one
    that pair identifies, never a separately-stored comparison id (none
    exists; the comparison itself is never persisted, see
    docs/adr/0020-scenario-priority-comparison.md)."""

    scenario_id: uuid.UUID
    framework_id: uuid.UUID


class AIAskRequest(BaseModel):
    scope: AIScope
    start_date: date
    end_date: date
    question: str = Field(min_length=1, max_length=1000)


class AIStatusRead(BaseModel):
    available: bool
    provider: str
    model: str | None = None
