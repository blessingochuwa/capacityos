# ADR 0042: Phase 42 — Capacity vs. Priority matrix

- **Status:** Accepted
- **Date:** 2026-09-08

## Context

Phase 41 was an audit-only re-audit of the full roadmap (no code, no ADR,
no commit) and recommended an Audit Log UI as the strongest ready
candidate, since the PRD's remaining Capacity-vs-Priority and
Risk-vs-Value visualizations were both still blocked on unresolved
product decisions (reconfirmed directly against source by the Phase 39
and Phase 41 audits: `Project` has no capacity field, and no rule
anywhere aggregates `Risk`'s categorical exposure into a single "Value"
axis).

The Phase 42 brief overrides that blocker for Capacity-vs-Priority
specifically by supplying the missing product decision directly, rather
than asking this phase to invent one:

> A project's capacity requirement is the total allocated hours for that
> project over the currently represented planning horizon.

This is a definition supplied by the user acting as product owner, not
one derived by this phase's own audit — the brief is explicit that this
question must not be reopened. With that decision given, the remaining
work is implementation, verification that the existing data model can
support it without fabrication, and disclosure of every resulting
data-handling choice.

### What was audited before implementing

- Git state: `HEAD` at `8f8ce7b` (Phase 40, committed **and** pushed to
  `origin/main`), working tree clean, branch `main`. Phase 41 left
  nothing uncommitted (it was audit-only).
- CLAUDE.md §§4, 21, 26–40; `docs/roadmap.md`; `docs/architecture.md`;
  `docs/domain-concepts.md`; `README.md`; `docs/PRD-phase-17-prioritization.md`
  §§5, 8, 15; ADR 0003 (capacity engine — `ProjectDemandRead.allocated_hours`
  semantics), ADR 0004 (scenario/project-demand reuse), ADR 0017/0018
  (prioritization engine, `ProjectPriorityScore`/`PortfolioRankingEntry`),
  ADR 0025/0027 (WSJF breakdown / Priority-vs-Effort scatter — the
  "zero backend changes, join client-side" precedent this phase follows),
  and ADR 0040 (Dependency Timeline — the most recent frontend-only
  visualization phase and its stated recommendation to re-audit rather
  than assume the next visualization).
- Backend: `app/api/v1/capacity.py::get_project_demand` (`GET
  /api/v1/capacity/projects/{id}?start_date=&end_date=` — per-project,
  requires an explicit date range, would need one call per project plus
  an invented global "planning horizon" window to use portfolio-wide);
  `app/api/v1/allocations.py::list_allocations` (`GET /api/v1/allocations`
  — already `ALLOCATION_READ`-gated, already organization-scoped via
  `get_current_membership`, already supports listing with no `person_id`/
  `project_id` filter, `limit` up to 500); `app/models/allocation.py`
  (`allocation_hours` is the **total** planned hours for the row's whole
  `[start_date, end_date]` span — the exact quantity a "total allocated
  hours" definition needs, summed across every `Allocation` row for a
  project); `app/schemas/capacity.py::ProjectDemandRead.allocated_hours`
  (confirms the existing precedent: an unallocated project's demand is a
  real, computed `0`, never `null` — the model this phase's capacity axis
  deliberately does **not** copy, see Decision); `app/models/project.py`
  (still no capacity field, confirming Capacity-vs-Priority was correctly
  blocked before this phase's product decision arrived).
- Frontend: `apps/web/src/api/entities.ts` (`LIST_ALL_LIMIT = 500`, the
  established "no pagination UI exists anywhere" convention every list
  wrapper already follows — `peopleApi.list`/`teamsApi.list`/
  `projectsApi.list`); `features/prioritization/utils/priorityEffortScatter.ts`
  and `wsjfBreakdown.ts` (the established "copy the already-computed
  `score` verbatim, exclude on `score !== null`" pattern this phase
  reuses exactly); `features/prioritization/utils/dependencyTimeline.ts`
  and `components/DependencyTimeline.tsx` (the established "join two
  already-authorized bulk reads client-side, pure transform + unit tests
  + chart/`aria-hidden` + accessible table" shape this phase mirrors);
  `features/prioritization/views/PrioritizationOverviewPage.tsx` (confirms
  `projectsQuery`/`portfolioQuery` are already mounted once per page load
  and reusable); `components/ui/{Table,EmptyState,Badge,QueryBoundary}.tsx`;
  `src/test/fixtures.ts` (no `makeAllocation` fixture existed yet).

## Decision

Build the Capacity vs. Priority matrix as a **frontend-only** feature
with **zero backend changes**, on the existing `PrioritizationOverviewPage`,
joining two already-authorized, already-organization-scoped reads
client-side — exactly the Phase 24/25/27/40 precedent.

### Capacity axis — total allocated hours, summed from existing Allocation rows

A project's capacity requirement is the sum of `allocation_hours` across
every `Allocation` currently recorded against it, fetched via the
existing `GET /api/v1/allocations` route (a new `allocationsApi.list()`
wrapper with no `person_id`/`project_id` filter, mirroring
`peopleApi.list`/`projectsApi.list` verbatim — **not** a new backend
route). No date window is applied — "the currently represented planning
horizon" is read as "every allocation currently on record," matching how
Phase 40 used each project's own `start_date`/`end_date` verbatim rather
than inventing a global window. This reuses `Allocation.allocation_hours`'s
existing, documented semantic (`app/models/allocation.py`: "the TOTAL
planned hours for the whole `[start_date, end_date]` period") with no new
formula, no forecasting, and no per-period query.

**A project with zero recorded allocations is treated as missing capacity
data, not a real zero, and is excluded from the plot.** This is the one
point where this phase deliberately does **not** copy
`ProjectDemandRead.allocated_hours`'s own "never null, 0 when
unallocated" convention: that field answers "how much demand exists in
*this specific date range*" (0 is a correct answer to a bounded
question), whereas this chart's axis answers "has this project's
capacity requirement been captured at all" (a project nobody has ever
allocated any hours to has simply not been capacity-planned yet — that
absence and a deliberate "planned for exactly zero hours" are different
facts, and nothing in the schema distinguishes them for an unallocated
project the way `ProjectPriorityScore.missing_criteria` explicitly
distinguishes "no value entered" from "entered as zero" for priority
inputs). Plotting an unallocated project at `x=0` would silently assert
"this project needs no capacity," which the data does not support.

### Priority axis — the existing portfolio score, reused verbatim

Each project's already-computed `score` from
`GET /api/v1/prioritization/portfolio` for the currently selected
framework (`usePortfolio`, already mounted on this page) — copied
verbatim, never recalculated (CLAUDE.md §4/§21). `score === null` (an
incomplete numeric-framework score, or any MoSCoW-scored project, which
`calculate_moscow_result` never gives a number at all) means priority is
missing, and the project is excluded — the identical `score !== null`
filter `WsjfBreakdownChart` and `PriorityEffortScatterChart` already use.
Unlike Priority-vs-Effort (framework-type-gated to RICE/WSJF, since only
those define an "effort" criterion), this chart needs no framework-type
gate at all — `score` is `string | null` uniformly across every framework
type, so the chart is shown for every framework and simply renders its
own "nothing plottable yet" state for a MoSCoW-only selection rather than
being hidden by a type check.

### Median reference lines and quadrant classification

Reference lines are the median capacity and median priority **across the
currently plotted points only** (never across excluded projects, which
have no comparable value, and never an arbitrary invented business
threshold — CLAUDE.md §17/§29). Median is the standard sorted-array
midpoint (average of the two middle values for an even count). **A value
exactly equal to its axis's median is classified on the "low"/"not
above" side of that axis** — an explicit, documented tie rule applied
identically to both axes (`app/../capacityPriorityMatrix.ts`'s own
`median`/quadrant logic, unit-tested for the 1-point case and the
exact-median case). No existing repository convention contradicted this
choice, so the brief's own suggested default was used directly.

Quadrants are purely descriptive position labels — `High Priority / High
Capacity`, `High Priority / Low Capacity`, `Low Priority / High
Capacity`, `Low Priority / Low Capacity` — never a recommendation, risk
rating, or "quick win"/"kill"/"danger" judgment (CLAUDE.md §17/§29's "no
false precision"/"no misleading chart" rules, already established by
every prior prioritization chart in this codebase).

### Data sources — both already authorized, nothing new

- `GET /api/v1/prioritization/portfolio?framework_id=` — unchanged since
  Phase 17, `Permission.PRIORITIZATION_READ` (every role), organization-
  scoped.
- `GET /api/v1/allocations` — unchanged since Phase 1,
  `Permission.ALLOCATION_READ`, organization-scoped via
  `get_current_membership`. A new `limit`-only client wrapper
  (`allocationsApi.list()`) was added; the route itself, its
  authorization, and its scoping are untouched.

The two are joined **client-side**, mirroring Phase 24/25/27/40 exactly.
No new endpoint, query parameter, schema field, model, migration,
permission, or role.

### Implementation shape

- **`features/prioritization/utils/capacityPriorityMatrix.ts`** —
  `buildCapacityPriorityMatrix(items, allocations): CapacityPriorityMatrixModel`,
  a pure, DB-free, unit-tested function (the `buildDependencyTimeline` /
  `buildWsjfBreakdown` discipline): sums allocation hours per project,
  filters to projects with both a capacity value and a priority score,
  computes the two medians, classifies each plotted project into one of
  four quadrants by the documented tie rule, and returns both the
  plotted points and the excluded projects (each with a specific reason:
  `no_priority_score` / `no_capacity_data` / both) — sorted
  deterministically by name then id throughout.
- **`features/prioritization/components/CapacityPriorityMatrixChart.tsx`**
  — a Recharts `ScatterChart` (`aria-hidden`) with two `ReferenceLine`s
  (median capacity, median priority, each carrying a visible text label
  on the chart itself), paired with: a plain-text sentence stating both
  median values and the plotted-project count (so the reference lines'
  meaning is available without the chart); a quadrant legend (`<dl>`)
  giving every quadrant's full descriptive text, never color-only; an
  accessible **"Capacity vs. priority matrix"** table (Project / Capacity
  (hours) / Priority (score) / Quadrant); and, only when non-empty, one
  disclosure sentence naming every excluded project and its specific
  reason plus the total excluded count.
- **`hooks/useAllocations.ts`** — mirrors `useProjects`/`useTeams`
  exactly (`['allocations']` query key, no args).
- **`PrioritizationOverviewPage.tsx`** — one new nested `QueryBoundary`
  for `allocationsQuery` (a new hook call, mounted once) inside the
  existing "Portfolio priority board" card's already-mounted
  `portfolioQuery` boundary, right after the WSJF breakdown block — no
  new `Card`, no new route, no new nav entry, docstring updated.

### Empty / edge states

| State | Behaviour |
|---|---|
| No framework selected | Existing "Select a framework above…" empty state (unchanged) |
| Portfolio has zero scored projects | Existing "No projects have been scored…" empty state (unchanged) |
| Projects exist, none plottable (missing priority, missing capacity, or both) | `CapacityPriorityMatrixChart`'s own `EmptyState`: "No projects have both a priority score and capacity data to plot yet." |
| Some plottable, some excluded | Chart + table render the plottable set; one disclosure sentence names every excluded project and its reason, with the total count |
| Allocations query loading/erroring | The nested `QueryBoundary`'s existing loading/error rendering — no new error architecture |

## Authorization & multi-tenancy

- **No authorization or tenancy code was written or changed.** Both reads
  are already permission-gated (`PRIORITIZATION_READ`, `ALLOCATION_READ`)
  and already scoped to the authenticated caller's active organization on
  the server.
- The frontend passes **no** organization id anywhere — it consumes the
  current-session hooks (`usePortfolio`, `useAllocations`) exactly like
  every other surface. There is no user-controlled org selector, and no
  new permission or role was introduced.
- Cross-organization isolation is a pre-existing backend guarantee,
  unchanged: an allocation or priority score from another organization is
  never in either response, so it can never reach this component. The
  transformation additionally reflects **only** the projects it is
  handed — an allocation whose `project_id` isn't one of the supplied
  portfolio items' ids is silently ignored, never surfaced as a phantom
  row (unit- and component-tested).
- Read-only: the component issues no mutation, so there is no CSRF or
  write-permission surface to consider.

## Consequences

- **Backend:** 0 files changed. 0 new tables, 0 migrations, 0 new routes,
  0 new permissions, 0 new roles, 0 API-contract changes.
  `docs/openapi.json` untouched (nothing to regenerate).
- **Frontend:** 5 new files (`hooks/useAllocations.ts`,
  `utils/capacityPriorityMatrix.ts` + test,
  `components/CapacityPriorityMatrixChart.tsx` + test), 3 files edited
  (`api/entities.ts` — one new `allocationsApi.list()` wrapper over the
  existing route; `test/fixtures.ts` — one new `makeAllocation` fixture;
  `views/PrioritizationOverviewPage.tsx` — 2 imports, 1 hook call, 1 new
  nested `QueryBoundary` block, docstring).
- **Tests:** +27 (19 in `utils/capacityPriorityMatrix.test.ts`, 8 in
  `components/CapacityPriorityMatrixChart.test.tsx`). Frontend suite
  **341 → 368 passing**, 71 → 73 files, all green.
- **Typecheck:** `tsc -b --noEmit` clean. **Lint:** `oxlint` clean (ran
  successfully in this environment this phase — the Phase 40 Application
  Control block on the native binary was not present this run; two
  pre-existing, unrelated warnings remain in `AuthContext.tsx`). **Build:**
  `tsc -b && vite build` succeeds (the pre-existing >500 kB chunk-size
  advisory is unchanged, unrelated to this phase — Recharts has been in
  the bundle since Phase 24).
- **Backend verification:** not run — 0 backend files changed
  (`git status`/`git diff --name-only` confirm no `apps/api` path
  touched), the same convention Phases 24/25/27/40 followed for a
  frontend-only visualization phase. `pytest` could not be invoked in
  this environment regardless (blocked by the same Application Control
  policy Phase 41 already documented for this sandbox), so no attempt to
  re-verify the backend suite's count was made or claimed.
- **Fresh-DB / migration verification:** not applicable — no model or
  migration file exists in this phase's diff.
- **Live/API verification:** no backend behaviour changed, so no endpoint
  or route was verified live this phase. Both `GET` responses this
  feature consumes were already live-verified in their own phases (Phase
  3 capacity dashboard / Phase 17 portfolio board) and are byte-for-byte
  unchanged here.
- **Browser verification:** **not performed** — no browser-automation
  tool is available in this environment (the same disclosed limitation as
  every prior frontend phase). Verification was unit/component-test level
  (27 new tests), typecheck, lint, and build only.
- **Technical debt introduced:** none. No new abstraction, no new
  dependency (`ReferenceLine` is a pre-existing `recharts` export,
  confirmed present in the installed package before use), no duplicated
  logic — the util/component/table shape mirrors `buildWsjfBreakdown` /
  `WsjfBreakdownChart` and `buildDependencyTimeline` / `DependencyTimeline`.

### Known limitations

- `allocationsApi.list()` fetches up to 500 allocations in one request
  (the established, documented, repo-wide "no pagination UI exists
  anywhere" convention — see ADR 0034's own identical note for the
  account directory). An organization with more than 500 recorded
  allocations across all projects would see an undercounted capacity sum
  for the projects whose allocations fall past that cutoff. This is a
  pre-existing architectural limitation of every "list all X" hook in
  this codebase (`peopleApi.list`, `teamsApi.list`, `projectsApi.list`),
  not something this phase introduces uniquely — but it is the first
  place a silently-truncated list would produce a **numerically wrong**
  displayed value (a missing project or team row is visibly absent; an
  undercounted capacity sum looks like a normal, correct number). Flagged
  here explicitly rather than silently inherited.
- No quadrant is drawn as shaded background regions on the chart itself —
  only the reference lines and the textual legend/table convey quadrant
  membership. This was a deliberate simplicity choice (CLAUDE.md §29: no
  decorative complexity) matching this codebase's existing "chart plus
  accessible table, not chart-as-sole-source" discipline; a future phase
  could add shaded quadrant backgrounds if requested, but none was
  invented here.
- The capacity axis has no unit conversion or normalization (e.g. no
  FTE-weeks, no percentage-of-team-capacity) — CLAUDE.md §3/§28 already
  distinguish capacity from allocation from utilization, and this phase's
  brief explicitly forbids inventing a new capacity/utilization metric;
  the axis is raw hours, exactly as `Allocation.allocation_hours` stores
  them.
- Against the current demo seed (`scripts/seed_demo_data.py`), whether
  any project has both a complete numeric score and at least one
  allocation was not verified live (no browser/live-server check was
  performed this phase) — if none does, the page renders the chart's own
  "No projects have both a priority score and capacity data to plot yet."
  empty state, which is the expected, not a defect (mirrors ADR 0040's
  identical note for the Dependency Timeline against the same seed).

### Deferred, not dropped

- **Risk vs. Value quadrant** — the one remaining PRD §15 visualization,
  still blocked on a genuine product decision (how a project's multiple
  `Risk` rows aggregate into one axis value, and what "Value" means
  outside WSJF's literal `business_value` criterion) — unchanged by this
  phase, per the brief's explicit exclusion list.
- Everything else the Phase 41 audit named as deferred (scenario
  snapshots, org-wide Risk/Stakeholder registers, external integrations,
  SSO/OAuth, billing, org hierarchies, Chrome extension, PostgreSQL
  concurrency verification, the Audit Log UI Phase 41 recommended) —
  unchanged, none started this phase, per the brief's explicit exclusion
  list.

### Recommended next phase

Per the brief's own suggested sequence, Risk vs. Value should only be
attempted once "Value" and a risk-aggregation rule can be defined without
inventing business logic — that is a product decision for the user to
supply directly, the same way this phase's capacity definition was
supplied, not one for an audit to guess at. Absent that, the Phase 41
audit's Audit Log UI recommendation remains the strongest ready,
zero-ambiguity candidate.

## Confirmation

Nothing was committed or pushed as part of this phase; git discipline
(status/diff before and after) is recorded in the Phase 42 Final Report.
