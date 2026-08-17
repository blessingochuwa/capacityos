"""A deterministic, non-LLM AIProvider (CLAUDE.md §39 Phase 8 spec §5).

Used by the backend test suite (no test ever makes a real network call to an
AI provider) and, when explicitly configured via Settings.ai_provider ==
"mock", for local development/demos without an API key. Never used in
production — see docs/adr/0008-phase-8-ai-insight-layer.md.

This is not "fake AI dressed up as real" (CLAUDE.md §26/Phase 8 spec §33):
every response is clearly labeled by AIService's provider="mock" metadata
field, and the frontend is expected to treat it identically to any other
provider's output — grounded only in what AIService actually put in the
request's context, never inventing a fact the context didn't contain.
"""

from app.integrations.ai.base import AIGenerationRequest, AIProvider
from app.schemas.ai import AIClaim, AIConfidence, AIModelOutput, AIRecommendation


class MockAIProvider(AIProvider):
    """Derives a small, deterministic response from simple markers already
    present in the (already-grounded) context text AIService assembled —
    never invents a fact the context doesn't contain."""

    def generate(self, request: AIGenerationRequest) -> AIModelOutput:
        context = request.context
        findings: list[AIClaim] = []
        risks: list[AIClaim] = []
        recommendations: list[AIRecommendation] = []

        if "type=skill_gap" in context:
            findings.append(
                AIClaim(
                    text="A skill requirement has a qualified-capacity gap.",
                    source_references=[],
                )
            )
            recommendations.append(
                AIRecommendation(
                    recommendation=(
                        "Consider reviewing whether additional qualified capacity for "
                        "this skill can be found before committing to the affected work."
                    ),
                    rationale="The context includes a skill_gap signal for this scope.",
                    assumptions=["Mock provider — not a real AI-generated recommendation."],
                )
            )
        if "type=over_allocation" in context:
            risks.append(
                AIClaim(
                    text="At least one person or team is over-allocated in this period.",
                    source_references=[],
                )
            )
        if "type=single_skill_holder" in context:
            risks.append(
                AIClaim(
                    text="A required skill currently has only one qualified holder.",
                    source_references=[],
                )
            )
        if "type=scenario_new_risk" in context:
            risks.append(
                AIClaim(
                    text=(
                        "This scenario introduces a new capacity risk not "
                        "present in the baseline."
                    ),
                    source_references=[],
                )
            )
        if "type=scenario_existing_risk" in context:
            risks.append(
                AIClaim(
                    text="An existing capacity risk changes under this scenario.",
                    source_references=[],
                )
            )

        if not findings and not risks:
            summary = "No material capacity risk is currently detected for this scope."
            confidence = AIConfidence.HIGH
        else:
            summary = (
                "This scope has one or more active capacity or skill signals worth "
                "reviewing — see the findings and risks below."
            )
            confidence = AIConfidence.MEDIUM

        return AIModelOutput(
            summary=summary,
            key_findings=findings,
            risks=risks,
            recommendations=recommendations,
            confidence=confidence,
        )
