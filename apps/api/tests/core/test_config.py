"""validate_production_config is a pure function (no I/O, no app, no
database) — these tests never construct a TestClient. See
docs/adr/0009-phase-9-production-readiness.md."""

from app.core.config import Settings, validate_production_config


def _production_safe_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "database_url": "postgresql://user:pass@db.internal:5432/capacityos",
        "ai_provider": "anthropic",
        "anthropic_api_key": "sk-real-key",
        "api_cors_origins": "https://app.capacityos.example.com",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_a_fully_safe_configuration_has_no_problems() -> None:
    assert validate_production_config(_production_safe_settings()) == []


def test_sqlite_database_url_is_flagged() -> None:
    settings = _production_safe_settings(database_url="sqlite:///./capacityos.db")
    problems = validate_production_config(settings)
    assert any("SQLite" in p for p in problems)


def test_mock_ai_provider_is_flagged() -> None:
    settings = _production_safe_settings(ai_provider="mock")
    problems = validate_production_config(settings)
    assert any("mock" in p.lower() for p in problems)


def test_none_ai_provider_is_not_flagged() -> None:
    """"none" (AI disabled) is a fully safe, first-class production
    configuration — only "mock" (canned demo output) is unsafe."""
    settings = _production_safe_settings(ai_provider="none", anthropic_api_key=None)
    problems = validate_production_config(settings)
    assert not any("provider" in p.lower() for p in problems)


def test_empty_cors_origins_is_flagged() -> None:
    settings = _production_safe_settings(api_cors_origins="")
    problems = validate_production_config(settings)
    assert any("CORS" in p for p in problems)


def test_wildcard_cors_origin_is_flagged() -> None:
    settings = _production_safe_settings(api_cors_origins="*")
    problems = validate_production_config(settings)
    assert any("CORS" in p for p in problems)


def test_multiple_problems_are_all_reported_at_once() -> None:
    settings = _production_safe_settings(
        database_url="sqlite:///./capacityos.db", ai_provider="mock"
    )
    problems = validate_production_config(settings)
    assert len(problems) == 2


def test_development_defaults_are_only_evaluated_by_this_function_not_enforced_by_settings() -> (
    None
):
    """Settings itself never rejects a development-shaped configuration —
    validate_production_config is an explicit, separate gate main.py's
    lifespan calls only when environment == "production"."""
    settings = Settings(environment="development")
    assert settings.database_url.startswith("sqlite")
    assert settings.ai_provider == "none"
