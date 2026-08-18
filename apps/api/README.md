# capacityos-api

FastAPI backend for CapacityOS, managed with [uv](https://docs.astral.sh/uv/). See the [repository root README](../../README.md) for the full quick start and [CLAUDE.md](../../CLAUDE.md) for architectural rules.

## Setup

```bash
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run python ../../scripts/create_first_owner.py   # first run only — see docs/adr/0010-authentication-rbac-audit.md
```

## Scripts

- `uv run uvicorn app.main:app --reload` — start the dev server (`GET /api/v1/health` for a liveness check)
- `uv run pytest` — run the test suite
- `uv run ruff check .` — lint
- `uv run ruff format .` — format
- `uv run pyright` — static type checking (strict mode; relaxed for `tests/` where third-party test-client typing is incomplete)
- `uv run alembic revision --autogenerate -m "..."` — generate a migration after changing `app/models` (always hand-review the result — see [docs/adr/0002-phase-1-domain-foundation.md](../../docs/adr/0002-phase-1-domain-foundation.md))

## Layout

```text
app/
├── main.py          FastAPI app + middleware + exception-handler wiring
├── api/
│   ├── deps.py        Shared auth/RBAC FastAPI dependencies (Phase 10) — get_current_user,
│   │                  require_permission, require_csrf
│   └── v1/            HTTP routes (thin — no business logic): auth, users, audit, people, teams,
│                       projects, allocations, working-schedules, availability-exceptions,
│                       capacity, scenarios, insights, skills, imports, exports, ai, health
├── core/              Settings, database session/transaction handling, domain exceptions, security
│                      primitives (password hashing, session tokens — Phase 10)
├── domain/            Pure deterministic business rules — the capacity engine (Phase 2) plus the
│                      RBAC permission table (Phase 10, app/domain/authorization.py)
├── services/          Validation and orchestration across repositories
├── repositories/      Persistence access (SQLAlchemy)
├── models/             SQLAlchemy ORM models — see docs/domain-concepts.md
├── schemas/            Pydantic Create/Update/Read contracts per entity
└── integrations/       External-service adapters (AI providers only — see docs/adr/0008)
```

See [docs/domain-concepts.md](../../docs/domain-concepts.md) for what each domain entity means.
