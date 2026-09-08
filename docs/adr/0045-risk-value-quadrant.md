# ADR 0045: Phase 45 — Risk vs. Value quadrant

- **Status:** Accepted
- **Date:** 2026-09-08

## Context

The Risk vs. Value quadrant is the last of the five Recharts
visualizations `docs/PRD-phase-17-prioritization.md` §15 names. Every
audit from Phase 25 through Phase 41 reconfirmed it blocked, for two
independent reasons: no repository-wide definition of a project's
"Value," and no established rule for aggregating a project's 0..N `Risk`
rows into a single axis position. Phase 42 demonstrated the correct
resolution pattern for exactly this kind of blocker (Capacity vs.
Priority): when the missing product decision is supplied explicitly by
the user rather than guessed at, implementation can proceed safely. This
phase applies the same discipline.

### What was audited before implementing

- Git state: `HEAD` at `6d89015` ("Implement Phase 44 audit log action &
  resource-type filtering"), matching `origin/main` exactly (0 ahead / 0
  behind), working tree clean.
- CLAUDE.md §§4, 21, 26–40; `docs/roadmap.md`; `docs/architecture.md`;
  `docs/domain-concepts.md`; `README.md`; `docs/PRD-phase-17-prioritization.md`
  §15; ADR 0013 (Risk management — confirmed directly, not assumed, that
  no org-wide risk register exists: "every route is nested under one
  project"), ADR 0017/0018 (prioritization engine — the `score`/
  `PortfolioRankingEntry` shape this phase reuses), ADR 0025/0027/0040/0042
  (every prior audit's own "still blocked" finding, and the two most
  recent visualization precedents this phase mirrors).
- Backend, re-verified directly against current source: `app/models/project.py`
  (still no value/business-value field of any kind — only
  `name`/`description`/`status`/dates/`external_id`); `app/models/risk.py`
  (no numeric field at all — `probability`/`impact` are 3-tier enums,
  `exposure` is explicitly NOT a column, "do not create risk scores that
  imply false precision"); `app/domain/risk.py` (`calculate_risk_exposure`
  — a 3×3 lookup, never a formula; `classify_risk_signal` — the exact
  condition `exposure == "high" and status != CLOSED` this phase's Risk
  aggregation reuses verbatim; no aggregation function exists anywhere in
  this module); `app/domain/prioritization.py` (`RICE_CRITERION_KEYS`/
  `ICE_CRITERION_KEYS` have no value-like criterion at all;
  `WSJF_CRITERION_KEYS` has `business_value` as one of four components
  feeding the WSJF score, never a standalone "project value"); `app/api/v1/projects.py`
  (confirmed `GET /{project_id}/risks` is the *only* risk-read route —
  project-nested, `Permission.RISK_READ`, org-scoped via
  `RiskService.list_for_project`; `Permission.RISK_READ` confirmed inside
  `_READ_PERMISSIONS`, granted to every role).
- Frontend: the complete Phase 42 `CapacityPriorityMatrixChart`/
  `capacityPriorityMatrix.ts` (the closest, most recent precedent, reused
  structurally); `features/risks/{api/risksApi.ts, hooks/useRisks.ts,
  types/risks.ts}` (the existing per-project risk read this phase
  composes over, `RiskRead`'s `exposure` already computed server-side);
  `usePortfolio`/`PortfolioRankingEntry` (unchanged since Phase 17).

## Decision gate — Path B, then Path A

The audit reconfirmed both blockers were still genuinely open (see
Context) — Path B. A Decision Report was produced identifying the
available data, the specific ambiguity, and 2–3 concrete options for
each of Value and Risk aggregation, with implications and a
recommendation grounded in what already exists in this codebase. The
user was asked directly, via a blocking question, rather than a default
being assumed. **The user chose:**

- **Value** = the project's existing priority score under the currently
  selected framework (reusing Phase 42's exact Y-axis definition).
- **Risk** = the count of the project's open (not `closed`) Risk records
  whose derived `exposure` is `"high"`.

With both decisions supplied explicitly, Path A — implementation —
proceeded.

## Implementation

Build the Risk vs. Value matrix as a **frontend-only** feature with
**zero backend changes**, on the existing `PrioritizationOverviewPage`,
mirroring `CapacityPriorityMatrixChart`'s structure closely.

### Value axis — identical to Phase 42's, not reinvented

Each project's already-computed `score` from `GET /api/v1/prioritization/portfolio`
for the selected framework, copied verbatim, never recalculated
(CLAUDE.md §4/§21) — the exact same value Phase 42's Capacity-vs-Priority
matrix and Phase 27's Priority-vs-Effort scatter already plot.
`score === null` (incomplete numeric-framework inputs, or any
MoSCoW-scored project, which never produces a number) excludes the
project (reason `no_priority_score`) — the identical filter every other
prioritization chart in this codebase already applies.

### Risk axis — a count, never a synthesized score

`utils/riskValueMatrix.ts::countOpenHighExposureRisks` counts every
`Risk` row for a project whose `status` is not `"closed"` and whose
`exposure` is `"high"` — reusing `app/domain/risk.py::classify_risk_signal`'s
own condition for firing the existing `risk_high_exposure` Insights
signal, verbatim, rather than inventing a new judgment about what counts
as "risky." This is a plain count of an already-meaningful, already-used
condition — never a weighted sum, never a numeric coercion of the
`low`/`medium`/`high` exposure scale itself, honoring CLAUDE.md §17's
"do not create risk scores that imply false precision" the same way
every other risk-related feature in this codebase already does.

**A risk count of `0` is a real, valid plotted value, not "missing
data."** This is a deliberate, disclosed departure from Phase 42's own
capacity-axis reasoning: an empty *allocation* list was treated as
"never capacity-planned" (ambiguous intent, excluded); an empty
*qualifying-risk* list is not ambiguous — it is the same positive fact
the Insights page already expresses by simply not firing a
`risk_high_exposure` signal for that project. A project's Risk axis
value is "missing" (reason `risk_data_unavailable`) **only** when its
risk list could not be fetched at all (a genuine query failure) — the
one real unknown this axis can have.

### No bulk risk endpoint — N parallel existing per-project calls

`app/api/v1/projects.py` exposes risk reads only as
`GET /projects/{id}/risks` — ADR 0013 explicitly decided against an
org-wide risk register. `features/prioritization/hooks/useRisksForProjects.ts`
fires one such call per plotted project via TanStack Query's `useQueries`
(already part of the installed `@tanstack/react-query` package — not a
new dependency or a second data-fetching abstraction), reusing the
*exact* query key `features/risks/hooks/useRisks.ts` already uses
(`['projects', projectId, 'risks']`) so results are shared with the
standalone Risks page's cache rather than duplicated. Each individual
call is already `Permission.RISK_READ`-gated (every role) and already
organization-scoped server-side — this hook adds no authorization or
tenancy logic and accepts no organization id.

A per-project query failure does **not** produce a page-level error: it
simply omits that project from `riskCountsByProject`, so the pure
transform (`buildRiskValueMatrix`) correctly reports it as
`risk_data_unavailable` and excludes it, disclosed by name — the same
graceful, disclosed-exclusion pattern every other missing-data case in
this chart already uses, rather than one failed project blocking the
entire visualization.

### Median reference lines and quadrant classification — reapplying Phase 42's technique, deliberately

Reference lines are the median Risk count and median Value across the
currently plotted points only — never an invented threshold. A value
exactly equal to its axis's median is classified on the "low" side of
that axis, the identical tie rule Phase 42 established. This phase's own
brief explicitly warned against *silently* reusing Phase 42's median
rule "unless the existing product definition supports it" — it is
reapplied here **deliberately, not silently**: it is the only
quadrant-boundary technique this codebase has ever used for a
descriptive prioritization quadrant (the alternative precedent,
Priority-vs-Effort, deliberately drew *no* boundary at all — a plain
scatter, ADR 0027), no alternative technique was specified by the user's
decision (which addressed *what* Risk and Value mean, not *how* to draw
quadrant lines), and the brief itself frames this chart as a "quadrant"
matching Phase 42's four-region shape. Quadrant labels — "High Value /
High Risk," etc. — are purely descriptive positions, never a
recommendation or "kill/invest" judgment (CLAUDE.md §17/§29).

### Implementation shape

- **`features/prioritization/hooks/useRisksForProjects.ts`** — the
  `useQueries` wrapper described above.
- **`features/prioritization/utils/riskValueMatrix.ts`** —
  `countOpenHighExposureRisks` (pure, unit-tested) and
  `buildRiskValueMatrix(items, riskCountsByProject): RiskValueMatrixModel`
  (pure, DB-free, unit-tested), mirroring `capacityPriorityMatrix.ts`'s
  median/quadrant/exclusion structure exactly, adapted for the two new
  definitions.
- **`features/prioritization/components/RiskValueMatrixChart.tsx`** —
  owns its own data fetching (`useRisksForProjects`, since the risk data
  it needs has no bulk counterpart to fetch at the page level the way
  Phase 42's `allocationsQuery` could), shows a `LoadingState` while any
  constituent query is pending, then a Recharts `ScatterChart`
  (`aria-hidden`, two `ReferenceLine`s) paired with a plain-text
  median/count sentence, a quadrant legend, an accessible **"Risk vs.
  value matrix"** table, and — when non-empty — a disclosure sentence
  naming every excluded project and its specific reason.
- **`PrioritizationOverviewPage.tsx`** — one new block inside the
  existing "Portfolio priority board" card, immediately after the
  Capacity vs. Priority block, unconditional on framework type (Value is
  defined for every numeric framework, exactly like Phase 42 — a
  MoSCoW-only selection naturally reduces to the chart's own "nothing
  plottable" empty state rather than being hidden by a type check).

## Authorization & multi-tenancy

- **No authorization or tenancy code was written or changed.** Both data
  sources are already permission-gated (`PRIORITIZATION_READ`,
  `RISK_READ` — both granted to every role) and already scoped to the
  caller's active organization on the server.
- The frontend passes **no** organization id anywhere. `useRisksForProjects`
  accepts only project ids already drawn from the organization-scoped
  portfolio response.
- Cross-organization isolation is a pre-existing backend guarantee: a
  risk or priority score from another organization is never in either
  response, so it can never reach this component. The transform
  additionally reflects only the projects it is handed — a
  `riskCountsByProject` entry for a project id outside the supplied
  portfolio items is silently ignored (unit-tested), never surfaced as a
  phantom row.
- Read-only: no mutation, no CSRF or write-permission surface.

## Consequences

- **Backend:** 0 files changed. 0 new tables, 0 migrations, 0 new
  routes, 0 new permissions, 0 API-contract changes. `docs/openapi.json`
  untouched.
- **Frontend:** 5 new files (`hooks/useRisksForProjects.ts`,
  `utils/riskValueMatrix.ts` + test,
  `components/RiskValueMatrixChart.tsx` + test), 1 file edited
  (`views/PrioritizationOverviewPage.tsx`).
- **Tests, lint, typecheck, build:** see the Phase 45 Final Report for
  exact totals and results.
- **Browser verification:** not performed — no browser-automation tool
  is available in this environment.

### Known limitations

- Fetching N projects' risks as N parallel HTTP requests has no upper
  bound enforced client-side — for a portfolio with an unusually large
  number of scored projects, this issues one request per project rather
  than a single bulk call. This mirrors the architectural reality ADR
  0013 already established (no bulk risk endpoint exists) rather than
  introducing a new limitation; a future phase adding an org-wide risk
  listing endpoint could replace this with a single call, but building
  that endpoint was outside this phase's scope (no visualization need
  alone justifies a new backend surface per this phase's own brief).
- If every constituent risk query fails at once (e.g., a full API outage
  affecting only the risk endpoint), every project is individually
  excluded as `risk_data_unavailable` rather than the chart showing one
  consolidated error banner — a deliberate choice favoring graceful,
  per-project degradation over an all-or-nothing error state, but it
  means a total outage reads as "no data available" rather than "the
  server is down" specifically.
- No project filter or framework-type gate on this chart (matches
  Capacity-vs-Priority's own precedent) — it always reflects the entire
  portfolio currently scored under the selected framework.

### Deferred, not dropped

Every item this phase's own brief listed out of scope — PortfolioSnapshot
export/import, scenario snapshots, organization hierarchy, billing,
SSO/OAuth, external integrations, Chrome extension, PostgreSQL
concurrency, membership/account-directory redesign, USER_WRITE scoping,
capacity/allocation redesign, Audit Log redesign, import/export
architecture — untouched, none started.

## Confirmation

With this phase, every PRD §15 visualization is implemented. Phase 46
was **not** started. Nothing in this phase was committed or pushed — see
the Phase 45 Final Report for the exact git state.
