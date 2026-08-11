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

## Current state (Phase 1)

The domain foundation exists: Person, Team/TeamMembership, Project, Allocation, WorkingSchedule/WorkingScheduleEntry, and AvailabilityException — with SQLAlchemy models, an Alembic migration, Pydantic contracts, repositories, services, and thin CRUD routes under `/api/v1/`. See [docs/domain-concepts.md](./domain-concepts.md) for what each entity means (in particular, the WORKING SCHEDULE ≠ AVAILABILITY ≠ ALLOCATION ≠ CAPACITY distinction) and [docs/adr/0002-phase-1-domain-foundation.md](./adr/0002-phase-1-domain-foundation.md) for the implementation decisions behind them.

**Still not implemented**, by design: any capacity/utilization/over-allocation calculation, the dashboard, scenario planning, AI, integrations, and auth. Phase 1 exists to give those later phases trustworthy source data — see [docs/adr/0001-phase-0-bootstrap.md](./adr/0001-phase-0-bootstrap.md) for the original bootstrap.
