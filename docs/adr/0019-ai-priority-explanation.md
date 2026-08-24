# ADR 0019: Phase 19 — AI priority explanation

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

CLAUDE.md §39 stopped at Phase 18; `docs/roadmap.md`'s "Proposed next" section
named the still-open remainder of the original Phase 17 PRD as one
provisional list: `PortfolioSnapshot`, scenario-vs-baseline ranking
comparison, AI priority explanation, the Priority Explanation Panel and
Scenario Comparison frontend views, and five Recharts visualizations —
none individually confirmed as "the next phase." Per the phase brief's
explicit instruction not to assume a scope, the repository was audited
(CLAUDE.md, `docs/roadmap.md`, `docs/architecture.md`,
`docs/domain-concepts.md`, ADRs 0008/0017/0018, the Phase 8 AI
infrastructure, and the Phase 17/18 prioritization implementation) before
any code was written. The scope reduction below was proposed to the user
in plain text — not a second blocking question, mirroring how Phase 18's
own scope was reduced from "the rest of Prioritization" — and confirmed
by proceeding, since it required no genuine architecture-changing product
decision.

## Decisions

### Scope: AI priority explanation only

Built: `AIService.explain_priority`, `AIContextBuilder.build_for_priority_score`,
`POST /api/v1/ai/explain-priority`, and a frontend `ExplainPriorityButton`
next to an existing `ProjectPriorityScore`. **Not** built (each a named,
scoped deferral — see Consequences): `PortfolioSnapshot`, scenario-vs-
baseline ranking comparison, the Scenario Comparison frontend view, and
the five remaining Recharts visualizations. Of the six items the roadmap
named, this is the only one that is simultaneously well-precedented (a
same-shape fifth capability alongside `summarize`/`explain-signal`/
`explain-scenario`/`ask`), requires no new persistence concept, and
resolves no ambiguous domain-model question — see "What was deliberately
not chosen" below.

### A fifth capability on the existing Phase 8 pipeline, not a new one

`AIContextBuilder`/`AIService`/`AiTriggerButton`/`AiResultPanel` are
unchanged in shape — `explain_priority` is a new method following the
exact same `build_for_*` → `_generate` → grounded `AIResponseEnvelope`
path every other capability already uses (CLAUDE.md §21/§35: never a
second AI orchestration path). `AIContextBuilder.build_for_priority_score`
calls `ProjectPriorityScoreService.get(organization_id, project_id,
score_id)` verbatim — the exact `(score, PriorityScoreResult)` pair
`project_priority_score_to_read` already builds the API response from —
so this phase recalculates nothing; every number handed to the model was
already produced by the Phase 17/18 deterministic engine before this
phase existed. `AIContextBuilder` gained one new constructor dependency
(`ProjectPriorityScoreService`), reusing the same repository wiring
`app/api/v1/prioritization.py`'s own `get_score_service` factory already
assembles.

### Grounding: a new `priority_score` reference type, not a special case

`AISourceReferenceType.PRIORITY_SCORE` was added alongside `signal`/
`capacity`/`scenario`/`skill_coverage`; `AIInsightContext.known_references()`
adds `("priority_score", score_id)` exactly the way `scenario`'s single
fact does. The generic `ground()` function needed no changes at all — it
already operates on arbitrary `(type, id)` pairs, so a fifth reference
type is a pure data addition, not new logic (existing grounding tests
already cover the mechanism; new tests only verify the new fact reaches
`known_references()`/`serialize_context` correctly).

### What was deliberately not chosen

- **`PortfolioSnapshot`** — a new persistence concept (point-in-time
  saved ranking) with no relationship to the Phase 8 AI infrastructure
  this slice was chosen to reuse; a genuinely separate vertical slice.
- **Scenario-vs-baseline ranking comparison** — audited and found
  genuinely ambiguous at the domain-model level: Scenario operations
  (`ADD_ALLOCATION`, `ADJUST_ALLOCATION`, etc. — see
  `docs/adr/0004-phase-4-scenario-planning.md`) never touch a project's
  prioritization criterion values, so "how does accepting this scenario
  change portfolio priority" has no defined computation today. Resolving
  that is a genuine product decision (what, precisely, does a scenario
  change about a project's RICE/ICE/WSJF/Weighted/MoSCoW inputs?), not an
  implementation detail — exactly the case CLAUDE.md §31 says to bring
  back to the user rather than silently resolve. Left for a future phase
  to scope explicitly.
- **The five Recharts visualizations** — visualization work, not
  decision-support computation; CLAUDE.md §29 already cautions against
  decorative charts, so building five in one slice would risk exactly
  that without a specific "what question does each answer" brief per
  chart, which the roadmap's one-line mention doesn't provide.

### Authorization and multi-tenancy: fully reused, nothing new

`Permission.AI_USE` only — the same permission every other `/api/v1/ai/*`
route already requires, granted to every role (matches CLAUDE.md's
existing "AI is read/interpret only" posture). No new grant-scoping was
needed: `build_for_priority_score` reaches the score exclusively through
`ProjectPriorityScoreService.get`, which is already organization-scoped
(the same repository path `app/api/v1/prioritization.py`'s own read/write
routes use) — a cross-organization `project_id`/`score_id` pair 404s
exactly as it already does for every other prioritization route, verified
with a dedicated regression test mirroring
`test_summary_404_for_person_in_another_organization`'s Phase 16-era
precedent.

### Database: no changes

Zero new tables, columns, or migrations — this phase adds no persistence
at all. Verified against a genuinely fresh SQLite database (empty →
`alembic upgrade head`, landing at Phase 18's `9fbd652ddd0b`, unchanged).

## Consequences

- 0 new tables, 0 migrations, 0 new permissions, 0 changes to any
  existing table or permission's grant set.
- Extended backend modules: `app/schemas/ai.py`
  (+`AISourceReferenceType.PRIORITY_SCORE`, +`AIExplainPriorityRequest`),
  `app/services/ai_context.py` (+`AIPriorityFact`, +`priority` field on
  `AIInsightContext`, +`AIContextBuilder.build_for_priority_score`,
  +`ProjectPriorityScoreService` constructor dependency),
  `app/services/ai_service.py` (+`AIService.explain_priority`, priority
  block in `serialize_context`), `app/api/v1/ai.py` (+`/explain-priority`
  route, `get_ai_service` wiring). No new backend files.
- New frontend modules: `features/ai/hooks/useAiExplainPriority.ts`,
  `features/ai/components/ExplainPriorityButton.tsx`. Extended:
  `features/ai/types/ai.ts`, `features/ai/api/aiApi.ts`,
  `features/prioritization/views/PrioritizationOverviewPage.tsx` (renders
  `ExplainPriorityButton` next to an existing score).
- Backend: +8 tests (4 service-level in `tests/services/test_ai_service.py`,
  4 API-level in `tests/api/test_ai.py`, including a cross-organization
  404 regression) — 878 total, all passing. `ruff check` and
  `uv run pyright` (strict) both fully clean.
- Frontend: 0 new tests — `ExplainPriorityButton`/`useAiExplainPriority`
  are thin wrappers around already-tested primitives
  (`AiTriggerButton`/`AiResultPanel`), matching the established, pre-
  existing coverage boundary: neither `ExplainScenarioButton` nor
  `ExplainSignalButton` (Phase 8) has a dedicated test file either — only
  the shared primitives and one representative trigger
  (`SummarizeButton`) are unit-tested. 202 total, all passing. `oxlint`/
  `tsc -b --noEmit` clean (the same 2 pre-existing, unrelated
  `AuthContext.tsx` warnings as every prior phase). Production build
  succeeds.
- Live verification: a real uvicorn instance was started against the
  Phase-18-head dev SQLite database; the live `/openapi.json` confirmed
  `POST /api/v1/ai/explain-priority` is registered (83 routes, up from
  82), and an unauthenticated request to it was confirmed rejected (401).
  No browser or interactive UI walkthrough was performed — no such tool
  is available in this environment (the same disclosed limitation as
  every prior phase).
- **Deferred, not dropped**: `PortfolioSnapshot`; scenario-vs-baseline
  ranking comparison (genuinely ambiguous at the domain-model level — see
  "What was deliberately not chosen" above); the Scenario Comparison
  frontend view; the five remaining Recharts visualizations. See
  [docs/PRD-phase-17-prioritization.md](../PRD-phase-17-prioritization.md)
  and [docs/adr/0018-prioritization-frameworks-and-dependencies.md](./0018-prioritization-frameworks-and-dependencies.md)
  for the full original scope.
- **Residual risk**: none newly introduced. No behavior change to any
  existing phase's authorization, audit, capacity, risk, scenario, or
  Phase 17/18 prioritization calculation — this phase only reads
  already-computed facts and asks a model to interpret them.
