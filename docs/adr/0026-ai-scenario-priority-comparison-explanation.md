# ADR 0026: Phase 26 — AI scenario-vs-baseline prioritization comparison explanation

- **Status:** Accepted
- **Date:** 2026-08-27

## Context

Phase 25 (ADR 0025) resolved the WSJF breakdown visualization but did not
select what Phase 26 should be. Per the phase brief's explicit
audit-first instruction, the repository was audited before any code was
written: CLAUDE.md (§§4, 21, 31, 39), `docs/roadmap.md`,
`docs/architecture.md`, `docs/domain-concepts.md`, every ADR through
0025, `docs/PRD-phase-17-prioritization.md`, the complete Phase 17-25
prioritization implementation, the Scenario implementation and its
delete lifecycle, Risk/Stakeholder, the Phase 6 import/export
infrastructure, the organization/membership API surface, existing
Recharts usage, and existing authorization/organization-scoping/testing/
migration conventions.

## Candidates re-audited from Phase 25's own deferred list

Per the phase brief's explicit instruction to re-verify rather than
re-assert, each item Phase 25 left deferred was checked directly against
current code, not merely repeated from a prior ADR's claim:

- **Scenario snapshots** — `ScenarioService.delete`
  (`app/services/scenario.py`) still performs a genuine hard delete
  (deletes the scenario and its own operations only). The "what happens
  to a scenario snapshot when its scenario is deleted" product decision
  ADR 0022 first flagged is **still unresolved**.
- **Import/Export registration** — `ImportEntityType`
  (`app/models/enums.py`) still has exactly the same 10 members. The "no
  Person/Project-style natural identity key" gap is **still unresolved**.
- **The remaining four PRD visualizations** — `ProjectDependency`
  (`app/models/project_dependency.py`) has only `created_at`; still no
  date/duration field of any kind, so the dependency timeline remains
  genuinely blocked. Capacity-vs-Priority and Risk-vs-Value still carry
  the same unspecified cross-domain ambiguity ADR 0025 identified.
- **A membership/user-management UI** — still fully backend-ready
  (`app/api/v1/organizations.py` unchanged), still a materially larger
  multi-flow vertical slice than a single feature.
- **A rank-over-time trend variant** — this was an explicit product
  decision Phase 24 already made (not merely deferred pending one); not
  re-litigated.
- **An AI interpretation of the Phase 20 scenario-vs-baseline
  comparison** — Phase 20's own brief named this as intentionally
  deferred "for a future phase to consider deliberately." Verified
  directly: no `explain_scenario_priority`/`explain-scenario-comparison`
  capability exists anywhere in `apps/api` today, and
  `ScenarioPriorityService.compare` (`app/services/scenario_priority.py`)
  already returns a complete, stable, already-computed comparison shape
  (`ScenarioPriorityComparisonItem`: baseline result, scenario result,
  `has_override`, `changed`, ranks) via the unchanged Phase 20
  `GET /api/v1/scenarios/{scenario_id}/priority-comparison` endpoint.

## Decision: AI explanation of the Phase 20 comparison, no blocking question needed

**Selected.** This is the only candidate that is simultaneously
already-specified (Phase 20's own ADR explicitly named it as the
intended next step, not merely an incidental deferral), requires no
resolution of any open product decision, and is the third instance of an
already-proven, well-tested pattern — `explain-priority` (Phase 19) and
`explain-snapshot-comparison` (Phase 23) both explain an existing
deterministic comparison/score without ever recalculating it. Per the
phase brief's own instruction ("do not ask a question merely for
confirmation when the repository already specifies the answer"), no
blocking question was raised.

### Checked for a Phase-25-style interpretation gap — found none

Phase 25's own ADR flagged that its source spec ("stacked bar of the
four inputs") left an execution detail under-specified, requiring a
documented interpretation. This phase's source material —
`ScenarioPriorityComparisonItem`'s exact fields, `ScenarioPriorityComparisonRead`'s
exact JSON shape, and Phase 19's/Phase 23's own precedent for how an AI
capability wraps an existing comparison — left **no comparable gap**:
every field this phase's context needs (baseline/scenario score, rank,
category, `has_override`, `changed`) already exists verbatim in the
Phase 20 response, and the AI-capability shape (context builder → AI
service method → POST route → frontend button) is fully determined by
two already-shipped precedents. No axis, aggregation, filtering, or
comparison-semantics ambiguity exists here — this is a text explanation
of an existing table, not a new visualization.

## Decisions

### A seventh capability on the existing Phase 8 pipeline, not a new one

`AIContextBuilder`/`AIService`/`AiTriggerButton`/`AiResultPanel` are
unchanged in shape — `explain_scenario_priority_comparison` is a new
method following the exact same `build_for_*` → `_generate` → grounded
`AIResponseEnvelope` path every other capability already uses (CLAUDE.md
§21/§35: never a second AI orchestration path).
`AIContextBuilder.build_for_scenario_priority_comparison` calls
`ScenarioPriorityService.compare(organization_id, scenario_id,
framework_id)` verbatim — the exact same `(scenario, framework, items)`
triple the existing API route already builds its response from — so this
phase recalculates nothing: no score, rank, or category is ever
recomputed by the AI layer. `AIContextBuilder` gained one new constructor
dependency (`ScenarioPriorityService`), reusing the same repository
wiring `app/api/v1/scenarios.py`'s own `get_scenario_priority_service`
factory already assembles.

### Framework/scenario 404s are inherited, not re-implemented

Because `build_for_scenario_priority_comparison` calls
`ScenarioPriorityService.compare` unchanged, its existing guarantees
carry straight through with no new code: an unknown or
cross-organization `scenario_id` or `framework_id` raises `NotFoundError`
(404, never 403), verified live against a genuinely cross-organization
scenario (the active-organization session, not merely account
membership, is what's checked — the same account had Owner membership in
both organizations and still received 404 for the other organization's
scenario).

### Grounding: a new `scenario_priority_comparison` reference type, one entity_id per project

`AISourceReferenceType.SCENARIO_PRIORITY_COMPARISON` was added alongside
`snapshot_comparison`/`priority_score`/etc. Like `snapshot_comparison`
(Phase 23), a scenario priority comparison is a *set* of per-project
facts, so `AIInsightContext.known_references()` adds one
`("scenario_priority_comparison", project_id)` pair per comparison item
— the same "one reference per collection member" shape already
established, not a new pattern.

### Authorization: `Permission.AI_USE` only, no new permission, no CSRF

`POST /api/v1/ai/explain-scenario-priority-comparison` is gated by the
same `Permission.AI_USE` every other `/api/v1/ai/*` route already
requires, granted to every role — matching `explain-priority`/
`explain-snapshot-comparison`/`explain-scenario`/`explain-signal`/
`summarize` exactly. No `require_csrf` dependency, matching every other
AI route (none of which mutate CapacityOS data). This mirrors, and does
not re-derive, the same authorization discipline Phase 19/23 already
established: the AI route does not require `SCENARIO_READ` separately —
`AI_USE` plus the organization-scoped service call underneath it is the
complete authorization surface, exactly as it already is for the other
six AI capabilities.

### API: one new route on the existing router, no new resource

```text
POST /api/v1/ai/explain-scenario-priority-comparison
```

Request body: `{scenario_id, framework_id}` — the identical pair
`GET /api/v1/scenarios/{scenario_id}/priority-comparison?framework_id=`
already takes (Phase 20), since the comparison being explained is
exactly the one that pair identifies; no separate comparison id exists
to reference instead (the comparison itself is never persisted).

### Frontend: extends the existing Scenario workspace, no new page

`ExplainScenarioPriorityComparisonButton` (mirroring
`ExplainSnapshotComparisonButton`/`ExplainPriorityButton` verbatim, down
to reusing `AiTriggerButton`/`AiResultPanel` unchanged) was added inside
the existing "Priority comparison" card in `ScenarioWorkspacePage`,
directly below `PriorityComparisonTable` — rendered whenever a
comparison framework is selected and at least one project is scored
under it. No new route, no new navigation entry.

## Consequences

- 0 new tables, 0 migrations, 0 new permissions, 0 changes to any
  existing table or permission's grant set. Verified: a fresh
  `alembic upgrade head` on a genuinely empty database lands at the
  unchanged Phase 21 head (`9f73a340f443`).
- Extended backend modules: `app/schemas/ai.py`
  (+`AISourceReferenceType.SCENARIO_PRIORITY_COMPARISON`,
  +`AIExplainScenarioPriorityComparisonRequest`),
  `app/services/ai_context.py` (+`AIScenarioPriorityComparisonItemFact`,
  +`AIScenarioPriorityComparisonFact`, +`scenario_priority_comparison`
  field on `AIInsightContext`,
  +`AIContextBuilder.build_for_scenario_priority_comparison`,
  +`ScenarioPriorityService` constructor dependency),
  `app/services/ai_service.py`
  (+`AIService.explain_scenario_priority_comparison`, a scenario-
  priority-comparison block in `serialize_context`), `app/api/v1/ai.py`
  (+`/explain-scenario-priority-comparison` route, `get_ai_service`
  wiring). No new backend files.
- New frontend modules:
  `features/ai/hooks/useAiExplainScenarioPriorityComparison.ts`,
  `features/ai/components/ExplainScenarioPriorityComparisonButton.tsx`.
  Extended: `features/ai/types/ai.ts`, `features/ai/api/aiApi.ts`,
  `features/scenarios/views/ScenarioWorkspacePage.tsx` (renders
  `ExplainScenarioPriorityComparisonButton` below the existing
  comparison table).
- Backend: +12 tests (5 service-level in
  `tests/services/test_ai_service.py` — context serialization,
  grounding/known-references, and unavailable/error/ok `_generate` paths;
  7 API-level in `tests/api/test_ai.py`, including a cross-organization
  404 regression for both the scenario id and the framework id, an
  unauthenticated 401 check, and a never-mutates-the-real-score check) —
  975 total, all passing. `ruff check` and `uv run pyright` (strict) both
  fully clean.
- Frontend: 0 new tests —
  `ExplainScenarioPriorityComparisonButton`/
  `useAiExplainScenarioPriorityComparison` are thin wrappers around
  already-tested primitives (`AiTriggerButton`/`AiResultPanel`), matching
  `ExplainSnapshotComparisonButton`'s (Phase 23) and
  `ExplainPriorityButton`'s (Phase 19) own established precedent — only
  the shared primitives and one representative trigger
  (`SummarizeButton`) are unit-tested anywhere in this codebase. 241
  total, all passing. `oxlint`/`tsc -b --noEmit` clean (the same 2
  pre-existing, unrelated `AuthContext.tsx` warnings as every prior
  phase). Production build succeeds.
- Live verification: a real uvicorn instance was started against a
  genuinely fresh, migrated, file-backed SQLite database with a real
  Owner account bootstrapped via `scripts/create_first_owner.py` and
  `AI_PROVIDER=mock`. A real authenticated session (cookie login,
  double-submit CSRF token) walked the full golden path over real
  HTTP — create project → create RICE framework → score it (400) →
  create a scenario → set a criterion override (reach 1000 → 9000) →
  confirmed the deterministic Phase 20 comparison correctly reports
  `has_changes: true` and `scenario_score: 3600` → requested the Phase
  26 AI explanation (confirmed `status: "ok"`) → re-read the real,
  persisted score (confirmed still exactly 400, untouched by the AI
  call) → confirmed a nonexistent scenario id 404s → confirmed an
  unauthenticated request 401s → created a second organization, created
  a scenario there, and confirmed that requesting an explanation from
  the Default organization referencing the other organization's
  scenario 404s (not 403) even though the same account holds Owner
  membership in both organizations — proving the boundary is enforced
  against the session's *active* organization, not merely account
  membership — plus a log scan confirming no password, CSRF token, or
  session token value was ever written to the server log. No browser or
  interactive UI walkthrough was performed — no such tool is available
  in this environment (the same disclosed limitation as every prior
  phase).
- **Deferred, not dropped**: the remaining four PRD visualizations
  (Priority-vs-Effort scatter, Capacity-vs-Priority matrix, Risk-vs-Value
  quadrant, dependency timeline); a membership/user-management frontend;
  Scenario snapshots (still blocked on the `Scenario` hard-delete
  lifecycle decision); Risk/Stakeholder/Prioritization/
  `ProjectDependency`/`PortfolioSnapshot` Import/Export registration
  (still blocked on a missing natural identity key); a rank-over-time
  trend variant (already explicitly declined, not re-litigated).
- **Residual risk**: none newly introduced. No behavior change to any
  existing phase's authorization, audit, capacity, risk, scenario, or
  Phase 17-25 prioritization/comparison behavior — this phase only reads
  an already-computed Phase 20 comparison result and asks a model to
  interpret it.

## Confirmation

Phase 27 was **not** started. Nothing in this phase was committed.
