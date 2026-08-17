"""Production AIProvider backed by the Anthropic Python SDK (CLAUDE.md §39
Phase 8). Provider-specific code is isolated entirely to this module —
AIService and everything above it depend only on
app.integrations.ai.base.AIProvider (spec §7), never this SDK directly.

Uses `messages.parse(output_format=AIModelOutput)`, Anthropic's structured-
output helper, so the response is guaranteed to validate against
AIModelOutput — never a free-form string this module has to parse itself
(spec §8). See docs/adr/0008-phase-8-ai-insight-layer.md.
"""

import anthropic

from app.integrations.ai.base import (
    AIGenerationRequest,
    AIProvider,
    AIProviderMalformedOutputError,
    AIProviderRateLimitedError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.schemas.ai import AIModelOutput


class AnthropicAIProvider(AIProvider):
    def __init__(self, api_key: str, model: str, timeout_seconds: int) -> None:
        self._client = anthropic.Anthropic(api_key=api_key, timeout=float(timeout_seconds))
        self._model = model

    def generate(self, request: AIGenerationRequest) -> AIModelOutput:
        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=request.max_output_tokens,
                system=request.system_instructions,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "<application_context>\n"
                            f"{request.context}\n"
                            "</application_context>\n\n"
                            "<task>\n"
                            f"{request.question}\n"
                            "</task>"
                        ),
                    }
                ],
                output_format=AIModelOutput,
            )
        except anthropic.APITimeoutError as exc:
            raise AIProviderTimeoutError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise AIProviderRateLimitedError(str(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderUnavailableError(str(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderUnavailableError(str(exc)) from exc

        if response.stop_reason == "refusal" or response.parsed_output is None:
            raise AIProviderMalformedOutputError(
                "Provider did not return a usable structured response "
                f"(stop_reason={response.stop_reason})."
            )
        return response.parsed_output
