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

## Current state (Phase 4)

The domain foundation (Phase 1) exists: Person, Team/TeamMembership, Project, Allocation, WorkingSchedule/WorkingScheduleEntry, and AvailabilityException — with SQLAlchemy models, an Alembic migration, Pydantic contracts, repositories, services, and thin CRUD routes under `/api/v1/`. See [docs/domain-concepts.md](./domain-concepts.md) for what each entity means (in particular, the WORKING SCHEDULE ≠ AVAILABILITY ≠ ALLOCATION ≠ CAPACITY distinction) and [docs/adr/0002-phase-1-domain-foundation.md](./adr/0002-phase-1-domain-foundation.md) for the implementation decisions behind them.

Phase 2 adds the deterministic capacity engine: `app/domain/capacity.py` and `app/domain/dates.py` are pure, database-free calculations (tested without a database under `apps/api/tests/domain/`) that turn `WorkingSchedule + AvailabilityException + Allocation` into gross/effective/allocated/remaining capacity, utilization, and over-allocation — for a person, a team, or a project's demand — exposed through three read-only endpoints under `/api/v1/capacity/`. See the "Capacity Engine" section of [docs/domain-concepts.md](./domain-concepts.md#capacity-engine-phase-2) for the formulas and [docs/adr/0003-phase-2-capacity-engine.md](./adr/0003-phase-2-capacity-engine.md) for the design decisions (allocation time-phasing, overlapping-exception handling, zero-capacity utilization, weighted team utilization).

Phase 3 adds the read-only capacity dashboard (`apps/web/src/features/capacity/`): a team overview, per-person and per-project views, all consuming the Phase 2 endpoints verbatim — no capacity math in the frontend.

Phase 4 adds scenario planning (`app/domain/scenario.py`, `app/services/scenario*.py`, `apps/web/src/features/scenarios/`): hypothetical "what if?" exercises that never write to production data. A `Scenario` is a baseline period plus a list of typed operations (add/adjust/remove/move an allocation, shift a project's dates, change availability, add a hypothetical resource); calculating one builds a hypothetical version of the same facts Phase 2 already consumes and runs them through the **unmodified** Phase 2 engine, then compares the two results. See [docs/domain-concepts.md](./domain-concepts.md#scenario-planning-phase-4) for the concepts and [docs/adr/0004-phase-4-scenario-planning.md](./adr/0004-phase-4-scenario-planning.md) for the design decisions (why no engine refactor was needed, the operation type set, JSON+discriminated-union payload storage, no caching).

**Still not implemented**, by design: skills/bottleneck analysis, AI, integrations, and auth. Phases 1–4 exist to give those later phases trustworthy source data, a trustworthy engine, and a safe what-if layer on top of it — see [docs/adr/0001-phase-0-bootstrap.md](./adr/0001-phase-0-bootstrap.md) for the original bootstrap.
