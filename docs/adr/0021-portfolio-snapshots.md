# ADR 0021: Phase 21 — portfolio snapshots

- **Status:** Accepted
- **Date:** 2026-08-25

## Context

Phase 20 (ADR 0020) resolved the one product decision Phase 19 explicitly
deferred (scenario-vs-baseline prioritization comparison) but, per that
phase's own brief, deliberately did not decide what Phase 21 should be.
CLAUDE.md §39 stopped at Phase 20; `docs/roadmap.md`'s "Proposed future
phases" section named several still-open items but explicitly marked all
of them provisional, not a commitment.

Per the phase brief's explicit instruction not to infer a scope from the
mere existence of deferred features, the repository was audited first —
CLAUDE.md (§§4, 21, 31, 39 especially), `docs/roadmap.md`,
`docs/architecture.md`, `docs/domain-concepts.md`, every ADR through 0020,
`docs/PRD-phase-17-prioritization.md`, the complete Phase 17-20
prioritization implementation, and the existing authorization/RBAC/
multi-tenancy mechanisms. That audit confirmed Phase 21 is not defined
anywhere and that the roadmap already named exactly three bounded,
genuinely viable candidates:

- **Portfolio Snapshots** — an explicit, immutable, point-in-time saved
  ranking (the PRD's own original §8 proposal, unrealized until now).
- **AI scenario-comparison explanation** — a sixth AI capability
  explaining Phase 20's comparison output, the smallest and most
  mechanical of the three (same-shape fifth-capability pattern Phase 19
  already proved), but the least product-novel.
- **The five remaining Recharts visualizations** — named in the roadmap
  but really several independent micro-slices bundled under one label;
  at least one (a dependency timeline) has no real semantics to visualize
  yet without inventing scope (`ProjectDependency` has no dates/duration).

A fourth bucket — other items named in CLAUDE.md §39's "Deferred items"
paragraph and the roadmap's "Proposed, unscheduled" list (Import/Export
registration, membership-management UI, SSO, billing, org hierarchies,
Chrome extension, a PostgreSQL verification of Phase 15) — was checked
and found to require a new, explicit product requirement before any of
them is even scopeable; none was promoted.

These three candidates, with their trade-offs, were presented to the user
via a blocking question rather than guessed. **Portfolio Snapshots was
selected** — the most self-contained of the three (depends on nothing
unfinished, introduces no new authorization pattern, and is a genuinely
novel domain concept rather than a repeat of Phase 19's own AI-capability
shape).

## Decisions

### The product decision was already made by the PRD — this phase builds it

Unlike Phase 20, this phase required no new product decision: the PRD's
own §8 (written and confirmed before Phase 17's first line of code) had
already specified `PortfolioSnapshot` precisely — "an explicit,
user-triggered 'save today's computed ranking' record... stored as a
genuine historical record (like `AuditEvent`), never read back as an
input to a live computation." Phase 21's job was to audit whether that
original design still held against the codebase as it actually evolved
through Phases 17-20, then build it. It did — no design fork was needed.

### Freezing the entries, not just referencing them

The PRD named the fields to capture (`organization_id`, `framework_id`,
`taken_at`, the ranked project list with each project's score "as of that
moment"). Implementing this literally required one refinement beyond the
PRD's own text: the ranked-list JSON entries capture `project_name`,
`score`, `rank`, `missing_criteria`, `breakdown`, and `category` in full,
not just `project_id` — because a snapshot's entire purpose is historical
reproducibility, and a project rename or later re-score must never change
what an already-taken snapshot shows. This is the direct implementation
of "historical ranking reproducibility," one of the exact audit points
the phase brief asked to verify before implementation.

That same reasoning was extended one level up, beyond what the PRD's text
literally named: `framework_name` and `framework_type` are ALSO frozen
directly on the `PortfolioSnapshot` row, not read live from the linked
`PrioritizationFramework` — a framework's `name` is editable
(`PrioritizationFrameworkUpdate.name`), so a live join would let a later
rename silently rewrite history. Verified live: renaming a framework
after taking two snapshots left both snapshots' frozen `framework_name`
unchanged, while a live `GET .../frameworks/{id}` correctly showed the
new name.

### `PortfolioSnapshotService.create` calls `rank_portfolio` verbatim

`PortfolioSnapshotService.create` calls
`ProjectPriorityScoreService.rank_portfolio` unchanged — the exact same
function the live Portfolio Priority Board uses — then copies its result
into a frozen JSON payload. No second ranking computation, no
recalculated score, matching every prior prioritization phase's "derive
through the one existing engine, never a second one" discipline exactly
(Phase 20's `ScenarioPriorityService.compare` established the same
pattern for the scenario comparison). `PortfolioSnapshotService` has no
constructor dependency on `PrioritizationFrameworkRepository` — framework
resolution and cross-organization validation are delegated entirely to
`rank_portfolio`, which already raises `NotFoundError` for a missing or
cross-organization framework, rather than duplicated.

### `PortfolioSnapshot`: its own table, JSON entries, no child table

A new, standalone `portfolio_snapshots` table — `organization_id`,
`framework_id` (FK, `RESTRICT`), `framework_name`, `framework_type`,
`entries` (a JSON array), plus the standard UUID/timestamp columns.
`entries` is untyped JSON at the model layer (`dict[str, Any]`, matching
`AuditEvent.event_metadata`'s own precedent for JSON that gets
reconstructed into strict types only at the schema boundary), rather than
a child table — a snapshot is only ever read back whole (never queried
per-entry), so a child table would add migration/join complexity with no
behavioral benefit. `created_at` (`TimestampMixin`) doubles as "taken
at" — no separate column, matching `AuditEvent`'s own precedent where
`created_at` already means "when this happened" for an immutable
historical record. No `created_by` column either: every other
business-domain entity in this codebase (`Risk`, `Stakeholder`,
`ProjectPriorityScore`, `ScenarioPriorityOverride`) answers "who did
this" through `AuditEvent`, not a denormalized actor column on the
entity itself — `PortfolioSnapshot` follows that same precedent rather
than inventing a new one.

`framework_id`'s FK is `RESTRICT`, matching `organization_id`'s own
convention — frameworks are soft-deleted only
(`PrioritizationFrameworkService.deactivate` sets `is_active=False`,
never a hard row delete, confirmed by reading
`app/services/prioritization_framework.py`), so this is a safety net for
a deletion path that does not currently exist, not behavior that will
ever actually trigger.

No PATCH/DELETE route exists for this entity — immutable and
append-only, matching `AuditEvent`'s own shape exactly. This was
confirmed with the user as part of the implementation-plan sign-off
before any code was written, alongside the entry-freezing decision above
and the authorization decision below.

### Authorization: `PRIORITIZATION_MANAGE`, not `PRIORITIZATION_SCORE`

Creating a snapshot is gated by the existing `Permission.
PRIORITIZATION_MANAGE` (Admin/Owner only) — reused unchanged, no new
permission. This was a deliberate choice, confirmed with the user before
implementation: `PRIORITIZATION_SCORE` is project-instance-scoped via
`require_project_access` (Phase 11's `ProjectAccessGrant` mechanism), but
a snapshot spans every project scored under a framework at once — there
is no single project to check a grant against. This matches framework
CRUD's own reasoning exactly (`PRIORITIZATION_MANAGE`'s docstring: "an
org-wide configuration surface, restricted tighter than ordinary write
access... a framework change silently reshuffles every project's rank
org-wide") — a snapshot is the same class of org-wide action. Listing
snapshots uses `Permission.PRIORITIZATION_READ` (every role), matching
every other read in this router and the PRD's own §11 proposal exactly.
Verified live: a Manager received 403 attempting to create a snapshot
but 200 listing them; an Admin succeeded creating one.

### API: extends the existing `/api/v1/prioritization` router

```text
POST /api/v1/prioritization/snapshots
GET  /api/v1/prioritization/snapshots
```

No new top-level resource, no organization id in the path — this departs
from the PRD's own original §9 draft
(`/api/v1/organizations/{org_id}/prioritization/snapshots`), which
predates how every other Phase 17-20 route actually ended up shaped:
`/api/v1/prioritization/frameworks`, `/api/v1/prioritization/portfolio`,
and `/api/v1/prioritization/dependency-graph` all resolve organization
scope from `membership.organization_id` via `get_current_membership`,
never from a URL path segment. The snapshots routes follow that
established, actually-built convention instead of the PRD's unrealized
draft — the same kind of "the PRD's language presupposed something that
was never actually built this way" correction ADR 0020 made for the
scenario-comparison routes.

### Audit: `portfolio_snapshot.create`, matching the PRD's own §12 proposal

`AuditAction.PORTFOLIO_SNAPSHOT_CREATE = "portfolio_snapshot.create"` —
named exactly as the PRD's own §12 proposal specified. Metadata logs
`framework_id` and `entry_count` only, never the full frozen ranking
(matching Risk/Stakeholder's "field names/counts only, never bulk
content" convention). Verified live via `GET /api/v1/audit`.

### Frontend: extends the existing Prioritization Overview page

`PortfolioSnapshotList` is a new component added to the existing
`PrioritizationOverviewPage` — no new route, no new navigation entry,
matching Phase 19/20's "extend the existing view" precedent. A "Take
snapshot" action (visible only to `PRIORITIZATION_MANAGE`, matching the
existing "New framework" button's gating) sits in the new card's header;
selecting a snapshot row renders its frozen entries by reusing the
existing `PortfolioTable` component as-is, since a snapshot entry has the
identical shape to a live ranking entry — no new table component, no new
charting dependency (CLAUDE.md §29).

## Consequences

- 1 new table (`portfolio_snapshots`), 1 migration, 0 new permissions, 1
  new `AuditAction` member (`portfolio_snapshot.create`). 0 changes to
  any existing table or permission's grant set.
- New backend modules: `app/models/portfolio_snapshot.py`,
  `app/repositories/portfolio_snapshot.py`,
  `app/services/portfolio_snapshot.py`. Extended:
  `app/schemas/prioritization.py` (+`PortfolioSnapshotCreate`,
  +`PortfolioSnapshotEntryRead`, +`PortfolioSnapshotRead`,
  +`portfolio_snapshot_to_read`), `app/api/v1/prioritization.py` (+2
  routes, +`get_snapshot_service`), `app/models/enums.py` (+1
  `AuditAction` member), `app/models/__init__.py`.
- New frontend modules:
  `features/prioritization/{types/prioritization additions,
  api/prioritizationApi.ts additions,
  hooks/usePortfolioSnapshots,hooks/useSnapshotMutations,
  components/PortfolioSnapshotList}`. Extended:
  `features/prioritization/views/PrioritizationOverviewPage.tsx`,
  `test/fixtures.ts` (+1 fixture builder).
- Backend: +15 tests (`tests/api/test_portfolio_snapshots.py` — creation
  freezing the live ranking, empty/incomplete/MoSCoW rankings, immutability
  against a later re-score and a later framework rename, listing/
  filtering, RBAC for both Manager-denied and Admin-allowed, audit, and
  the explicit cross-organization/IDOR tests every new resource requires)
  — 931 total, all passing. `ruff check` and `uv run pyright` (strict)
  both fully clean. Fresh `alembic upgrade head`, `alembic current`, and
  an upgrade→downgrade→upgrade round trip all verified against a real
  file-backed database.
- Frontend: +3 tests (`PortfolioSnapshotList.test.tsx`) — 218 total, all
  passing. `oxlint`/`tsc -b --noEmit` clean (the same 2 pre-existing,
  unrelated `AuthContext.tsx` warnings as every prior phase). Production
  build succeeds.
- Live verification: a real uvicorn instance was started against a
  genuinely fresh, migrated, file-backed SQLite database with a real
  Owner account bootstrapped via `scripts/create_first_owner.py`. A real
  authenticated session (cookie login, double-submit CSRF token) walked
  the full golden path over real HTTP — create project → create RICE
  framework → score it (400) → take a snapshot (frozen at rank 1, score
  400) → re-score the project (3600) → re-read the ORIGINAL snapshot
  (confirmed still 400, untouched) → take a SECOND snapshot (confirmed
  3600, the new value) → rename the framework → re-read BOTH snapshots
  (confirmed both still show the original frozen framework name, not the
  rename) — plus confirmed unauthenticated (401), a Manager denied
  creation (403) but allowed to list (200), an Admin allowed to create
  (201), a nonexistent/cross-organization framework id (404, not
  403/500), real `AuditEvent` rows for both snapshot creations with the
  expected `framework_id`/`entry_count` metadata, and a log scan
  confirming no password or secret value was ever written to the server
  log. No browser or interactive UI walkthrough was performed — no such
  tool is available in this environment (the same disclosed limitation
  as every prior phase).
- **Deferred, not dropped**: the five remaining Recharts visualizations;
  an AI interpretation of the Phase 20 scenario comparison (left for a
  future phase, per that phase's own brief); a diffing/trend UI comparing
  two snapshots; a snapshot of a scenario's hypothetical (rather than
  baseline) ranking; `PortfolioSnapshot` Import/Export registration
  (matching Risk/Stakeholder/Prioritization/`ProjectDependency`'s own
  precedent).
- **Residual risk**: none newly introduced. No behavior change to any
  existing phase's authorization, audit, capacity, risk, scenario, or
  Phase 17-20 prioritization/comparison behavior — this phase only reads
  already-computed facts through the unchanged `rank_portfolio` path and
  persists a frozen copy of them.
