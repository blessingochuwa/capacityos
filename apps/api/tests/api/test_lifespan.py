"""main.py's lifespan is the one place validate_production_config's result
becomes a hard startup failure — these tests exercise that wiring directly
(not just the pure function, already covered by tests/core/test_config.py),
by monkeypatching the module-level `settings` object main.py's lifespan
reads and driving the async context manager directly, without a full
TestClient/database setup."""

import asyncio

import app.main as main_module
from app.core.config import ProductionConfigError, Settings


def _run_lifespan(settings: Settings) -> None:
    original = main_module.settings
    main_module.settings = settings
    try:

        async def _enter_and_exit() -> None:
            async with main_module.lifespan(main_module.app):
                pass

        asyncio.run(_enter_and_exit())
    finally:
        main_module.settings = original


def test_lifespan_raises_for_unsafe_production_configuration() -> None:
    unsafe = Settings(
        environment="production",
        database_url="sqlite:///./capacityos.db",
        ai_provider="none",
    )
    try:
        _run_lifespan(unsafe)
    except ProductionConfigError as exc:
        assert "SQLite" in str(exc)
    else:
        raise AssertionError("expected ProductionConfigError to be raised")


def test_lifespan_does_not_raise_for_safe_production_configuration() -> None:
    safe = Settings(
        environment="production",
        database_url="postgresql://user:pass@db.internal:5432/capacityos",
        ai_provider="anthropic",
        anthropic_api_key="sk-real-key",
        api_cors_origins="https://app.capacityos.example.com",
    )
    _run_lifespan(safe)  # must not raise


def test_lifespan_does_not_raise_for_development_environment_even_with_sqlite() -> None:
    dev = Settings(environment="development")
    _run_lifespan(dev)  # must not raise — development defaults are intentional
