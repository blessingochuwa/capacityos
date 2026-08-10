# Architecture Overview

This is a summary for orientation. [CLAUDE.md](../CLAUDE.md) is the governing source of truth — if anything here conflicts with it, CLAUDE.md wins.

## System boundary

```text
apps/web (React + TypeScript + Vite)
      │  HTTP (fetch, versioned REST)
      ▼
apps/api (FastAPI)
      │  api/          — thin HTTP routes: validation, serialization, DI
      │  services/      — orchestration
      │  domain/         — pure, deterministic business rules (the capacity engine)
      │  repositories/    — persistence access
      ▼
Database (SQLite in dev, PostgreSQL-compatible; SQLAlchemy + Alembic)
```

`packages/contracts` holds TypeScript types shared between `apps/web` and `apps/api`'s contracts, populated once there is real domain data to share.

## Non-negotiable rules (see CLAUDE.md for full detail)

- **Deterministic core** (CLAUDE.md §4): all capacity math (working hours, availability, realistic capacity, allocation, utilization, over/under-allocation, skill bottlenecks) lives in `apps/api/app/domain` as pure, independently-testable functions. AI is never the source of truth for these numbers.
- **Thin API routes** (CLAUDE.md §6): `apps/api/app/api` handles HTTP concerns only; business logic belongs in `services`/`domain`.
- **No business logic in React components** (CLAUDE.md §6): complex calculations stay server-side; the frontend consumes and presents.
- **Postgres-compatible from day one** (CLAUDE.md §7): SQLite is a dev convenience; no SQLite-specific assumptions in domain/persistence code.
- **Phased build order** (CLAUDE.md §39): don't implement a phase before the one before it is stable.

## Current state (Phase 0)

Repository and architecture bootstrap only. No domain entities, capacity engine, dashboard, scenario planning, AI layer, auth, or integrations exist yet. See [docs/adr/0001-phase-0-bootstrap.md](./adr/0001-phase-0-bootstrap.md) for what was scaffolded and why.
