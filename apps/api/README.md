# capacityos-api

FastAPI backend for CapacityOS, managed with [uv](https://docs.astral.sh/uv/). See the [repository root README](../../README.md) for the full quick start and [CLAUDE.md](../../CLAUDE.md) for architectural rules.

## Setup

```bash
uv sync
uv run alembic upgrade head   # once domain migrations exist
uv run uvicorn app.main:app --reload
```

## Scripts

- `uv run uvicorn app.main:app --reload` — start the dev server (`GET /api/v1/health` for a liveness check)
- `uv run pytest` — run the test suite
- `uv run ruff check .` — lint
- `uv run ruff format .` — format
- `uv run pyright` — static type checking (strict mode; relaxed for `tests/` where third-party test-client typing is incomplete)
- `uv run alembic revision --autogenerate -m "..."` — generate a migration once domain models exist under `app/models`

## Layout

```text
app/
├── main.py          FastAPI app + middleware wiring
├── api/              HTTP routes (thin — no business logic)
├── core/              Settings, database session
├── domain/            Pure deterministic business rules (the capacity engine)
├── services/          Orchestration across repositories/domain
├── repositories/      Persistence access (SQLAlchemy)
├── models/             SQLAlchemy ORM models
├── schemas/            Pydantic request/response schemas
└── integrations/       External-service adapters (none yet)
```
