# CapacityOS

CapacityOS is an open-source-first resource and capacity planning platform for growing teams. It helps teams answer: **can we realistically take on this work with the people, time, skills, and capacity we currently have?**

The full product mission, operating philosophy, and architectural rules for this repository are defined in [CLAUDE.md](./CLAUDE.md) — that document is the governing source of truth for how this project is built. See also [docs/architecture.md](./docs/architecture.md) for a shorter technical overview.

> **Status:** Phase 1 — domain foundation (Person, Team, Project, Allocation, WorkingSchedule, AvailabilityException). No capacity calculations, dashboard, scenarios, AI, or integrations exist yet. See [docs/domain-concepts.md](./docs/domain-concepts.md) for what the domain entities mean and [docs/adr/](./docs/adr/) for the decisions behind them.

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

### Environment variables

Copy `.env.example` to `.env` at the repo root and adjust values as needed. See the file for what each variable controls.

## Development

- Frontend lint/typecheck/test: `npm run lint --workspace apps/web`, `npm run typecheck --workspace apps/web`, `npm run test --workspace apps/web`
- Backend lint/typecheck/test: from `apps/api`, `uv run ruff check .`, `uv run pyright`, `uv run pytest`

See [CONTRIBUTING.md](./CONTRIBUTING.md) for full contribution guidelines and [SECURITY.md](./SECURITY.md) for reporting vulnerabilities.

## License

[MIT](./LICENSE)
