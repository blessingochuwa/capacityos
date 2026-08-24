# ADR 0018: Phase 18 — remaining prioritization frameworks, criteria editing, and project dependencies

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

CLAUDE.md §39 stopped naming phases at 17; `docs/roadmap.md` named the next
item only as the provisional "Phase 17b: rest of Prioritization," explicitly
flagged as unconfirmed. Per the phase brief's own explicit instruction not
to assume Phase 17b was automatically "Phase 18," the ambiguity was reported
to the user with the concrete options the roadmap actually named, rather
than guessed. The user selected "Phase 17b: rest of Prioritization" — but
that macro-scope was still too large for one slice under CLAUDE.md §31's
"smallest complete slice" principle (mirroring how Phase 17 itself was
sliced from its own PRD). A further reduction was proposed in plain text
(not a second blocking question) and implemented as this phase.

## Decisions

### Phase 18 scope: complete the framework set, editable criteria, and dependencies — not the rest of the Phase 17 PRD

Built: ICE and WSJF formulas; MoSCoW (categorical, never numeric); editing
a Weighted Scoring framework's criteria after creation (add/rename/
reweight/remove, respecting `is_editable`); `ProjectDependency`
(blocks/related/enables) with cycle detection on `blocks` edges; a
Dependency Graph frontend view. **Not** built in this phase (each a named,
not silently dropped, gap — see Consequences): `PortfolioSnapshot`,
scenario-vs-baseline ranking comparison, AI priority explanation, the
Priority Explanation Panel and Scenario Comparison frontend views, and the
five remaining Recharts visualizations named in
[docs/PRD-phase-17-prioritization.md](../PRD-phase-17-prioritization.md).

### One scoring engine, not five parallel ones

RICE, ICE, and WSJF all share the same fixed-criteria shape Phase 17
established for RICE alone — `FIXED_CRITERION_KEYS: dict[PrioritizationFrameworkType,
tuple[str, ...]]` in `app/domain/prioritization.py` is the single source of
truth both the seeding service (`_seed_fixed_criteria`, generalized from
Phase 17's RICE-only `_seed_rice_criteria`) and `calculate_priority_score`'s
dispatch consult — so a fourth "fixed-criteria" framework type would mean
adding one dict entry and one formula function, never a parallel code path.
ICE is `(Impact + Confidence + Ease) / 3` — a documented, deliberate choice
of the average convention over a product, since (unlike RICE, which is
always a product by definition) ICE's exact combination rule isn't as
universally fixed across sources. WSJF is SAFe's own `(Business Value +
Time Criticality + Risk Reduction/Opportunity Enablement) / Job Size`,
verbatim — "Risk Reduction/Opportunity Enablement" stays SAFe's single
combined criterion, not split into two invented ones.

### MoSCoW is categorical by construction, never coerced into a number

CLAUDE.md §17's "do not create scores that imply false precision" — already
applied to `Risk`/`Stakeholder` — extends here exactly: MoSCoW never
produces a `score`, and `PrioritizationFramework.criteria` is empty for a
MOSCOW framework (`calculate_moscow_result` takes only a `MoscowCategory`
enum, no criterion values at all). Storage-wise this meant `category`
couldn't reuse `ProjectPriorityCriterionValue` (Decimal-only) — a
`category: MoscowCategory | None` column was added directly to
`ProjectPriorityScore` instead, nullable because it is meaningless for
every other framework type, with "which column is actually used" enforced
at the service layer (`ProjectPriorityScoreService._validate_category`)
rather than a DB CHECK spanning two tables. `rank_portfolio` lists a
MoSCoW-framework score with `rank: null` exactly like an incomplete
numeric score — a category is never treated as sortable against a number.

### Criteria editing is Weighted-Scoring-only, gated by `is_editable`, never by a bulk PATCH

Three new endpoints (`POST/PATCH/DELETE
.../frameworks/{id}/criteria[/{criterion_id}]`), not a `criteria` field on
`PrioritizationFrameworkUpdate` — a route shaped like a generic bulk PATCH
would make it too easy to reach a RICE/ICE/WSJF criterion by accident. Every
one of the three re-checks `is_editable` server-side (`ForbiddenError`,
403) regardless of what the frontend shows, matching CLAUDE.md §21's "the
backend is what actually enforces this." A criterion's `key` is never
changed by a rename — it stays the stable identifier
`ProjectPriorityCriterionValue` rows and `app/domain/prioritization.py`
key off of, so renaming never orphans a previously recorded value.
Removing a Weighted framework's last remaining criterion is rejected
(`DomainValidationError`) — the same "needs at least one criterion"
invariant `PrioritizationFrameworkCreate` already enforces at creation
time, just as true after the fact.

### Dependencies: one directed edge, three types, cycle detection scoped to `blocks` only

`ProjectDependency` stores one direction (`from_project` → `to_project`,
`dependency_type`); the inverse ("blocked by") view is always derived by
querying the other direction, never stored separately — matching
`ProjectAccessGrant`'s "store one direction, derive the inverse" precedent
rather than risking two directions disagreeing. Cycle detection
(`app/domain/prioritization.py::detects_cycle`, a DFS reachability check)
only ever runs against `blocks` edges — `related`/`enables` don't imply a
strict ordering the way `blocks` does, so a graph mixing all three edge
types isn't meaningful to cycle-check (this default was named as the
answer to the Phase 17 PRD's own Open Question 6). A dependency is
created/deleted only through its `from_project`'s URL
(`/api/v1/projects/{id}/dependencies`) — `ProjectDependencyCreate`'s own
docstring calls this "the URL names the owning project," matching how
every other project-nested resource in this codebase works; deleting the
edge from the `to_project`'s URL returns 404, not a redirect or a 403,
consistent with every other cross-tenant-shaped access check in this
codebase resolving to "acts as if it doesn't exist here."

### Authorization: reused, not invented

No new `Permission` enum member. Criterion CRUD reuses
`PRIORITIZATION_MANAGE` (Admin/Owner only, matching framework CRUD's own
blast radius). Dependency create/delete reuses `PRIORITIZATION_SCORE` via
the existing `require_project_access` — "Managers can create dependencies
for projects they manage," identical shape to scoring itself. Dependency
list and the organization-wide dependency-graph endpoint reuse
`PRIORITIZATION_READ` (every role). No new grant table, no new concurrency
surface — the existing Phase 11/15 concurrency suites were re-run as
regression and still pass unmodified.

### Audit: five new `AuditAction` members, same metadata discipline as Phase 17

`prioritization_criterion.create/update/delete` and
`project_dependency.create/delete`, using the existing `AuditService`
unchanged. A criterion-create/update event's metadata is `{name, weight}`-
shaped (or `{fields: [...]}` for update, matching every other
`*.update` event in this codebase); a dependency-create event's metadata
is `{to_project_id, dependency_type}` — never free text, matching Risk/
Stakeholder/Phase 17's own precedent.

### Database: one new table, one new column, no changes to any other existing table

`project_dependencies` (new); `project_priority_scores.category` (new,
nullable). `dependency_type` and `category` are both DB-CHECK-constrained
(`create_constraint=True`) — three and four fixed values respectively,
matching `RiskProbability`'s closed-vocabulary precedent, unlike
`framework_type`'s deliberately open one. Adding a nullable CHECK-
constrained column to an existing SQLite table requires
`op.batch_alter_table` (a plain `op.add_column` silently skips creating the
CHECK constraint on SQLite, and the naive batch drop-column downgrade in
turn fails unless the CHECK constraint is dropped explicitly first,
before the column it references) — both directions were verified against
a real file-backed database with a full upgrade→downgrade→upgrade round
trip, and the pre-existing, documented SQLite CHECK-constraint autogenerate
false positive (unrelated to this migration) was confirmed present at the
Phase 17 head too, not introduced by this change.

### Import/Export: deferred, matching Phase 13/14/17's own precedent

`ProjectDependency` is not registered into the Phase 6 import/export
system — not specified, and deferred exactly as Phase 17's own
`ProjectPriorityScore` was.

## Consequences

- 1 new table, 1 new column on an existing table, 1 migration, 0 new
  permissions, 5 new `AuditAction` members. 0 changes to any existing
  permission's grant set, 0 new concurrency surface.
- New backend module: `app/models/project_dependency.py`,
  `app/repositories/project_dependency.py`,
  `app/services/project_dependency.py`. Extended:
  `app/domain/prioritization.py` (+`ICE_CRITERION_KEYS`,
  +`WSJF_CRITERION_KEYS`, +`FIXED_CRITERION_KEYS`,
  +`calculate_ice_score`, +`calculate_wsjf_score`,
  +`calculate_moscow_result`, +`detects_cycle`), `app/models/enums.py`
  (+`MoscowCategory`, +`ProjectDependencyType`, extended
  `PrioritizationFrameworkType`, +5 `AuditAction` members),
  `app/models/project_priority_score.py` (+`category`),
  `app/models/__init__.py`, `app/schemas/prioritization.py`
  (+`CriterionUpdate`, +`ProjectDependencyCreate/Read`,
  +`DependencyGraphRead`, `category` on score schemas),
  `app/services/prioritization_framework.py`
  (+`add_criterion`/`update_criterion`/`remove_criterion`, generalized
  fixed-criteria seeding), `app/services/project_priority_score.py`
  (`category` validation), `app/api/v1/prioritization.py` (+9 routes),
  `tests/factories.py` (+`make_project_dependency`, `category` param).
- New frontend modules:
  `features/prioritization/{components/FrameworkCriteriaEditor,
  components/DependencyManager, components/DependencyGraphTable}.tsx`,
  `hooks/{useCriterionMutations,useProjectDependencies,
  useDependencyMutations,useDependencyGraph}.ts`. Extended:
  `types/prioritization.ts`, `api/prioritizationApi.ts`,
  `components/FrameworkForm.tsx`, `components/ScoreForm.tsx`,
  `components/PortfolioTable.tsx`, `views/PrioritizationOverviewPage.tsx`,
  `test/fixtures.ts` (+2 fixture builders, `category` field on 2 existing
  ones).
- Backend: +52 tests (16 domain, 36 API) — 870 total, all passing.
  `ruff check` and `uv run pyright` (strict) both fully clean. Fresh
  `alembic upgrade head`, `alembic current`, and an
  upgrade→downgrade→upgrade round trip all verified against a real
  file-backed database.
- Frontend: +16 tests (5 new component test files plus extensions to
  `FrameworkForm.test.tsx`/`ScoreForm.test.tsx`) — 202 total, all passing.
  `oxlint`/`tsc -b --noEmit` clean (the same 2 pre-existing, unrelated
  `AuthContext.tsx` warnings as every prior phase). Production build
  succeeds.
- Live verification: a real uvicorn instance was started against the dev
  SQLite database (migrated to this phase's head) and its live
  `/openapi.json` was fetched, confirming all 9 new routes are registered
  and that an unauthenticated request is correctly rejected (401) —
  consistent with the automated test suite's exhaustive per-endpoint
  auth/role/grant/cross-organization coverage, which exercises the same
  ASGI application and a real SQLite database. No browser or interactive
  UI walkthrough was performed — no such tool is available in this
  environment (the same disclosed limitation as every prior phase).
- **Deferred, not dropped**: `PortfolioSnapshot`; scenario-vs-baseline
  ranking comparison; AI priority explanation; the Priority Explanation
  Panel and Scenario Comparison frontend views; the five remaining
  Recharts visualizations (Priority vs. Effort scatter, Capacity vs.
  Priority matrix, Risk vs. Value quadrant, WSJF breakdown, dependency
  timeline). `ProjectDependency` Import/Export registration. See
  [docs/PRD-phase-17-prioritization.md](../PRD-phase-17-prioritization.md)
  for the full original scope.
- **Residual risk**: none newly introduced beyond what's listed above. No
  behavior change to any existing phase's authorization, audit, capacity,
  risk, scenario, or Phase 17 RICE/Weighted-Scoring calculation.
