# CapacityOS

CapacityOS is an open-source-first resource and capacity planning platform for growing teams. It helps teams answer: **can we realistically take on this work with the people, time, skills, and capacity we currently have?**

The full product mission, operating philosophy, and architectural rules for this repository are defined in [CLAUDE.md](./CLAUDE.md) — that document is the governing source of truth for how this project is built. See also [docs/architecture.md](./docs/architecture.md) for a shorter technical overview.

> **Status:** Phase 11 — domain foundation, a deterministic capacity engine, a read-only capacity dashboard, scenario/what-if planning, operational insights (prioritized, explainable capacity signals), CSV/JSON import/export, skills & bottleneck analysis (SKILL capacity vs TOTAL capacity, skill gaps, single points of failure), an optional AI insight layer (explains existing deterministic facts — summaries, signal/scenario/bottleneck explanations, grounded recommendations — never a second calculation engine), a production-readiness/observability foundation (structured logging, request correlation, health/readiness, configuration safety, consistent error handling), an identity/authentication/RBAC/audit foundation (session-cookie login, a five-role permission model, and a persistent audit trail — see [docs/adr/0010-authentication-rbac-audit.md](./docs/adr/0010-authentication-rbac-audit.md)), and instance-level resource authorization (a Manager's write/delete authority on a Team or Project is scoped to explicit grants, not automatic for every Team/Project in the system — see [docs/adr/0011-instance-level-resource-authorization.md](./docs/adr/0011-instance-level-resource-authorization.md)) are implemented. The app runs fully without any AI provider configured. External integrations and multi-tenancy do not exist yet. See [docs/production-readiness.md](./docs/production-readiness.md) for the operational reference, [docs/domain-concepts.md](./docs/domain-concepts.md) for what the domain entities mean, and [docs/adr/](./docs/adr/) for the decisions behind them.

## Repository layout

```text
apps/
  web/           React + TypeScript + Vite frontend
  api/            Python + FastAPI backend
packages/
  contracts/      Shared contracts (placeholder — populated once there is real domain data to share)
scripts/          Deterministic operational utilities (seeding, imports/exports, maintenance)
data/             Development-only seed data and fixtures (never real/production data)
docs/             Architecture, domain, and decision documentation
tests/            Cross-application / end-to-end tests
```

## Prerequisites

- [Node.js](https://nodejs.org/) 24+ and npm 11+
- [uv](https://docs.astral.sh/uv/) (manages the Python version and virtual environment for `apps/api` — no separate Python install required)

## Quick start

### Frontend (`apps/web`)

```bash
npm install
npm run dev --workspace apps/web
```

The dev server runs at `http://localhost:5173`.

### Backend (`apps/api`)

```bash
cd apps/api
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`. A health check is available at `GET /api/v1/health`; domain CRUD routes (people, teams, projects, allocations, working schedules, availability exceptions) are under `/api/v1/`.

**First run only:** create the first Owner account (there is no open self-registration — see [docs/adr/0010-authentication-rbac-audit.md](./docs/adr/0010-authentication-rbac-audit.md)):

```bash
uv run python ../../scripts/create_first_owner.py
```

### Environment variables

Copy `.env.example` to `.env` at the repo root and adjust values as needed. See the file for what each variable controls.

## Development

- Frontend lint/typecheck/test: `npm run lint --workspace apps/web`, `npm run typecheck --workspace apps/web`, `npm run test --workspace apps/web`
- Backend lint/typecheck/test: from `apps/api`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`

See [CONTRIBUTING.md](./CONTRIBUTING.md) for full contribution guidelines and [SECURITY.md](./SECURITY.md) for reporting vulnerabilities.

## License

[MIT](./LICENSE)
