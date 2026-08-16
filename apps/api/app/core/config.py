from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../../.env", env_file_encoding="utf-8", extra="ignore"
    )

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

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
