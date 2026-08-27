# ADR 0023: Phase 23 — AI snapshot comparison explanation

- **Status:** Accepted
- **Date:** 2026-08-27

## Context

Phase 22 (ADR 0022) built snapshot diff/trend but deliberately did not
decide what Phase 23 should be. CLAUDE.md §39 stopped at Phase 22;
`docs/roadmap.md`'s "Proposed next" section named two remaining Phase
17-22 items as still open but provisional: an AI explanation of a Phase
22 snapshot comparison, and a multi-snapshot trend chart beyond a
two-point diff — alongside the longer-standing "Proposed, unscheduled"
list (Risk/Stakeholder/Prioritization import/export, a membership/
user-management UI, scenario snapshots, external integrations, SSO,
billing, organization hierarchies).

Per the phase brief's explicit audit-first instruction, the repository
was audited before any code was written: CLAUDE.md (§§4, 21, 31, 39
especially), `docs/roadmap.md`, `docs/architecture.md`,
`docs/domain-concepts.md`, every ADR through 0022, and — the phase
brief's own explicit target — the complete Phase 22 snapshot-comparison
implementation (`app/domain/portfolio_snapshot.py`,
`app/services/portfolio_snapshot.py`, `app/schemas/prioritization.py`,
`app/api/v1/prioritization.py`'s `/snapshots/compare` route, its
authorization/organization-scoping, the frontend
`PortfolioSnapshotComparisonTable`, and its tests) and the complete
Phase 19 AI priority-explanation implementation end-to-end
(`AIContextBuilder`/`AIService`/grounding/the API route/the frontend
`ExplainPriorityButton`/`AiTriggerButton`/`AiResultPanel` pattern, and
its tests). The audit confirmed no existing code handles a
snapshot-comparison explanation anywhere, and that this phase's own
brief had already correctly identified it as the one item Phase 22
explicitly named as its own still-open remainder with no further open
sub-question — unlike scenario snapshots (blocked on a `Scenario`
hard-delete lifecycle decision) or Risk/Stakeholder import/export
(blocked on a missing natural identity key), both still unresolved per
ADR 0022's Context. This phase's scope was therefore not chosen from a
list of candidates the way Phases 20-22 each were; it was confirmed
directly, exactly as the phase brief framed it.

## Decisions

### A sixth capability on the existing Phase 8 pipeline, not a new one

`AIContextBuilder`/`AIService`/`AiTriggerButton`/`AiResultPanel` are
unchanged in shape — `explain_snapshot_comparison` is a new method
following the exact same `build_for_*` → `_generate` → grounded
`AIResponseEnvelope` path every other capability already uses (CLAUDE.md
§21/§35: never a second AI orchestration path).
`AIContextBuilder.build_for_snapshot_comparison` calls
`PortfolioSnapshotService.compare(organization_id, from_snapshot_id,
to_snapshot_id)` verbatim — the exact same `(from_snapshot, to_snapshot,
items)` triple `portfolio_snapshot_comparison_to_read` already builds
the API response from — so this phase recalculates nothing: no status
(`entered`/`left`/`changed`/`unchanged`), rank, score, or category is
ever recomputed by the AI layer. `AIContextBuilder` gained one new
constructor dependency (`PortfolioSnapshotService`), reusing the same
repository wiring `app/api/v1/prioritization.py`'s own
`get_snapshot_service` factory already assembles.

### Framework-mismatch (422) and cross-organization/unknown snapshots (404) are inherited, not re-implemented

Because `build_for_snapshot_comparison` calls
`PortfolioSnapshotService.compare` unchanged, every one of that method's
existing guarantees carries straight through to the new AI route with no
new code: a nonexistent or cross-organization `from_snapshot_id`/
`to_snapshot_id` raises `NotFoundError` (404, never 403 — CLAUDE.md §27),
and comparing snapshots from two different frameworks raises
`DomainValidationError` (422) before an AI context is ever built. This
mirrors `build_for_priority_score`'s own reliance on
`ProjectPriorityScoreService.get`'s existing guarantees (ADR 0019) —
authorization and multi-tenancy are never re-derived at the AI layer,
only reused from the deterministic service underneath it.

### Grounding: a new `snapshot_comparison` reference type, one entity_id per project

`AISourceReferenceType.SNAPSHOT_COMPARISON` was added alongside
`signal`/`capacity`/`scenario`/`skill_coverage`/`priority_score`.
Unlike `priority_score` (one fact, one id), a snapshot comparison is a
*set* of per-project facts, so `AIInsightContext.known_references()`
adds one `("snapshot_comparison", project_id)` pair per comparison item
— the same "one reference per collection member" shape `signal` and
`skill_coverage` already established, not a new pattern. The generic
`ground()` function needed no changes at all — it already operates on
arbitrary `(type, id)` pairs, so this is a pure data addition, matching
ADR 0019's own observation about adding `priority_score`.

### Scope anchor: the `to` snapshot, not a synthetic comparison id

No comparison entity is ever persisted (see below), so there is no
natural id to scope the AI request's `AIEntityContext` to. The `to`
snapshot's id was chosen as the anchor (`entity_type=
"portfolio_snapshot_comparison"`, `entity_id=to_snapshot.id`) — the more
recent of the two frozen states, matching how a diff is conventionally
read ("what changed by the time of the second snapshot"). This only
affects display text and the harmless, pre-existing `("capacity",
str(scope.entity_id))` entry `known_references()` unconditionally adds
for every capability (a no-op here, since no `AICapacityFact` is ever
attached to this context) — it has no bearing on which project-level
`snapshot_comparison` references are actually grounded.

### No new persistence, no new mutation surface

Zero new tables, columns, or migrations. The comparison itself was
already established by Phase 22 as computed fresh on every read, never
cached (ADR 0022) — this phase's context-building call inherits that
discipline for free rather than introducing a second "should this be
cached" question. Verified live: re-reading the `from` snapshot
immediately after requesting its AI explanation showed a byte-identical
frozen `entries` payload, and a fresh `alembic upgrade head` against a
genuinely empty database lands unchanged at Phase 21's `9f73a340f443`
(no migration exists between Phase 21 and this phase — Phase 22 itself
added none either).

### Authorization: `Permission.AI_USE` only, no new permission, no CSRF

`POST /api/v1/ai/explain-snapshot-comparison` is gated by the same
`Permission.AI_USE` every other `/api/v1/ai/*` route already requires,
granted to every role — matching `explain-priority`/`explain-scenario`/
`explain-signal`/`summarize`/`ask` exactly. Like every other AI route,
it carries no `require_csrf` dependency: none of the five pre-existing
AI routes mutate any CapacityOS data, so the double-submit CSRF
defense-in-depth applied to genuinely mutating routes doesn't apply
here either. Verified live: a Viewer-role account was not separately
tested (every role holds `AI_USE`, matching the existing test
convention that no role-specific AI test exists anywhere in this
codebase), but an unauthenticated request was confirmed rejected (401),
matching every other protected route.

### API: one new route on the existing router, no new resource

```text
POST /api/v1/ai/explain-snapshot-comparison
```

Request body: `{from_snapshot_id, to_snapshot_id}` — the identical pair
`GET /api/v1/prioritization/snapshots/compare` already takes as query
parameters (Phase 22), since the comparison being explained is exactly
the one that pair identifies; no separate comparison id exists to
reference instead (the comparison itself is never persisted).

### Frontend: extends the existing snapshot-comparison section, no new page

`ExplainSnapshotComparisonButton` (mirroring `ExplainPriorityButton`
verbatim, down to reusing `AiTriggerButton`/`AiResultPanel` unchanged)
was added inside the existing "Portfolio snapshots" card in
`PrioritizationOverviewPage`, directly below
`PortfolioSnapshotComparisonTable` — rendered only once both a `from`
and `to` snapshot are selected and the comparison has loaded, matching
`ExplainPriorityButton`'s own "next to the deterministic result it
explains" placement. No new route, no new navigation entry.

## Consequences

- 0 new tables, 0 migrations, 0 new permissions, 0 changes to any
  existing table or permission's grant set. Verified: a fresh
  `alembic upgrade head` on a genuinely empty database lands at the
  unchanged Phase 21 head (`9f73a340f443`).
- Extended backend modules: `app/schemas/ai.py`
  (+`AISourceReferenceType.SNAPSHOT_COMPARISON`,
  +`AIExplainSnapshotComparisonRequest`), `app/services/ai_context.py`
  (+`AISnapshotComparisonItemFact`, +`AISnapshotComparisonFact`,
  +`snapshot_comparison` field on `AIInsightContext`,
  +`AIContextBuilder.build_for_snapshot_comparison`,
  +`PortfolioSnapshotService` constructor dependency),
  `app/services/ai_service.py` (+`AIService.explain_snapshot_comparison`,
  a snapshot-comparison block in `serialize_context`), `app/api/v1/ai.py`
  (+`/explain-snapshot-comparison` route, `get_ai_service` wiring). No
  new backend files.
- New frontend modules:
  `features/ai/hooks/useAiExplainSnapshotComparison.ts`,
  `features/ai/components/ExplainSnapshotComparisonButton.tsx`.
  Extended: `features/ai/types/ai.ts`, `features/ai/api/aiApi.ts`,
  `features/prioritization/views/PrioritizationOverviewPage.tsx`
  (renders `ExplainSnapshotComparisonButton` below the existing
  comparison table).
- Backend: +13 tests (5 service-level in
  `tests/services/test_ai_service.py` — context serialization,
  grounding/known-references, unavailable/error/ok paths; 8 API-level in
  `tests/api/test_ai.py`, including a cross-organization 404 regression,
  a framework-mismatch 422 regression, an unauthenticated 401 check, a
  never-mutates-either-snapshot check, and a structural check that
  `AIModelOutput` carries no score/rank field at all) — 963 total, all
  passing. `ruff check` and `uv run pyright` (strict) both fully clean.
- Frontend: 0 new tests — `ExplainSnapshotComparisonButton`/
  `useAiExplainSnapshotComparison` are thin wrappers around
  already-tested primitives (`AiTriggerButton`/`AiResultPanel`),
  matching `ExplainPriorityButton`'s own established Phase 19 precedent
  (itself matching `ExplainScenarioButton`/`ExplainSignalButton`'s
  Phase 8 precedent) — only the shared primitives and one representative
  trigger (`SummarizeButton`) are unit-tested anywhere in this codebase.
  223 total, all passing (one pre-existing, unrelated `LoginPage.test.tsx`
  timeout under full-suite parallel load was confirmed to pass cleanly
  in isolation — not a regression from this phase). `oxlint`/
  `tsc -b --noEmit` clean (the same 2 pre-existing, unrelated
  `AuthContext.tsx` warnings as every prior phase). Production build
  succeeds.
- Live verification: a real uvicorn instance was started against a
  genuinely fresh, migrated, file-backed SQLite database with a real
  Owner account bootstrapped via `scripts/create_first_owner.py` and
  `AI_PROVIDER=mock`. A real authenticated session (cookie login,
  double-submit CSRF token) walked the full golden path over real
  HTTP — create project → create RICE framework → score it (400) →
  take snapshot 1 → re-score (3600) → take snapshot 2 → confirm the
  Phase 22 `/snapshots/compare` read still reports `changed` correctly
  → request the Phase 23 AI explanation (confirmed `status: "ok"`) →
  re-read snapshot 1 (confirmed still frozen at exactly 400, untouched
  by the AI call) → create a MoSCoW framework/snapshot and confirm
  comparing across frameworks still 422s before the AI layer is reached
  → confirmed a nonexistent snapshot id 404s → confirmed an
  unauthenticated request 401s → created a second organization, took a
  snapshot there, and confirmed that requesting an explanation from the
  Default organization referencing the other organization's snapshot
  404s (not 403) even though the same account holds Owner membership in
  both organizations — proving the boundary is enforced against the
  session's *active* organization, not merely account membership — plus
  a log scan confirming no password, CSRF token, or session token value
  was ever written to the server log. No browser or interactive UI
  walkthrough was performed — no such tool is available in this
  environment (the same disclosed limitation as every prior phase).
- **Deferred, not dropped**: a multi-snapshot trend chart beyond a
  two-point diff; scenario snapshots (still blocked on a `Scenario`
  hard-delete lifecycle decision, per ADR 0022's Context); an AI
  interpretation of the Phase 20 scenario-vs-baseline comparison (left
  for a future phase, per Phase 20's own brief); the five remaining
  Recharts visualizations; Risk/Stakeholder/Prioritization/
  `ProjectDependency`/`PortfolioSnapshot` import/export registration
  (still blocked on a missing natural identity key, per ADR 0022's
  Context); a membership/user-management UI.
- **Known limitations**: the mock AI provider used by the test suite and
  local development (`MockAIProvider`) was not extended with any
  `snapshot_comparison`-specific marker — it returns its existing
  generic "no material capacity risk detected" response for this
  capability exactly as it already does for `explain-priority`, since
  neither capability's mock coverage asserts specific generated content,
  only that a grounded `ok` envelope is returned. This matches
  `explain-priority`'s own established test-depth boundary (ADR 0019),
  not a gap introduced by this phase.
- **Residual risk**: none newly introduced. No behavior change to any
  existing phase's authorization, audit, capacity, risk, scenario, or
  Phase 17-22 prioritization/snapshot/comparison behavior — this phase
  only reads an already-computed Phase 22 comparison result and asks a
  model to interpret it.
