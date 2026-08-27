# ADR 0027: Phase 27 — Priority vs. Effort scatter visualization

- **Status:** Accepted
- **Date:** 2026-08-27

## Context

Phase 26 (ADR 0026) resolved the AI interpretation of the Phase 20
scenario-vs-baseline comparison but did not select what Phase 27 should
be. Per the phase brief's explicit audit-first instruction, the
repository was audited before any code was written: CLAUDE.md
(§§4, 21, 31, 39), `docs/roadmap.md`, `docs/architecture.md`,
`docs/domain-concepts.md`, every ADR through 0026,
`docs/PRD-phase-17-prioritization.md`, the complete Phase 17-26
implementation, the Scenario model/operations/workspace/comparison/
delete lifecycle, the complete prioritization frameworks/scoring/
ranking/snapshot/comparison/trend/WSJF-breakdown/AI-explanation
capabilities, the Phase 6 import/export infrastructure and
`ImportEntityType`, the organization/membership API and frontend
surfaces, existing Recharts usage, and existing authorization/
organization-scoping/testing/factory conventions.

## Candidates re-audited from Phase 26's own deferred list

Per the phase brief's explicit instruction not to assume a previously
deferred item is still blocked without checking current code, each
candidate was re-verified directly:

- **Scenario snapshots** — `ScenarioService.delete`
  (`app/services/scenario.py`) still performs a genuine hard delete
  (unchanged since the Phase 22/23/24/25/26 audits). The "what happens
  to a scenario snapshot when its scenario is deleted" product decision
  is **still unresolved**.
- **Import/Export registration** — `ImportEntityType`
  (`app/models/enums.py`) still has exactly the same 10 members, none
  Risk/Stakeholder/Prioritization/`ProjectDependency`/`PortfolioSnapshot`.
  The missing-natural-identity-key gap is **still unresolved**.
- **A membership/user-management UI** — `app/api/v1/organizations.py`
  still exposes the same 10 routes (create/list/get/update
  organization, add/list/update/revoke membership,
  switch-organization). Still fully backend-ready, still a materially
  larger multi-flow vertical slice than a single feature — consistently
  deferred for size reasons across the Phase 22, 25, and 26 audits, not
  for any missing capability.
- **A rank-over-time trend variant** — not re-litigated: this was an
  explicit product decision Phase 24 already made (a rank trend
  conflates a project's own change with the portfolio around it, and a
  MoSCoW result's rank is always null), not merely a deferral pending
  one. Re-opening it without new information would be re-deciding a
  settled call, not auditing readiness.
- **The remaining four PRD §15 visualizations** — re-evaluated
  individually:
  - **Capacity-vs-Priority matrix** — still genuinely blocked. "Capacity"
    is a Person/Team-level concept (Phase 2 engine); `Project` has no
    capacity field or derivable single number, and no specification
    anywhere defines which people/period/aggregation "a project's
    capacity" would mean. No code changed in Phases 24-26 that would
    resolve this.
  - **Risk-vs-Value quadrant** — still genuinely blocked. `Risk` is a
    project-scoped *set* (zero to many rows per project, each with its
    own categorical probability/impact), not a single value; no
    aggregation rule is specified, and "Value" is not a defined term
    anywhere either.
  - **Dependency timeline** — still genuinely blocked.
    `ProjectDependency` (`app/models/project_dependency.py`) still has
    only `created_at`; no date or duration field exists to plot a
    timeline against.
  - **Priority-vs-Effort scatter** — **now buildable, no blocking
    question needed.** `app/domain/prioritization.py::RICE_CRITERION_KEYS`
    names its effort criterion literally `"effort"`;
    `WSJF_CRITERION_KEYS` names the structurally analogous denominator
    `"job_size"` — the PRD's own §5.1 table already lists both formulas
    as `(...) / <divisor>`, so treating these as the same axis concept
    for RICE and WSJF is grounded in existing code and the PRD's own
    table, not invented. `calculate_ice_score`
    (`(Impact + Confidence + Ease) / 3`) confirms ICE has **no**
    effort-like denominator at all — it is a plain average, never
    divided by anything — so ICE is excluded, not guessed at. Weighted
    Scoring's criteria are fully organization-defined with no reliable
    "effort" key, so it is excluded too, for the same reason.

## Decision: Priority vs. Effort scatter, no blocking question needed

**Selected.** This is the only remaining PRD visualization with no
open product decision: RICE and WSJF (and only these two) have a
code-defined effort-like criterion, and every value the chart needs
(`score`, `breakdown.effort`/`breakdown.job_size`) is already returned
verbatim by the unchanged Phase 17 `GET /api/v1/prioritization/portfolio`
response — the same data source `WsjfBreakdownChart` (Phase 25) already
consumes. Per the phase brief's own instruction ("do not ask unnecessary
questions when the repository already determines the answer"), no
blocking question was raised.

### Y-axis convention: score, following established product-management practice, not an invention

"Priority" (Y-axis) is each project's already-computed score, matching
every prior visualization's own treatment of "priority" (`PortfolioTable`,
`PortfolioSnapshotTrendChart`, `WsjfBreakdownChart` all already use
`score` this way). Effort-on-X/value-on-Y is the standard convention for
an impact-vs-effort prioritization scatter — not something invented for
this phase, and consistent with CLAUDE.md §18's own prioritization
philosophy (RICE/WSJF are both explicitly value-divided-by-effort
formulas).

### No quadrant lines, no "quick win" threshold

The chart plots only the raw facts — no median-split lines, no fixed
threshold separating "quick wins" from "big bets." No such boundary is
defined anywhere in this codebase, and CLAUDE.md §17/§29 are explicit
that inventing a magnitude threshold *for display* is exactly the false
precision this project avoids everywhere else (Phase 5's Insights
pipeline has exactly one backend-owned threshold in the entire codebase,
`LOW_CAPACITY`, and every other signal fires on a fact or existence
condition, never an invented magnitude judgment). This chart follows
that same discipline: a plain scatter of already-computed facts, not a
judgment.

### Zero backend changes, reusing the Phase 25 pattern exactly

No new backend endpoint, model, or migration — `GET
/api/v1/prioritization/portfolio` already returns everything needed.
`features/prioritization/utils/priorityEffortScatter.ts::buildPriorityEffortScatter`
is a pure, unit-tested frontend function (mirroring
`buildWsjfBreakdown`'s own discipline exactly): it copies `score` and the
relevant effort-criterion value verbatim, never recomputing anything,
and excludes any project without a complete score for the resolved
effort criterion rather than plotting a fabricated zero. Framework types
with no effort criterion return an empty point list rather than a
runtime error.

### Frontend: extends the existing Portfolio priority board, no new page

`PriorityEffortScatterChart` (chart + accessible table, matching
`WsjfBreakdownChart`'s/`ProjectDemandTimeline`'s established pairing) was
added inside the existing "Portfolio priority board" card in
`PrioritizationOverviewPage`, gated on
`selectedFramework?.framework_type === 'rice' || 'wsjf'` — the same
"gate in the parent by framework type" pattern `WsjfBreakdownChart`
already established, placed above the WSJF-only breakdown section since
it applies to a broader set of frameworks. No new route, no new
navigation entry.

## Consequences

- 0 new tables, 0 migrations, 0 new permissions, 0 backend files
  touched. Verified: `git diff --stat` against `apps/api/` is empty for
  this phase; the full backend suite (975 tests) and `ruff`/`pyright`
  (strict) were re-run as a regression check and are unaffected.
- New frontend modules:
  `features/prioritization/utils/priorityEffortScatter.ts`
  (+`buildPriorityEffortScatter`, +`PriorityEffortPoint`),
  `features/prioritization/components/PriorityEffortScatterChart.tsx`.
  Extended: `features/prioritization/views/PrioritizationOverviewPage.tsx`
  (renders `PriorityEffortScatterChart` inside the existing "Portfolio
  priority board" card).
- Frontend: +8 tests (5 in `utils/priorityEffortScatter.test.ts` —
  RICE's `effort` key, WSJF's `job_size` key, exclusion for
  ICE/Weighted/MoSCoW, exclusion of an incomplete score, multi-project
  inclusion; 3 in `components/PriorityEffortScatterChart.test.tsx` — the
  empty state for a framework with no effort criterion, the rendered
  table for a RICE project, and for a WSJF project) — 249 total, all
  passing. `oxlint`/`tsc -b --noEmit` clean (the same 2 pre-existing,
  unrelated `AuthContext.tsx` warnings as every prior phase). Production
  build succeeds.
- Fresh-database/migration verification: not applicable — no model or
  migration file was touched this phase.
- Live/API verification: not performed as a new check — no backend
  behavior changed, so there is no new endpoint or route to verify live.
  The `GET /api/v1/prioritization/portfolio` data this feature consumes
  was already live-verified in Phase 17's own audit and is byte-for-byte
  unchanged here; this phase's own frontend unit tests directly assert
  the "copied verbatim, never recomputed" property.
- Browser verification: not performed — no browser automation tool is
  available in this environment (the same disclosed limitation as every
  prior phase). Verification for this phase was unit/component-test
  level (8 new tests) and build-level (`tsc -b`, `vite build`) only.
- **Technical debt introduced**: none. No new abstraction, no
  duplicated logic — the utility/component/table pattern mirrors
  `buildWsjfBreakdown`/`WsjfBreakdownChart` exactly.
- **Deferred, not dropped**: the remaining three PRD visualizations
  (Capacity-vs-Priority matrix, Risk-vs-Value quadrant, dependency
  timeline — all three still genuinely blocked, reconfirmed directly
  against current code); a membership/user-management frontend
  (re-confirmed fully backend-ready, not selected for size reasons this
  phase either); Scenario snapshots (still blocked on the `Scenario`
  hard-delete lifecycle decision); Risk/Stakeholder/Prioritization/
  `ProjectDependency`/`PortfolioSnapshot` Import/Export registration
  (still blocked on a missing natural identity key); a rank-over-time
  trend variant (already explicitly declined, not re-litigated).
- **Residual risk**: none newly introduced. No backend behavior, table,
  migration, permission, or API contract changed at all this phase —
  this is a purely additive, read-only frontend reshaping of data every
  prior phase already made available and already authorized correctly.

## Confirmation

Phase 28 was **not** started. Nothing in this phase was committed.
