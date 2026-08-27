# CapacityOS

CapacityOS is an open-source-first resource and capacity planning platform for growing teams. It helps teams answer: **can we realistically take on this work with the people, time, skills, and capacity we currently have?**

The full product mission, operating philosophy, and architectural rules for this repository are defined in [CLAUDE.md](./CLAUDE.md) — that document is the governing source of truth for how this project is built. See also [docs/architecture.md](./docs/architecture.md) for a shorter technical overview.

> **Status:** Phase 25 — domain foundation, a deterministic capacity engine, a read-only capacity dashboard, scenario/what-if planning, operational insights (prioritized, explainable capacity signals), CSV/JSON import/export, skills & bottleneck analysis (SKILL capacity vs TOTAL capacity, skill gaps, single points of failure), an optional AI insight layer (explains existing deterministic facts — summaries, signal/scenario/bottleneck explanations, grounded recommendations — never a second calculation engine), a production-readiness/observability foundation (structured logging, request correlation, health/readiness, configuration safety, consistent error handling), an identity/authentication/RBAC/audit foundation (session-cookie login, a five-role permission model, and a persistent audit trail — see [docs/adr/0010-authentication-rbac-audit.md](./docs/adr/0010-authentication-rbac-audit.md)), instance-level resource authorization (a Manager's write/delete authority on a Team or Project is scoped to explicit grants, not automatic for every Team/Project in the system — see [docs/adr/0011-instance-level-resource-authorization.md](./docs/adr/0011-instance-level-resource-authorization.md)), organizations & multi-tenancy (every entity belongs to exactly one Organization; role lives on a per-organization membership rather than the account, so one person can hold different roles in different organizations, and a user can never read, modify, or export another organization's data — see [docs/adr/0012-organizations-multi-tenancy.md](./docs/adr/0012-organizations-multi-tenancy.md)), risk management (a project-scoped risk register — description, cause, potential effect, probability, impact, response, owner, status, review date — with exposure always derived, never stored as a false-precision score, and high-exposure/overdue-review risks surfaced through the existing Insights page — see [docs/adr/0013-phase-13-risk-management.md](./docs/adr/0013-phase-13-risk-management.md)), stakeholder management (a project-scoped stakeholder register — name, an optional link to an existing Person, role, influence, interest, decision authority, communication needs — with no score or "engagement quadrant" ever computed, and deliberately not surfaced through Insights since CLAUDE.md defines no deterministic stakeholder signal — see [docs/adr/0014-phase-14-stakeholder-management.md](./docs/adr/0014-phase-14-stakeholder-management.md)), a last-owner invariant (every active Organization retains at least one Owner who can actually authenticate — role change, membership revocation, and account deactivation are each guarded by an atomic check safe under concurrent requests, closing a gap deferred since Phase 12 — see [docs/adr/0015-last-owner-invariant.md](./docs/adr/0015-last-owner-invariant.md)), a completed instance-authorization audit (every remaining Phase 11 deferral — Team→Project inheritance, Person-keyed resource scoping, Scenario scoping — was re-examined and deliberately retained as role-only, since no specification defines the ownership concept any of them would require; the audit closed a real cross-organization test-coverage gap instead — see [docs/adr/0016-instance-authorization-completion.md](./docs/adr/0016-instance-authorization-completion.md)), and a prioritization engine (RICE, ICE, WSJF, Weighted Scoring, and MoSCoW rank a portfolio against an organization-chosen framework — CapacityOS never prescribes one; a score is always derived at read time from recorded criterion inputs, never stored or cached; a Weighted Scoring framework's criteria can be edited after creation; `ProjectDependency` tracks blocks/related/enables relationships with cycle detection and a Dependency Graph view; an AI capability explains why an existing score is what it is, without ever computing or suggesting a score itself; a Scenario can carry explicit, hypothetical prioritization inputs and be compared against the live baseline ranking under a chosen framework, using the exact same deterministic scoring/ranking engine and never mutating the real, persisted score; and an explicit, user-triggered, immutable point-in-time portfolio snapshot freezes a framework's current ranking — project names, scores, ranks, and the framework's own name at that moment — so a later rename, re-score, or deletion never rewrites an already-taken snapshot, with no PATCH/DELETE route at all, matching `AuditEvent`'s own append-only shape; and two immutable snapshots can be diffed (entered/left/changed/unchanged per project, rejected with a 422 if they belong to different frameworks) through a pure comparison that never touches the scoring engine and is never persisted; a sixth AI capability explains an existing snapshot comparison in plain language — grounded exclusively in that already-computed Phase 22 diff, never recalculating a score, rank, or category itself; a multi-snapshot score-over-time trend chart, built entirely from already-fetched snapshot data with zero backend changes, shows how a project's priority score has moved across two or more saved snapshots; and, for a WSJF-typed framework, a breakdown chart shows each scored project's four fixed WSJF inputs — also built entirely from already-fetched portfolio data with zero backend changes — stacking the three additive Cost-of-Delay components while showing Job Size (the formula's divisor, not a fourth additive term) as its own adjacent bar; the four remaining Recharts visualizations the original PRD specifies, an AI interpretation of the scenario comparison, a rank-over-time variant of the trend chart, a membership/user-management UI, and a snapshot of a scenario's own hypothetical ranking remain scoped, deliberate deferrals, not oversights — see [docs/PRD-phase-17-prioritization.md](./docs/PRD-phase-17-prioritization.md), [docs/adr/0017-prioritization-engine.md](./docs/adr/0017-prioritization-engine.md), [docs/adr/0018-prioritization-frameworks-and-dependencies.md](./docs/adr/0018-prioritization-frameworks-and-dependencies.md), [docs/adr/0019-ai-priority-explanation.md](./docs/adr/0019-ai-priority-explanation.md), [docs/adr/0020-scenario-priority-comparison.md](./docs/adr/0020-scenario-priority-comparison.md), [docs/adr/0021-portfolio-snapshots.md](./docs/adr/0021-portfolio-snapshots.md), [docs/adr/0022-portfolio-snapshot-comparison.md](./docs/adr/0022-portfolio-snapshot-comparison.md), [docs/adr/0023-ai-snapshot-comparison-explanation.md](./docs/adr/0023-ai-snapshot-comparison-explanation.md), [docs/adr/0024-portfolio-snapshot-trend.md](./docs/adr/0024-portfolio-snapshot-trend.md), and [docs/adr/0025-wsjf-breakdown-visualization.md](./docs/adr/0025-wsjf-breakdown-visualization.md)) are implemented. The app runs fully without any AI provider configured. External integrations, SSO/OAuth, and billing do not exist yet. See [docs/roadmap.md](./docs/roadmap.md) for the full phase-by-phase status and what's proposed next, [docs/production-readiness.md](./docs/production-readiness.md) for the operational reference, [docs/domain-concepts.md](./docs/domain-concepts.md) for what the domain entities mean, and [docs/adr/](./docs/adr/) for the decisions behind them.

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
