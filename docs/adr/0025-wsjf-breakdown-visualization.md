# ADR 0025: Phase 25 — WSJF breakdown visualization

- **Status:** Accepted
- **Date:** 2026-08-27

## Context

Phase 24 (ADR 0024) resolved the multi-snapshot trend chart but did not
select what Phase 25 should be. Per the phase brief's explicit
audit-first instruction, the repository was audited before any code was
written: CLAUDE.md (§§4, 21, 31, 39), `docs/roadmap.md`,
`docs/architecture.md`, `docs/domain-concepts.md`, every ADR through
0024, `docs/PRD-phase-17-prioritization.md`, the complete Phase 17-24
prioritization implementation, the complete `PortfolioSnapshot`/Phase
22/Phase 23/Phase 24 implementations, the Scenario implementation and its
delete lifecycle, Risk and Stakeholder, the Phase 6 import/export
infrastructure, the existing membership/user-management API surface
(`app/api/v1/organizations.py`), existing Recharts usage, and existing
authorization/organization-scoping/testing/migration conventions.

## Candidates found

The audit found exactly the candidates CLAUDE.md/the roadmap already
name, no more:

1. **The five Recharts visualizations the PRD's own §15 actually names**
   — Priority-vs-Effort scatter, Capacity-vs-Priority matrix,
   Risk-vs-Value quadrant, WSJF breakdown (stacked bar of the four
   inputs), and a dependency timeline.
2. **Scenario snapshots** — a snapshot of a scenario's hypothetical
   ranking.
3. **Risk/Stakeholder/Prioritization/`ProjectDependency`/
   `PortfolioSnapshot` Import/Export registration.**
4. **A membership/user-management frontend.**
5. **An AI interpretation of the Phase 20 scenario comparison** and **a
   rank-over-time variant of the Phase 24 trend chart** (both explicitly
   audited and declined in Phases 20 and 24 respectively — not
   re-litigated here).

## Evaluation

- **Scenario snapshots** — verified directly: `ScenarioService.delete`
  (`app/services/scenario.py`) still performs a genuine hard delete; the
  "what happens to a scenario snapshot when its scenario is deleted"
  product decision ADR 0022 first flagged remains **unresolved**. Not
  selectable without a blocking question.
- **Import/Export registration** — verified directly:
  `ImportEntityType` (`app/models/enums.py`) still has exactly the same
  10 members it had at the Phase 22 audit, none Risk, Stakeholder,
  Prioritization, `ProjectDependency`, or `PortfolioSnapshot`. The
  "no Person/Project-style natural identity key for CSV upsert-matching"
  gap ADR 0022 identified is **still unresolved**. Not selectable without
  a blocking question.
- **Membership/user-management UI** — genuinely viable (every backend
  route already exists, confirmed by re-reading
  `app/api/v1/organizations.py`'s full route list: create, list, get,
  update, add/list/update/revoke membership, switch-organization). But
  it is a multi-flow surface (list members, invite, change role, revoke,
  disable an account) touching security-sensitive actions the Phase 15
  last-owner invariant already guards — a materially larger vertical
  slice than a single chart, and the phase brief's own instruction for
  this candidate ("do not modify backend authorization merely to create
  a frontend page unless the audit identifies a concrete existing
  defect") only bounds *how* to build it, not its size. Not selected —
  see "What was NOT selected" below.
- **The five PRD visualizations** — per the phase brief's own instruction
  to implement ONE, not all five. Of the five, three carry real,
  undiscussed cross-domain ambiguity that would require inventing
  product semantics: Capacity-vs-Priority (what does "a project's
  capacity" mean — whose remaining capacity, over what period, aggregated
  how?), Risk-vs-Value (Risk is a project-scoped *set*, not a single
  value — which risk, or what aggregation rule, represents "the"
  project's risk?), and the dependency timeline (already audited in
  Phase 21 and found to have "no real semantics to visualize yet without
  inventing scope" — `ProjectDependency` has no dates/duration at all).
  Priority-vs-Effort has one framework-scoping wrinkle (Effort/Job Size
  only exists for RICE/WSJF, not Weighted/MoSCoW) but is otherwise
  buildable. **WSJF breakdown** has zero cross-domain ambiguity: its
  "four inputs" are `app/domain/prioritization.py::WSJF_CRITERION_KEYS`
  verbatim, already returned in full by the unchanged Phase 17
  `GET /api/v1/prioritization/portfolio` response's `breakdown` field.

## Decision: WSJF breakdown, no blocking question needed

**WSJF breakdown was selected** — the one candidate that is simultaneously
already-specified (the PRD's own §15 names it in one unambiguous line,
backed by `calculate_wsjf_score`'s own fixed, well-documented formula),
requires zero backend change (matching Phase 24's own "reuse what
already exists" precedent — `GET /api/v1/prioritization/portfolio` was
already fetched by this exact page before this phase), and carries no
open product decision of any kind. Per the phase brief's own instruction
("do not ask a question merely for confirmation when the repository
already specifies the answer"), no blocking question was raised for this
selection.

### One execution-level interpretation, not a product decision

The PRD's one-line spec ("stacked bar of the four inputs") does not
specify *how* the four values should be stacked, and a literal single
`stackId` across all four would produce a materially misleading result:
`business_value` + `time_criticality` +
`risk_reduction_opportunity_enablement` sum to a real, meaningful
quantity — SAFe's own "Cost of Delay," the WSJF numerator — but
`job_size` is the formula's *divisor*, not a fourth additive term.
Stacking it in would produce a combined bar height that is not the WSJF
score, not Cost of Delay, and not any other meaningful number — exactly
the "no false precision" / "no decorative or misleading chart" concern
CLAUDE.md §17/§29 already establish as binding, not merely stylistic.
The three additive criteria are stacked together (`stackId="cost_of_delay"`,
whose total genuinely is Cost of Delay); `job_size` is rendered as its
own adjacent bar, distinctly coloured, in the same chart. This is an
execution-quality judgment within the selected scope, not a redefinition
of what the visualization shows — all four inputs are still shown,
together, per project, exactly as specified.

### What was NOT selected, and why

- **Membership/user-management UI** — audited and confirmed
  fully backend-ready (again), but its scope (multiple CRUD flows, each
  touching Phase 15's last-owner invariant, each needing its own
  authorization/audit verification) is a materially larger vertical
  slice than one chart. Deferred, not dropped — CLAUDE.md §31's "smallest
  complete slice" favored the smaller, equally-ready candidate.
- **Scenario snapshots, Import/Export registration** — both still
  genuinely blocked on an unresolved product decision, reconfirmed
  directly against current code (see Evaluation above), not merely
  repeated from a prior ADR's claim.
- **The other four PRD visualizations** — Capacity-vs-Priority and
  Risk-vs-Value both carry real cross-domain ambiguity not specified
  anywhere; the dependency timeline is still blocked on
  `ProjectDependency` having no date/duration data (ADR 0021's own
  finding, reconfirmed unchanged); Priority-vs-Effort is buildable but
  not the smallest/cleanest of the remaining set — left for a future
  phase to select deliberately, matching this phase's own "one chart at
  a time" instruction.

## Consequences

- 0 new tables, 0 migrations, 0 new permissions, 0 backend files
  touched. Verified: `git diff --stat` against `apps/api/` is empty for
  this phase; the full backend suite (963 tests) and `ruff`/`pyright`
  (strict) were re-run as a regression check and are unaffected.
- New frontend modules: `features/prioritization/utils/wsjfBreakdown.ts`
  (+`buildWsjfBreakdown`, +`WsjfBreakdownRow`),
  `features/prioritization/components/WsjfBreakdownChart.tsx`. Extended:
  `features/prioritization/views/PrioritizationOverviewPage.tsx` (renders
  `WsjfBreakdownChart` inside the existing "Portfolio priority board"
  card, gated on `selectedFramework?.framework_type === 'wsjf'`).
- Frontend: +7 tests (4 in `utils/wsjfBreakdown.test.ts` — verbatim
  copy of the four criterion values, exclusion of an incomplete score,
  exclusion of a non-WSJF breakdown, multi-project ordering; 3 in
  `components/WsjfBreakdownChart.test.tsx` — the empty state for no
  complete WSJF score, the rendered breakdown table for a fully-scored
  project, and exclusion of a non-WSJF-framework project) — 241 total,
  all passing. `oxlint`/`tsc -b --noEmit` clean (the same 2 pre-existing,
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
  level (7 new tests) and build-level (`tsc -b`, `vite build`) only.
- **Deviations from CLAUDE.md/spec**: the PRD literally says "stacked bar
  of the four inputs"; this phase stacks three of the four (the additive
  Cost-of-Delay components) and renders `job_size` as a separate adjacent
  bar in the same chart, for the reason given above (a literal four-way
  stack would produce a misleading combined total, which CLAUDE.md §17/
  §29 already forbid). All four values are still shown, together, per
  project — this is a chart-encoding decision, not a scope change.
- **Deferred, not dropped**: the other four PRD visualizations
  (Priority-vs-Effort scatter, Capacity-vs-Priority matrix, Risk-vs-Value
  quadrant, dependency timeline); a membership/user-management frontend
  (re-confirmed fully backend-ready, not selected for size reasons this
  phase); Scenario snapshots (still blocked on the `Scenario` hard-delete
  lifecycle decision); Risk/Stakeholder/Prioritization/`ProjectDependency`/
  `PortfolioSnapshot` Import/Export registration (still blocked on a
  missing natural identity key); an AI interpretation of the Phase 20
  scenario comparison; a rank-over-time variant of the Phase 24 trend
  chart (both previously declined, not re-litigated this phase).
- **Residual risk**: none newly introduced. No backend behavior, table,
  migration, permission, or API contract changed at all this phase —
  this is a purely additive, read-only frontend reshaping of data every
  prior phase already made available and already authorized correctly.

## Confirmation

Phase 26 was **not** started. Nothing in this phase was committed.
