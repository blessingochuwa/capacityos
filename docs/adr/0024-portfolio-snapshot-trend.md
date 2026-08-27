# ADR 0024: Phase 24 — multi-snapshot portfolio trend visualization

- **Status:** Accepted
- **Date:** 2026-08-27

## Context

Phase 23 (ADR 0023) resolved the other item Phase 22 had named as its own
still-open remainder (an AI explanation of a snapshot comparison), leaving
one item still named across ADRs 0021–0023 but never actually specified
anywhere: "a multi-snapshot trend chart beyond a two-point diff."

Per the phase brief's explicit audit-first instruction, the repository was
audited before any code was written: CLAUDE.md (§§4, 21, 31, 39
especially), `docs/roadmap.md`, `docs/architecture.md`,
`docs/domain-concepts.md`, every ADR through 0023,
`docs/PRD-phase-17-prioritization.md`, the complete Phase 21 Portfolio
Snapshot implementation, the complete Phase 22 snapshot-comparison
implementation, the complete Phase 23 AI-explanation implementation, the
existing prioritization ranking/scoring services, every existing frontend
prioritization component, `apps/web/package.json` (confirming
`recharts@^3.10.1` is already an approved, installed dependency, used
today in `features/capacity/components/{DailyCapacityTimeline,
ProjectDemandTimeline}.tsx`), and the existing authorization/organization-
scoping/testing/frontend conventions this phase would need to follow.

**A materially important finding**: the audit discovered that "the five
remaining Recharts visualizations" the PRD's own §15 actually named are
Priority-vs-Effort scatter, Capacity-vs-Priority matrix, Risk-vs-Value
quadrant, a WSJF breakdown stacked bar, and a dependency timeline — a
multi-snapshot trend chart is **not** one of them. It appears nowhere in
the original PRD; it was only ever named, with no defined semantics, in
ADR 0021's, 0022's, and 0023's own "deferred, not dropped" lists as a
natural extension of Phase 21/22, never as a specified deliverable. This
matters directly under CLAUDE.md §21's "AI must not invent... business
priority" and §31's "identify assumptions and risks" — while this is a
deterministic feature rather than an AI one, the same discipline applies:
undefined product semantics must not be silently invented.

## Decision: one blocking product question, not a guess

The audit found several sub-questions inferable with high confidence
directly from existing precedent, requiring no decision:

- **Same-framework-only trending.** ADR 0022 already established that "a
  RICE score and a WSJF score aren't comparable numbers" for a two-way
  diff; the identical reasoning extends to any N-way trend with no new
  argument needed.
- **X-axis = time (`taken_at`).** The only axis "trend" can sensibly mean,
  and the field Phase 21 already froze on every snapshot for exactly this
  purpose.
- **Missing/entering/leaving projects represented as gaps, never
  fabricated.** Directly required by the codebase's consistent "derive,
  never invent" discipline (CLAUDE.md §21, and `compare_snapshot_entries`'s
  own precedent of never treating an absent entry as a zero).

One question remained genuinely open and consequential enough to change
the shape of the whole feature: **what does the Y-axis plot?**
`app/domain/prioritization.py::calculate_moscow_result` confirms a MoSCoW
score is *never* numeric (`score=None` always — only a category), and
`rank_priority_results` confirms a MoSCoW result's `rank` is *always*
`None` too (ranked last, unranked, by construction). This makes "score
over time," "rank over time," and "both" three materially different
features, not a styling choice:

- **Score** answers "is this project's underlying priority strengthening
  or weakening?" — usable only for numeric frameworks (RICE/ICE/WSJF/
  Weighted); a MoSCoW framework has no numeric score to plot at all.
- **Rank** answers "is this project moving up/down the queue?" — but ADR
  0022 already flagged, for the two-point diff, that a rank change can be
  caused entirely by *another* project entering above it, not by this
  project's own score moving — a rank trend risks conflating "this project
  changed" with "the portfolio around it changed."
- **Both** is a strict superset requiring a UI toggle, not a smaller
  feature than either alone.

Per the phase brief's explicit instruction not to invent behavior merely
to keep moving, this was presented to the user as a blocking question with
these three concrete options and their trade-offs, before any code was
written. **The user selected Score over time.**

## Decisions

### Scope reduction: frontend-only, zero backend changes

The audit's second material finding: `GET /api/v1/prioritization/snapshots`
(Phase 21, unchanged since) already returns every selected snapshot's full
`entries` array — `project_id`, `project_name`, `score`, `rank`,
`missing_criteria`, `breakdown`, `category` — plus the snapshot's own
`taken_at`. This is already sufficient to build a per-project score-over-
time series with no additional data. Per the phase brief's own explicit
preference ("a read-only backend/API extension only if the existing API
cannot efficiently provide the required data") and CLAUDE.md §31's
"implement the smallest complete slice," **no new backend endpoint, model,
or migration was added.** This is a smaller slice than even a single new
API route — the entire feature is a pure client-side reshaping of data the
page already fetches via the existing, unchanged `usePortfolioSnapshots`
hook.

### A pure, testable utility function — not inline component logic

`features/prioritization/utils/snapshotTrend.ts::buildSnapshotTrend`
mirrors `app/domain/portfolio_snapshot.py::compare_snapshot_entries`'s own
discipline, translated to the frontend: a pure function, independently
unit-tested, that never recomputes a score/rank/category and never
fabricates a value for a snapshot where a project has none. CLAUDE.md §6
("complex business calculations do not belong in React components")
motivated keeping this reshaping logic out of the component itself, even
though it is presentational data-pivoting rather than a business
calculation (no capacity/priority math, no threshold/scoring logic) — the
existing `features/{capacity,import-export,insights,scenarios}/utils/`
convention was followed directly rather than inventing a new one, and
`features/prioritization/utils/` did not exist before this phase.

### Duplicate selection, missing projects, and immutability

`buildSnapshotTrend` dedupes by snapshot id (a repeated/duplicate
selection collapses to one point, never double-counted), sorts
chronologically by `taken_at` regardless of input order, and only
considers a project "trendable" if it has a numeric score in at least one
selected snapshot — a MoSCoW-only selection (or any selection where every
entry's score happens to be null) naturally produces zero trendable
projects, which the component renders as an explanatory empty state rather
than an invented type check. A project's `project_name` is taken from the
chronologically *latest* snapshot that includes it, matching
`compare_snapshot_entries`'s own "prefer the `to` side" precedent for a
project renamed between captures. The function reads its input snapshots
and never mutates them — verified directly by a dedicated unit test
(`never mutates the snapshots it was given`, deep-equality before/after).

### Chart + accessible table pairing, not chart-only

`PortfolioSnapshotTrendChart` follows the exact "chart above, accessible
table below, both driven by the same already-fetched data" precedent
`ProjectDemandTimeline` already established — CLAUDE.md §29's "never rely
on colour alone to communicate state" is satisfied structurally: every
line has a legend label, a tooltip name, and a table column, not merely a
distinct colour. A snapshot's selection uses plain checkboxes (no new UI
primitive) since no multi-select control exists anywhere in this codebase
yet, and a checkbox is a smaller addition than inventing one. `Recharts`'s
`connectNulls={false}` (the default) was set explicitly and verified in a
test — a gap in a project's presence is drawn as a gap, never
interpolated.

### No new authorization, no new tenancy boundary

Because zero backend surface changed, there is no new permission to gate
and no new cross-organization attack surface to test: the feature can only
ever display snapshots the existing, unchanged, organization-scoped
`GET /api/v1/prioritization/snapshots?framework_id=` already returned to
`usePortfolioSnapshots` — the same `Permission.PRIORITIZATION_READ` gate
and organization-scoped repository Phase 21 already established. The data
integrity requirements the phase brief named (unauthenticated access,
organization isolation, unknown snapshot ids, cross-org snapshot ids) are
already covered by Phase 21/22's own existing test suite for that
unmodified endpoint; this phase introduces no new instance of any of them
to test, and re-running that suite (below) confirms it is still
unaffected. "No accidental call to the live scoring engine" and "no
mutation of `PortfolioSnapshot` records" are true by construction — the
frontend utility performs no HTTP writes and the backend was not touched
at all.

## Consequences

- 0 new tables, 0 migrations, 0 new permissions, 0 backend files touched.
  Verified: `git diff --stat` against `apps/api/` is empty for this
  phase; the full backend suite (963 tests) and `ruff`/`pyright` (strict)
  were re-run as a regression check and are unaffected.
- New frontend modules: `features/prioritization/utils/snapshotTrend.ts`
  (+`buildSnapshotTrend`, +`SnapshotTrendProject`, +`SnapshotTrendRow`,
  +`SnapshotTrendData`), `features/prioritization/components/
  PortfolioSnapshotTrendChart.tsx`. Extended:
  `features/prioritization/views/PrioritizationOverviewPage.tsx` (renders
  `PortfolioSnapshotTrendChart` inside the existing "Portfolio snapshots"
  card, below the Phase 22 comparison section).
- Frontend: +11 tests (8 in `utils/snapshotTrend.test.ts` — chronological
  sorting regardless of input order, per-snapshot score plotting,
  duplicate-selection collapse, project entering/leaving as gaps, a
  MoSCoW/no-numeric-score selection producing zero trendable projects,
  project-name preference on rename, and non-mutation of the input; 3 in
  `components/PortfolioSnapshotTrendChart.test.tsx` — the "select at least
  2" prompt, the rendered trend table once 2 snapshots are selected, and
  the explanatory empty state for an all-MoSCoW selection) — 234 total,
  all passing. `oxlint`/`tsc -b --noEmit` clean (the same 2 pre-existing,
  unrelated `AuthContext.tsx` warnings as every prior phase). Production
  build succeeds.
- Fresh-database/migration verification: not applicable — no model or
  migration file was touched this phase.
- Live/API verification: not performed as a new check — no backend
  behavior changed, so there is no new endpoint or route to verify live.
  The `GET /api/v1/prioritization/snapshots` data this feature consumes
  was already live-verified in Phase 21's and Phase 22's own audits and is
  byte-for-byte unchanged here; this phase's own frontend unit tests
  directly assert the "frozen value, never recalculated, never mutated"
  property the phase brief asked to verify.
- Browser verification: not performed — no browser automation tool is
  available in this environment (the same disclosed limitation as every
  prior phase). Verification for this phase was API-shape-level (via the
  unchanged, already-live-verified snapshot endpoint), unit/component-test
  level (11 new tests, including duplicate/missing/immutability cases),
  and build-level (`tsc -b`, `vite build`) only — no interactive UI
  walkthrough confirms the chart actually renders correctly for a human
  eye.
- **Deferred, not dropped**: the five Recharts visualizations the PRD's
  own §15 actually named (Priority-vs-Effort scatter, Capacity-vs-Priority
  matrix, Risk-vs-Value quadrant, WSJF breakdown, dependency timeline); a
  rank-over-time or toggleable score/rank variant of this same trend chart
  (audited and explicitly not selected — see the blocking-question
  Decision above); an AI interpretation of the Phase 20 scenario
  comparison; a snapshot of a scenario's hypothetical ranking (still
  blocked on a `Scenario` hard-delete lifecycle decision, per ADR 0022's
  Context); Risk/Stakeholder/Prioritization/`ProjectDependency`/
  `PortfolioSnapshot` import/export registration; a membership/
  user-management UI.
- **Residual risk**: none newly introduced. No backend behavior, table,
  migration, permission, or API contract changed at all this phase — this
  is a purely additive, read-only frontend reshaping of data every prior
  phase already made available and already authorized correctly.

## Confirmation

Phase 25 was **not** started. Nothing in this phase was committed.
