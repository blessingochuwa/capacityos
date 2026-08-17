"""Provider abstraction for Phase 8's AI insight layer (CLAUDE.md §39 Phase
8). CapacityOS is never hard-coupled to one AI vendor, and the deterministic
system must keep working with no provider configured at all (spec §5/§32).

AIProvider is the one seam every implementation
(anthropic_provider.py, mock.py) sits behind — AIService and the API layer
never import an SDK directly. See docs/adr/0008-phase-8-ai-insight-layer.md.
"""

from dataclasses import dataclass
from typing import Protocol

from app.schemas.ai import AIModelOutput


@dataclass(frozen=True)
class AIGenerationRequest:
    system_instructions: str
    """The fixed instruction hierarchy (Phase 8 spec §39) — never contains
    user-supplied or imported business text."""
    context: str
    """The serialized AIInsightContext — structured, labeled application
    data only (see app/services/ai_context.py). Never a raw database dump."""
    question: str
    """A fixed per-capability instruction (e.g. "Summarize the operational
    picture for this scope.") for every capability except ask, where it is
    the user's free-text question — still never treated as an instruction
    override; see AIService's prompt assembly for the untrusted-data
    framing."""
    max_output_tokens: int


class AIProviderError(Exception):
    """Base class for provider failures. AIService always catches this and
    returns a graceful AIResponseEnvelope — never lets it propagate as a
    raw exception to the API layer (spec §23/§29)."""


class AIProviderTimeoutError(AIProviderError):
    pass


class AIProviderRateLimitedError(AIProviderError):
    pass


class AIProviderUnavailableError(AIProviderError):
    """The provider itself is unreachable or erroring (5xx, connection
    failure, authentication) — distinct from AIProviderMalformedOutputError,
    where the provider responded but its structured output didn't validate."""


class AIProviderMalformedOutputError(AIProviderError):
    """The provider's response failed schema validation."""


class AIProvider(Protocol):
    def generate(self, request: AIGenerationRequest) -> AIModelOutput: ...
