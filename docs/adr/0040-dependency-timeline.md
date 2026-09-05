# ADR 0040: Phase 40 — Dependency timeline visualization

- **Status:** Accepted
- **Date:** 2026-09-05

## Context

Phase 39 was an audit-only hard stop (no code, no ADR, no commit). It
re-verified directly against current source — not on the strength of a
prior ADR's claim — that the three then-remaining PRD §15 visualizations
(`docs/PRD-phase-17-prioritization.md` §15) are **not** equally ready:

- **Capacity vs. Priority matrix** — blocked. `Project`
  (`app/models/project.py`) has no capacity field and no single derivable
  capacity number; capacity in this system is a Person/Team concept from
  the Phase 2 engine. "A project's capacity" is undefined on three axes at
  once (whose capacity, over what period, aggregated how), and "matrix"
  implies quadrant threshold lines CLAUDE.md §17/§29 forbid inventing.
- **Risk vs. Value quadrant** — blocked. `Risk` is a project-scoped *set*
  (0..N rows/project) with a categorical `exposure ∈ {low, medium, high}`
  (`app/domain/risk.py`); no rule anywhere aggregates that set into one
  axis position, and "Value" is not a defined term (only WSJF has a
  literal `business_value` criterion).
- **Dependency timeline** — the narrowest gap. Unlike the other two, the
  data it needs already exists: `Project.start_date` / `Project.end_date`
  (both nullable). Its blocker was never "the data does not exist" but
  "what does the axis plot, and how are undated projects handled" — a
  bounded set of decisions, not an open-ended product-modelling question.

The Phase 40 brief made those decisions explicitly (see below) and
instructed: build the dependency timeline if it can be completed
consistently with them, without asking a further product question unless
the codebase contradicts them. It does not — so this phase implemented it.

### What was audited before implementing

- Git state: `HEAD` at `19f013d` (Phase 38, committed **and** pushed —
  `main` level with `origin/main`), working tree clean, Phase 39 left
  nothing behind.
- CLAUDE.md §§4, 21, 26–40; `docs/roadmap.md`; `docs/architecture.md`;
  `docs/domain-concepts.md`; `README.md`; `docs/PRD-phase-17-prioritization.md`
  §§7, 14, 15; ADRs 0017, 0018 (`ProjectDependency` / dependency graph),
  0021, 0022, 0024, 0025, 0027 (the shipped visualizations and their
  frontend-only precedent), and the Phase 39 report.
- Backend: `app/models/project.py` (has `start_date`/`end_date`,
  nullable, DB `CHECK` `end_date >= start_date` when both set),
  `app/models/project_dependency.py` (`from_project_id`, `to_project_id`,
  `dependency_type`, `created_at` — **no** date/duration),
  `app/api/v1/projects.py::list_projects` (`Permission.PROJECT_READ`,
  scoped to `membership.organization_id`), `app/schemas/prioritization.py`
  (`DependencyGraphRead` — `nodes` + `edges`, each edge carrying both
  project ids **and** names), `app/api/v1/prioritization.py` (the
  dependency-graph route, organization-scoped since Phase 18).
- Frontend: `apps/web/src/hooks/useProjects.ts` (`GET /api/v1/projects`,
  `Page<Project>`), `features/prioritization/hooks/useDependencyGraph.ts`
  (already called on `PrioritizationOverviewPage`),
  `features/prioritization/types/prioritization.ts`,
  `features/capacity/components/ProjectDemandTimeline.tsx` and
  `features/prioritization/components/PriorityEffortScatterChart.tsx` (the
  chart-`aria-hidden` + accessible-table pairing this phase copies),
  `components/ui/{Table,EmptyState,Badge,QueryBoundary}.tsx`,
  `src/test/fixtures.ts` (`makeProject`, `makeProjectDependency`,
  `makeDependencyGraph` all already exist).

## Decision

Build the dependency timeline as a **frontend-only** feature with **zero
backend changes**, on the existing `PrioritizationOverviewPage`, from data
two already-authorized, already-organization-scoped reads already return.

### Product semantics (Phase 39 decisions, implemented verbatim)

| Concern | Decision |
|---|---|
| Timeline span | Each project's own `start_date` → `end_date`, copied verbatim. |
| A project is "scheduled" | Only when **both** `start_date` and `end_date` are present. |
| Undated projects | Listed in a separate **"Unscheduled projects"** section with the specific missing-date reason. Never given a fabricated date or axis position. |
| Dependency edges shown | `blocks` only. `related` / `enables` excluded. `blocked_by` is not synthesised — it is only ever the inverse read of a stored `blocks` edge (`ProjectDependency`'s own model docstring), so materialising it here would risk two directions that disagree. |
| Schedule-consistency warnings | **Not computed.** A `blocks` predecessor whose dates fall after its successor's is *not* flagged — that is a separate product rule not requested for this phase, and inventing a consistency judgement for display is exactly what CLAUDE.md §17/§29 warn against. |
| Interactivity | Read-only. No editing, no drag-to-schedule, no edge create/delete, no critical-path / conflict / health calculation. |

### Data sources — both already authorized, nothing new

- `GET /api/v1/projects` via the existing `useProjects()` hook —
  `Permission.PROJECT_READ`, scoped to the caller's active organization
  (`membership.organization_id`). Supplies `id`, `name`, `status`,
  `start_date`, `end_date`.
- `GET /api/v1/prioritization/dependency-graph` via the existing
  `useDependencyGraph()` hook — already rendered on this page for the
  Dependency Graph table (Phase 18), organization-scoped. Supplies every
  `blocks`/`related`/`enables` edge with both project ids and names.

The two are joined **client-side**. No new endpoint, query parameter,
schema field, model, migration, permission, or role. This mirrors the
Phase 24 / 25 / 27 precedent exactly (each a PRD §15 visualization built
with zero backend changes).

### Implementation shape

- **`features/prioritization/utils/dependencyTimeline.ts`** —
  `buildDependencyTimeline(projects, graph): DependencyTimelineModel`, a
  pure, DB-free, unit-tested function (the `buildWsjfBreakdown` /
  `buildPriorityEffortScatter` discipline): copies every date verbatim,
  never recomputes or interpolates, partitions projects into
  `scheduled` / `unscheduled`, filters edges to `blocks` only, flags each
  edge `both_scheduled`, derives `rangeStart`/`rangeEnd` as the min/max
  across scheduled rows, and sorts everything deterministically (scheduled
  by start-date, then end-date, then name, then id; unscheduled and edges
  by name/id) so identical inputs always render identically.
- **`features/prioritization/components/DependencyTimeline.tsx`** — a
  horizontal Recharts range-bar Gantt (`layout="vertical"`, each bar the
  `[startOffsetDays, endOffsetDays + 1]` span from `rangeStart`), wrapped
  `aria-hidden` and paired with an accessible **"Scheduled projects"**
  table (Project / Start / End). Below it a **"Blocking relationships"**
  table (Blocking project / *blocks* / Blocked project / on-timeline
  marker), and — when any exist — the **"Unscheduled projects"** table
  (Project / Status / Missing). Recharts is already a dependency
  (`recharts@^3.10.1`, used by three existing charts); no new library was
  added or needed.
- **`PrioritizationOverviewPage.tsx`** — one new "Dependency timeline"
  `Card` after the existing "Dependency graph" card, composing the two
  existing `QueryBoundary`-wrapped queries. No new route, no new nav
  entry.

### Empty / edge states

| State | Behaviour |
|---|---|
| No projects at all | `EmptyState` "No projects yet." |
| Projects exist, none scheduled | "No scheduled projects yet." message, then the Unscheduled table. Not an error. |
| Scheduled projects, no dependencies | Timeline renders normally; "No blocking relationships recorded." Not an error. |
| A `blocks` edge with an unscheduled endpoint | Shown in the relationships table with an "Involves an unscheduled project" badge; no timeline position implied for the unscheduled side. |
| An edge referencing a project not in the projects list (e.g. filtered/other data) | Rendered from the edge payload's own `*_project_name`; `both_scheduled = false`; pulls in no project row. |

## Authorization & multi-tenancy

- **No authorization or tenancy code was written or changed.** Both reads
  are already `Permission.*_READ`-gated and already scoped to the
  authenticated caller's active organization on the server
  (`membership.organization_id` / the Phase 18 dependency-graph service).
- The frontend passes **no** organization id anywhere — it consumes the
  current-session hooks (`useProjects`, `useDependencyGraph`) exactly as
  every other surface does. There is no user-controlled org selector.
- Cross-organization isolation is therefore a pre-existing backend
  guarantee, unchanged: a project or dependency from another organization
  is never in either response, so it can never reach this component. The
  utility additionally reflects *only* the projects it is handed (a unit
  test asserts an edge pointing at an unknown project id pulls in no
  row) — it cannot fabricate or cross-reference tenant data.
- The component is read-only: it issues no mutation, so there is no CSRF
  or write-permission surface to consider.

## Consequences

- **Backend:** 0 files changed. 0 new tables, 0 migrations, 0 new
  routes, 0 new permissions, 0 new roles, 0 API-contract changes.
  `docs/openapi.json` untouched (nothing to regenerate).
- **Frontend:** 3 new files
  (`utils/dependencyTimeline.ts`, `components/DependencyTimeline.tsx`,
  plus their two test files), 1 file edited
  (`views/PrioritizationOverviewPage.tsx` — 3 imports, 1 hook call, 1
  new card, docstring).
- **Tests:** +19 (10 in `utils/dependencyTimeline.test.ts`, 9 in
  `components/DependencyTimeline.test.tsx`). Frontend suite **322 → 341
  passing**, 69 → 71 files, all green. Backend suite unchanged at **1060**
  and **not re-run** — 0 backend files changed (`git status` confirms no
  `apps/api` path touched), the same convention Phases 24/25/27 followed
  for a frontend-only visualization phase.
- **Typecheck:** `tsc -b --noEmit` clean. **Build:** `tsc -b && vite
  build` succeeds (the pre-existing >500 kB chunk-size advisory is
  unrelated — Recharts has been in the bundle since Phase 24).
- **Lint:** `oxlint` **could not be run** — this environment's OS blocks
  its native binary (`An Application Control policy has blocked ...
  oxlint.win32-x64-msvc.node`) and the WASM fallback module is absent.
  This is a pre-existing tooling gap, not a code issue, and it affects
  every file in the repo equally. `prettier --check` reports the new
  files as non-conformant, but so is every existing file in
  `features/prioritization/` — `prettier` is not this repo's enforced
  gate (`oxlint` is), and the new files match the hand-style of their
  siblings deliberately rather than diverging from it. `tsc` (which
  catches the substantive class of issues) is clean.
- **Fresh-DB / migration verification:** not applicable — no model or
  migration file exists in this phase's diff.
- **Live/API verification:** no backend behaviour changed, so no endpoint
  or route was verified live. The two `GET` responses this feature
  consumes were already live-verified in their own phases (Phase 3 /
  Phase 18) and are byte-for-byte unchanged here; the unit tests directly
  assert the "copied verbatim, never fabricated" property.
- **Browser verification:** **not performed** — no browser-automation
  tool is available in this environment (the same disclosed limitation as
  every prior frontend phase). Verification was unit/component-test level
  (19 new tests) and build-level only.
- **Technical debt introduced:** none. No new abstraction, no new
  dependency, no duplicated logic — the util/component/table shape mirrors
  `buildWsjfBreakdown` / `WsjfBreakdownChart` and `ProjectDemandTimeline`.

### Known limitations

- The Gantt bars are not connected by drawn arrows between predecessor
  and successor; the `blocks` relationships are conveyed by the adjacent
  accessible table instead. Drawing positioned SVG arrows over Recharts
  internal coordinates would be fragile and is not required to answer
  "does A block B" (CLAUDE.md §29: no decorative complexity).
- No schedule-consistency signal (a `blocks` edge whose endpoints'
  dates contradict the blocking order) — deliberately excluded (see
  Decision); a future phase could add it as an explicit, named rule.
- The timeline shows every scheduled project in the organization, not a
  framework- or selection-scoped subset. There is no project filter on
  this card yet (consistent with the existing org-wide Dependency Graph
  table beside it).
- Against the current demo seed (`scripts/seed_demo_data.py`), **no**
  project has dates, so the timeline renders its "No scheduled projects
  yet." state until a user sets project dates — expected, not a defect.

### Deferred, not dropped

- **Capacity vs. Priority matrix** and **Risk vs. Value quadrant** — the
  two remaining PRD §15 visualizations, each still blocked on a genuine
  product decision (see Context). Not started.
- **Scenario snapshots** — still blocked on the `Scenario` hard-delete
  lifecycle decision (`app/services/scenario.py::delete` still
  hard-deletes; reconfirmed by the Phase 39 audit).
- **Rank-over-time trend variant** — a Phase 24 product decision to
  decline, not a deferral; not re-opened.
- External integrations, SSO/OAuth, billing, org hierarchies, Chrome
  extension — unchanged, still explicitly deferred (CLAUDE.md §§22/23/32).

### Recommended next phase

Reassess the roadmap rather than reflexively building the next PRD
visualization. Capacity-vs-Priority and Risk-vs-Value both still require a
product decision this project should make deliberately (per its own
established practice — ask, don't assume), not a definition invented to
keep the phase number moving. Candidates genuinely ready without a new
decision are thinner now; the membership/user-management UI slices are
done (Phases 28–34), so a fresh audit is the honest next step.

## Confirmation

Phase 41 was **not** started. Nothing in this phase was committed or
pushed.
