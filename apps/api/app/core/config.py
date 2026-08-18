from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../.env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    """Explicit deployment environment — defaults to "development" so an
    unconfigured checkout never silently behaves as production. Drives only
    validate_production_config below (a startup-time safety gate, called
    from main.py's lifespan); nothing else in the app branches on this
    value. See docs/adr/0009-phase-9-production-readiness.md."""

    log_level: str = "INFO"
    """Standard Python logging level name. See app/core/logging.py."""

    max_request_body_bytes: int = 5 * 1024 * 1024
    """Hard cap on every request body this API accepts, enforced by
    MaxBodySizeMiddleware (app/api/middleware.py) before any body is read.
    Matches import_max_file_size_bytes by default — the import endpoints are
    this app's one legitimately large body, so the general ceiling is set to
    that same size rather than special-casing import routes; ImportService's
    own check still runs afterward and gives a more specific, actionable
    Level-1 error for an oversized import file."""

    database_url: str = "sqlite:///./capacityos.db"
    api_cors_origins: str = "http://localhost:5173"
    low_capacity_threshold_hours_per_day: Decimal = Decimal("1.00")
    """The one backend-owned, service-layer-configurable threshold in
    CapacityOS — a deliberate, single-signal reversal of ADR 0004's
    "at-capacity thresholds stay frontend-only" stance (see
    docs/adr/0005-phase-5-operational-insights.md). Expressed as hours PER
    DAY, not a flat period total, so it means the same thing whether the
    queried range is one day or MAX_RANGE_DAYS long: "less than this many
    hours of slack per working day, on average, across the period." Compared
    against remaining_capacity / period_days in
    app.domain.insights.classify_capacity_signal — never against
    remaining_capacity directly."""

    import_max_file_size_bytes: int = 5 * 1024 * 1024
    """Hard cap on an uploaded import file's size (5 MiB), checked before
    any parsing is attempted (Level 1) — a request-scoped bound so a client
    can't force the API to buffer/parse an unbounded upload (CLAUDE.md
    §26/§27). Comfortably fits several thousand CSV rows of any of the
    7 importable entity shapes; a genuinely larger import is expected to be
    split by the client into multiple files."""

    import_max_rows: int = 5000
    """Hard cap on the number of data rows (header excluded) a single
    validate/apply request will process — checked after parsing, before any
    per-row work, so an oversized file is rejected with one clear Level-1
    error rather than a huge, slow-to-render row-error report."""

    export_max_rows: int = 5000
    """Hard cap on the number of rows a single export response will
    return — enforced as an explicit 422 (see ExportService), never silent
    truncation, so a client can never mistake a truncated export for a
    complete one."""

    ai_provider: str = "none"
    """"anthropic" | "mock" | "none" (default). CapacityOS's deterministic
    functionality never depends on this — with "none", AI endpoints report
    themselves as unavailable rather than erroring (CLAUDE.md §21/Phase 8
    spec §32: the app must remain fully usable with no AI provider
    configured). "mock" wires in a deterministic, non-LLM provider for
    local development/demos — never used in production. See
    docs/adr/0008-phase-8-ai-insight-layer.md."""

    anthropic_api_key: str | None = None
    """Server-side only — never exposed to apps/web. A CLAUDE.md-application
    API key, distinct from any Claude Code development credential (Phase 8
    spec §6)."""

    ai_model: str = "claude-sonnet-5"
    """Configurable rather than hard-coded so the operator can trade off
    cost/quality without a code change."""

    ai_max_output_tokens: int = 2048
    """A structured operational summary is a bounded, small response — this
    caps cost/latency per request (CLAUDE.md §18)."""

    ai_request_timeout_seconds: int = 30
    """AI generation is explicitly user-triggered (never on page load), so a
    bounded timeout with a clear failure state is preferable to a long hang."""

    session_ttl_hours: int = 24
    """Fixed absolute session lifetime from login — deliberately no silent
    sliding renewal (docs/adr/0010-authentication-rbac-audit.md). A stolen-
    but-unused session token still expires; re-login is required after this
    many hours regardless of activity."""

    session_cookie_name: str = "capacityos_session"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]

    @property
    def session_cookie_secure(self) -> bool:
        """Deliberately NOT a settable field — deriving this from
        `environment` means there is no insecure-by-omission default an
        operator could forget to flip for a production deployment (unlike
        every other production risk in validate_production_config below,
        which requires an operator to have left something unconfigured)."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


class ProductionConfigError(Exception):
    """Raised by main.py's startup lifespan when environment == "production"
    and validate_production_config finds an unsafe default still in effect.
    A pure, testable check — never raised for "development"/"test", where
    SQLite, the mock AI provider, and a permissive CORS list are all
    intentional, documented defaults (CLAUDE.md §7/docs/adr/0008)."""


def validate_production_config(settings: Settings) -> list[str]:
    """Returns human-readable problems with a "production" configuration —
    empty list means safe. A pure function (no I/O, no logging) so it's
    testable without constructing an app; main.py's lifespan is the only
    caller that turns a non-empty result into a hard startup failure."""
    problems: list[str] = []
    if settings.database_url.startswith("sqlite"):
        problems.append(
            "DATABASE_URL is SQLite. CapacityOS's production architecture requires "
            "PostgreSQL-compatible storage (CLAUDE.md §7) — SQLite is a development "
            "convenience only."
        )
    if settings.ai_provider == "mock":
        problems.append(
            "AI_PROVIDER=mock. The mock provider returns deterministic canned text for "
            "local development/demos and must never be used for real decision support "
            "(docs/adr/0008-phase-8-ai-insight-layer.md)."
        )
    if not settings.cors_origins or "*" in settings.cors_origins:
        problems.append(
            "API_CORS_ORIGINS is empty or contains a wildcard. Production CORS must "
            "explicitly allowlist the deployed frontend origin(s)."
        )
    return problems
