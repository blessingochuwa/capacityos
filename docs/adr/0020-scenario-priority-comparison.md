# ADR 0020: Phase 20 — scenario-vs-baseline prioritization comparison

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

Phase 19 (ADR 0019) explicitly named scenario-vs-baseline ranking comparison
as requiring a genuine product decision before it could be built: Scenario
(Phase 4) has no domain-model relationship to Prioritization (Phases 17-19)
today — none of the 8 `ScenarioOperationType` values can touch a
`ProjectPriorityCriterionValue` or `ProjectPriorityScore.category`, and no
criterion (RICE's Effort, WSJF's Job Size, etc.) is derived from allocation/
capacity data anywhere in the codebase. Per the phase brief's explicit
instruction not to let implementation guess this, the repository (CLAUDE.md,
`docs/roadmap.md`, `docs/architecture.md`, `docs/domain-concepts.md`, every
ADR through 0019, the complete Phase 4 Scenario implementation, and the
complete Phase 17-19 prioritization implementation, including
`docs/PRD-phase-17-prioritization.md` §8's own original — and, on inspection,
unrealized — proposal) was audited first, and the resulting options were
presented to the user via a blocking question rather than chosen silently.

## Decisions

### The product decision: explicit, scenario-scoped criterion overrides

The user selected **explicit scenario-scoped criterion overrides** over the
two alternatives audited and presented (an ad-hoc, non-persisted "hypothetical
score preview" API; deferring the feature entirely). A Scenario can declare
"in this hypothetical, Project X's Effort is 6 instead of 4" (or a different
MoSCoW category) — a human-declared override, never auto-derived from
allocation/capacity data. The PRD's own §8 language ("compute the portfolio
ranking twice... against two different fact sets") presupposed criterion
values came from a fact set that could differ between baseline and scenario;
as actually built in Phases 17-18, no such fact set exists — this phase
creates the first one, deliberately, as its own explicit, scenario-scoped
concept, never by retrofitting an implicit connection into
`ProjectPriorityCriterionValue` itself.

A fourth option — auto-deriving a criterion from a project's scenario
allocation/demand data — was audited and explicitly ruled out as not
presentable at all: no such mapping is specified anywhere (which criterion,
which formula), and inventing one now would be exactly the "invent a product
rule for technical convenience" the phase brief forbade.

### `ScenarioPriorityOverride`: its own table, not a `ScenarioOperation`

`ScenarioPriorityOverride` (organization_id, scenario_id, project_id,
framework_id, values: JSON dict, category) is a new, standalone table —
deliberately **not** a ninth `ScenarioOperationType`. The existing 8 types are
all capacity/allocation concerns, replayed in creation-sequence order through
`PlanningState` (`app/domain/scenario.py`); a prioritization override has no
ordering semantics at all (it's a value, not a delta-in-a-sequence) and never
touches capacity, so extending that engine or its CHECK-constrained
`operation_type` vocabulary would have been the wrong shape for a genuinely
different concern. One row per (scenario, project, framework) — matching
`ProjectPriorityScore`'s own one-row-per-(project,framework) uniqueness
exactly, just scenario-scoped instead of persisted-baseline-scoped. A second
`POST` for the same triple **replaces** the first (an upsert) rather than
requiring a separate PATCH endpoint — the smallest mutation surface for a
row this simple.

### The baseline is never mutated — merged in memory, at read time only

An override is read **alongside** the real, persisted `ProjectPriorityScore`
and never written back to it. `ScenarioPriorityService.compare` builds each
project's baseline `values` dict via
`ProjectPriorityScoreService.values_dict` (unchanged, reused verbatim), then
merges the scenario's override values on top **in memory** to build the
scenario-side input — a criterion the override doesn't mention still carries
its real baseline value, never blank. Both baseline and scenario results are
computed through the exact same
`ProjectPriorityScoreService.compute_result` → `calculate_priority_score`
path — reusing the RICE/ICE/WSJF/Weighted/MoSCoW engine Phases 17-18 already
built, never a second scoring engine. Verified directly: a live golden-path
walkthrough re-read the project's persisted score after setting and comparing
against an override and confirmed it was byte-for-byte unchanged.

### Ranking is now one shared function, not two copies of the same sort

`ProjectPriorityScoreService.rank_portfolio`'s inline sort
(`entries.sort(key=...)`) was extracted to
`app/domain/prioritization.py::rank_priority_results` — a small, generic,
pure function (`list[tuple[K, PriorityScoreResult]] -> list[tuple[K,
PriorityScoreResult, int | None]]`) — and `rank_portfolio` now calls it
instead of sorting inline. The scenario comparison calls the identical
function twice (once for the baseline entry set, once for the scenario entry
set), so a project's rank can never disagree between the live portfolio board
and this comparison, and the "missing/categorical score ranks last, unranked"
rule (already established in Phase 17/18) is inherited automatically rather
than re-implemented. `ProjectPriorityScoreService._validate_category` was
similarly promoted to a shared pure function,
`validate_category_for_framework_type`, reused by both services. Both
refactors are behavior-preserving — the full pre-existing prioritization test
suite (101 tests) was re-run immediately after each and passed unchanged
before any Phase 20 code was written on top of them.

### `changed` is computed from results, never from "an override exists"

`ScenarioPriorityComparisonItem.changed` compares
`(baseline_result.score, baseline_result.category, baseline_rank)` against
the same triple for the scenario side — never inferred from whether an
override row exists. A no-op override (one whose value happens to exactly
match the baseline) correctly reports `changed: false`; a project with no
override at all whose rank still moves (because a sibling project's override
displaced it) correctly reports `changed: true`. `has_changes` at the
comparison's top level is `any(item.changed for item in items)` — computed
the same way, so a scenario with no overrides (or overrides that don't move
anything) explicitly reports "no prioritization change" rather than omitting
the field or leaving the caller to infer it, per the phase brief's explicit
requirement. Both cases are covered by dedicated tests (`test_comparison_
no_op_override_reports_no_change`, `test_comparison_with_no_overrides_and_
no_baseline_scores_reports_no_change`).

### Authorization: SCENARIO_READ/WRITE/DELETE, deliberately not PRIORITIZATION_SCORE

Every new route is gated by the *existing* `SCENARIO_READ`/`SCENARIO_WRITE`/
`SCENARIO_DELETE` permissions — role-only, no `ProjectAccessGrant` — matching
every other Scenario mutation exactly (Phase 16 deliberately kept Scenario
role-only). This was a deliberate choice, not an oversight: the action being
authorized is "editing a hypothetical scenario," not "editing this project's
real score," so `PRIORITIZATION_SCORE`'s grant-scoping (which exists
specifically to scope *real* score mutations to projects a Manager is granted
access to) doesn't apply here. A Manager can create/delete an override
against any project in their organization without a grant on that
project — proven by a dedicated test
(`test_manager_can_create_and_delete_override_without_any_project_grant`)
that exists specifically to make this deliberate asymmetry visible rather
than accidentally discovered later. Organization membership remains the hard
boundary throughout: `scenario_id`, `project_id`, and `framework_id` are each
independently resolved through their own org-scoped repository before an
override is ever written or a comparison ever computed — six dedicated
cross-organization tests (scenario/project/framework referenced from another
org, on both the override-create and comparison-read paths) all 404, never
403 or 500.

### API: extends the existing `/api/v1/scenarios` router, no new top-level resource

Four new routes, all nested under the existing scenario resource, matching
its established shape (`/{scenario_id}/operations`,
`/{scenario_id}/comparison`) exactly:

```text
POST   /api/v1/scenarios/{scenario_id}/priority-overrides
GET    /api/v1/scenarios/{scenario_id}/priority-overrides
DELETE /api/v1/scenarios/{scenario_id}/priority-overrides/{override_id}
GET    /api/v1/scenarios/{scenario_id}/priority-comparison?framework_id=
```

No new top-level router, no duplicate route family under
`/api/v1/prioritization/*`.

### AI: none in this phase

No AI capability was added. The phase brief was explicit that AI may only
interpret an established deterministic comparison, never be its source — and
since establishing that deterministic comparison was this phase's entire
scope, an AI explanation of it (mirroring `explain-priority`'s own pattern)
is left for a future phase to consider once this deterministic base has been
used and validated, not bundled in speculatively.

### Frontend: extends the existing Scenario workspace, no new page

`PriorityOverrideForm`/`PriorityOverrideList`/`PriorityComparisonTable` are
new sections added to the existing `ScenarioWorkspacePage` — no new route, no
new navigation entry. The comparison table always shows Baseline and
Scenario as two explicit, adjacent column groups (rank/score/status each),
mirroring `ComparisonTable`'s established "Baseline → Scenario → Change"
shape from Phase 4, plus a `Change`/`No change` column per project and a
scenario-level banner stating explicitly whether anything changed. No new
charting dependency (CLAUDE.md §29) — this is a table, matching Phase 18's
own Dependency Graph precedent for the same reasoning.

## Consequences

- 1 new table (`scenario_priority_overrides`), 1 migration, 0 new
  permissions, 2 new `AuditAction` members
  (`scenario_priority_override.create/delete`). 0 changes to any existing
  permission's grant set.
- New backend modules: `app/models/scenario_priority_override.py`,
  `app/repositories/scenario_priority_override.py`,
  `app/services/scenario_priority.py`, `app/schemas/scenario_priority.py`.
  Extended: `app/domain/prioritization.py` (+`rank_priority_results`,
  +`validate_category_for_framework_type`),
  `app/services/project_priority_score.py` (+`compute_result`,
  +`values_dict`, `rank_portfolio` refactored to call
  `rank_priority_results`), `app/api/v1/prioritization.py` (rank-tuple
  unpacking updated to match), `app/api/v1/scenarios.py` (+4 routes),
  `app/models/enums.py` (+2 `AuditAction` members), `app/models/__init__.py`.
- New frontend modules:
  `features/scenarios/{types/scenarioPriority,api additions,
  hooks/useScenarioPriorityOverrides,hooks/useScenarioPriorityComparison,
  hooks/useScenarioPriorityOverrideMutations,
  components/PriorityOverrideForm,components/PriorityOverrideList,
  components/PriorityComparisonTable}`. Extended:
  `features/scenarios/api/scenariosApi.ts`,
  `features/scenarios/views/ScenarioWorkspacePage.tsx`,
  `test/fixtures.ts` (+3 fixture builders).
- Backend: +38 tests (7 domain, 31 API — every supported framework type
  covered: RICE, ICE, WSJF, Weighted, MoSCoW) — 916 total, all passing.
  `ruff check` and `uv run pyright` (strict) both fully clean. Fresh
  `alembic upgrade head`, `alembic current`, and an
  upgrade→downgrade→upgrade round trip all verified against a real
  file-backed database.
- Frontend: +13 tests (2 new `ScenarioWorkspacePage` tests plus 3 new
  component test files) — 215 total, all passing. `oxlint`/
  `tsc -b --noEmit` clean (the same 2 pre-existing, unrelated
  `AuthContext.tsx` warnings as every prior phase). Production build
  succeeds.
- Live verification: a real uvicorn instance was started against a
  genuinely fresh, migrated, file-backed SQLite database with a real
  Owner account bootstrapped via `scripts/create_first_owner.py`. A real
  authenticated session (cookie login, double-submit CSRF token) walked
  the full golden path over real HTTP — create project → create framework
  → score it → create scenario → set an override → list overrides → read
  the comparison (confirmed `has_changes: true`, correct baseline/scenario
  scores) → confirm the persisted baseline score was untouched → delete
  the override → re-read the comparison (confirmed `has_changes: false`)
  — plus confirmed unauthenticated (401), missing-CSRF (403), and
  unknown-scenario (404, not 403/500) rejections, real `AuditEvent` rows
  for both the create and delete, and a log scan confirming no password or
  secret value was ever written to the server log. Cross-organization
  IDOR was verified via the automated test suite (6 dedicated tests
  against a real ASGI app and a real SQLite database) rather than
  repeated manually in this session. No browser or interactive UI
  walkthrough was performed — no such tool is available in this
  environment (the same disclosed limitation as every prior phase).
- **Deferred, not dropped**: `PortfolioSnapshot`; the five remaining
  Recharts visualizations; AI interpretation of this comparison (left for
  a future phase, per the brief's own instruction not to bundle AI in
  speculatively).
- **Residual risk**: none newly introduced. No behavior change to any
  existing phase's authorization, audit, capacity, risk, or Phase 17-19
  prioritization/AI behavior — the `rank_portfolio`/`_validate_category`
  refactor is a pure extraction, verified behavior-identical by the full
  pre-existing prioritization test suite before any new code was added on
  top of it.
