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

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.api_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
