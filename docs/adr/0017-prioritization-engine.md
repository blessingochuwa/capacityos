# ADR 0017: Phase 17 prioritization engine (v1 slice)

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

CLAUDE.md §18 names the gap Phases 1–16 never closed: CapacityOS could
describe capacity, risk, and skill facts but never helped an operator
decide what to do about them when demand exceeds capacity. Phase 17 is the
first phase that is a new *product module* rather than an extension of
existing infrastructure — per the user's own request, a
[PRD](../PRD-phase-17-prioritization.md) was written and reviewed before
any code was written, and two decisions were confirmed before
implementation started: build a reduced v1 slice first (not the full
brief in one pass), and use the PRD's own recommended defaults for the
remaining open questions. This ADR records what was actually built,
matching every prior phase's ADR/PRD split (the PRD is the pre-
implementation proposal; this document is the as-built record).

## Decisions

### v1 scope: two frameworks, no dependency graph, no scenario comparison, no AI yet

Built: `PrioritizationFramework`/`PrioritizationCriterion`/
`ProjectPriorityScore`/`ProjectPriorityCriterionValue`, RICE and Weighted
Scoring formulas, framework CRUD, score CRUD, portfolio ranking. **Not**
built in this phase: ICE/WSJF/MoSCoW formulas, `ProjectDependency` and
cycle detection, `PortfolioSnapshot`, scenario-vs-baseline ranking
comparison, AI explanation, and five of the six frontend views (Priority
Explanation Panel, Scenario Comparison, Dependency Graph) and all six
chart types. Each is a genuine, named gap — not silently dropped — see
Consequences. CLAUDE.md §31 ("implement the smallest complete slice") was
the explicit reason to slice rather than build the entire brief at once;
full security/audit/IDOR discipline was NOT deferred along with the rest
of the surface — every mutation path built in v1 has complete test
coverage to the same standard as every other phase.

### The framework model: one generic engine, not five parallel systems

RICE and Weighted Scoring share one storage shape
(`PrioritizationFramework` → `PrioritizationCriterion` → one value per
criterion per score) — only the combining formula differs, selected by
`framework_type` and dispatched through
`app/domain/prioritization.py::calculate_priority_score`, the single
place that decision is made (mirrors `has_permission` being the one place
a role's grants are decided). RICE's four criteria (Reach, Impact,
Confidence, Effort) are fixed and seeded automatically
(`PrioritizationFrameworkService._seed_rice_criteria`) with
`is_editable=False`; Weighted Scoring's criteria are fully organization-
defined with `is_editable=True`. Neither framework type supports editing
its criteria after creation in v1 — a mis-defined Weighted Scoring
framework is deactivated and recreated, not patched in place (see
Consequences).

### Scores are computed at read time, never stored

`ProjectPriorityScore` holds no `score` column. Only the human-entered
criterion **inputs** (`ProjectPriorityCriterionValue`) are persisted; the
score itself is a pure function of (inputs, framework's current criteria/
weights) recomputed on every read — the same "derive, never cache"
discipline `Risk.exposure` and every Scenario result already follow (ADR
0004: "results are never stale relative to production data"). This also
means editing a Weighted Scoring criterion's weight (were that supported
— it isn't, in v1) would retroactively change every existing score's
ranking with zero migration/recomputation step, by construction.

### Missing inputs are explicit, never treated as zero

A score with incomplete criterion inputs returns `score: null` and a
`missing_criteria` list, both from every read (`PriorityScoreResult`).
Portfolio ranking (`rank_portfolio`) lists incomplete scores last, with
`rank: null` — never sorted as if a missing input were the lowest possible
value. This is the phase's concrete answer to the brief's "no hidden
calculations" requirement.

### Scoring inputs are an upsert, not a full replace

`ProjectPriorityScoreUpdate.values`, when provided, updates only the
criteria it mentions — a criterion not included keeps its previously
recorded value. This is a deliberate departure from
`WorkingScheduleUpdate.entries`'s full-replace-on-PATCH convention: a
working schedule's entries represent one indivisible weekly pattern (a
partial week isn't a meaningful concept), while a priority score is
explicitly designed to be completed incrementally over time (the whole
point of surfacing `missing_criteria` at all). Recorded in code comments
at the point of departure rather than silently deviating from precedent.

### Authorization: framework management is Admin/Owner only, scoring is Manager+grant

Three new permissions, reusing the existing `ROLE_PERMISSIONS`/
`require_permission`/`require_project_access` machinery unchanged:

- `PRIORITIZATION_READ` — every role (frameworks, scores, portfolio
  ranking), matching every other `*_READ` permission.
- `PRIORITIZATION_SCORE` — Manager+, instance-scoped via the existing
  `ProjectAccessGrant` mechanism (`require_project_access`), identical
  shape to Risk/Stakeholder/Allocation: "Managers can score projects they
  manage," not the whole organization.
- `PRIORITIZATION_MANAGE` — Admin/Owner only, deliberately **not**
  Manager-level despite Skill's own org-wide-catalog precedent being
  Manager-writable. A framework change reshuffles every project's rank
  across the organization at once — closer in blast radius to
  `MEMBERSHIP_MANAGE`/`ORGANIZATION_MANAGE` than to an ordinary catalog
  edit, per the phase brief's own explicit "Owners/Admins manage
  organization frameworks."

Frameworks are organization-wide (no `organization_id` path segment,
matching Skill's exact routing shape — `/api/v1/prioritization/frameworks`,
not `/api/v1/organizations/{id}/prioritization/frameworks`, since every
other org-wide-but-not-project-nested resource in this codebase uses the
simpler shape and only `organizations.py`'s own sub-resources use the
path-segment form). Scores are project-nested
(`/api/v1/projects/{id}/priority-scores`), matching Risk/Stakeholder
exactly.

### No new concurrency surface

No new grant table was introduced (scoring reuses the existing
`ProjectAccessGrant`), so no new concurrency test was needed — the
existing Phase 11/15 concurrency suites were re-run as regression and
still pass unmodified.

### Audit: framework changes record criteria names and weights only; score changes never record notes or values

`prioritization_framework.create/update/deactivate` and
`project_priority_score.create/update/delete`, using the existing
`AuditService` unchanged. Matches Risk/Stakeholder's precedent exactly
(`test_updating_a_risk_audit_event_never_carries_free_text_values`): a
framework-create event's metadata includes `{name, weight}` per criterion
(never a criterion's free-text description, since none exists); a score
update's metadata is `{"fields": [...]}"` — field *names* changed, never
the submitted criterion values or notes text. Verified with a dedicated
regression test asserting the confidential note text literally does not
appear anywhere in the audit event.

### Database: four new tables, no changes to any existing table

`prioritization_frameworks`, `prioritization_criteria`,
`project_priority_scores`, `project_priority_criterion_values`.
`framework_type` is deliberately **not** DB-CHECK-constrained (matches
`AvailabilityType`'s open-vocabulary precedent, not `RiskProbability`'s
fixed one) — CLAUDE.md §18 names three more frameworks as "may be
supported later," so adding one must stay a pure code change. Fresh
`alembic upgrade head`, `alembic check` (only the pre-existing,
documented SQLite CHECK-constraint false positive against *unrelated*
existing columns — nothing from this migration), and an
upgrade→downgrade→upgrade round trip were all verified against a real
file-backed database.

### Import/Export: deferred, matching Phase 13/14's own precedent

Not registered into the Phase 6 import/export system — not specified by
CLAUDE.md, and prioritization data (structured criteria + per-criterion
values) is less naturally tabular than Risk/Stakeholder already were. The
brief's own fallback instruction ("otherwise document the deferral") is
followed here exactly as Phase 13/14 did.

## Consequences

- 4 new tables, 1 migration, 3 new permissions, 6 new `AuditAction`
  members. 0 changes to any existing table, 0 changes to any existing
  permission, 0 new concurrency surface.
- New backend modules: `app/domain/prioritization.py`,
  `app/models/{prioritization_framework,prioritization_criterion,
  project_priority_score,project_priority_criterion_value}.py`,
  `app/repositories/{prioritization_framework,prioritization_criterion,
  project_priority_score}.py`, `app/services/{prioritization_framework,
  project_priority_score}.py`, `app/schemas/prioritization.py`,
  `app/api/v1/prioritization.py`. Extended: `app/models/project.py`
  (+`priority_scores` relationship), `app/models/enums.py`
  (+`PrioritizationFrameworkType`, +6 `AuditAction` members),
  `app/domain/authorization.py` (+3 `Permission` members), `app/main.py`.
- New frontend module: `apps/web/src/features/prioritization/` (types,
  api, 5 hooks, 3 components, 1 view). Extended: `app/routes.tsx`,
  `components/layout/AppShell.tsx` (+nav link), `test/fixtures.ts` (+4
  fixture builders).
- Backend: +49 tests (12 domain, 37 API) — 818 total, all passing.
  `ruff check` and `uv run pyright` (strict) both fully clean.
- Frontend: +14 tests (3 component files) — 186 total, all passing.
  `oxlint`/`tsc` clean (2 pre-existing documented warnings only).
  Production build succeeds.
- **Deferred, not dropped** (each is a real, named v1 boundary, not an
  oversight): ICE/WSJF/MoSCoW formulas; `ProjectDependency` and cycle
  detection; `PortfolioSnapshot`; scenario-vs-baseline ranking comparison;
  AI priority explanation (`AIPriorityContext`, `/api/v1/ai/explain-
  priority`); the Priority Explanation Panel, Scenario Comparison, and
  Dependency Graph frontend views; all six Recharts visualizations
  (Priority vs. Effort scatter, Capacity vs. Priority matrix, Risk vs.
  Value quadrant, WSJF breakdown, dependency timeline — the portfolio
  ranking table itself IS built); editing a framework's criteria after
  creation; Import/Export registration. See
  [docs/PRD-phase-17-prioritization.md](../PRD-phase-17-prioritization.md)
  for the full original scope and the reasoning behind each deferral.
- **Residual risk**: none newly introduced beyond what v1 explicitly
  doesn't cover yet (listed above). No behavior change to any existing
  phase's authorization, audit, or capacity/risk/scenario calculation.
