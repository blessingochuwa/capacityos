# ADR 0022: Phase 22 — portfolio snapshot diff/trend

- **Status:** Accepted
- **Date:** 2026-08-25

## Context

Phase 21 (ADR 0021) built `PortfolioSnapshot` — an explicit, immutable,
point-in-time saved ranking — but deliberately left "compare two
snapshots" out of its own bounded scope. CLAUDE.md §39 stopped at Phase
21; `docs/roadmap.md`'s "Proposed future phases" section named several
still-open items but marked all of them provisional, not a commitment.

Per the phase brief's explicit instruction not to assume the next phase
is simply the first item in a deferred list, the repository was audited
first — CLAUDE.md (§§4, 21, 31, 39 especially), `docs/roadmap.md`,
`docs/architecture.md`, `docs/domain-concepts.md`, every ADR through
0021, the Phase 17-21 prioritization implementation, and — newly for
this audit — the organization/membership API
(`app/api/v1/organizations.py`) and the Phase 6 import/export system
(`app/services/import_service.py`, `app/domain/import_export_*.py`),
neither of which any prior phase's audit had inspected in depth. That
audit found seven named candidates (snapshot diff/trend; scenario
snapshots; AI explanation of the Phase 20 comparison; the five remaining
Recharts visualizations; Risk/Stakeholder import/export; a
membership/user-management UI; other unscheduled roadmap items) and
found two of them — scenario snapshots and Risk/Stakeholder
import/export — to each carry a genuine open sub-question that would
need its own decision before either was buildable (respectively: what
happens to a scenario snapshot when its `Scenario` is hard-deleted, since
`Scenario` — unlike `PrioritizationFramework` — supports a real, non-soft
delete; and what natural identity key a Risk/Stakeholder CSV row would
upsert-match against, since neither entity has a Person/Project-style
key). These trade-offs were presented to the user via a blocking
question rather than guessed. **Snapshot diff/trend was selected** — the
only candidate with no open sub-question of its own, building directly
and exclusively on the now-stable Phase 21 foundation.

## Decisions

### Pure diff over already-frozen data — no new domain ambiguity

`GET /api/v1/prioritization/snapshots/compare?from_snapshot_id=&to_snapshot_id=`
diffs two already-taken, immutable `PortfolioSnapshot.entries` payloads.
`app/domain/portfolio_snapshot.py::compare_snapshot_entries` is pure and
DB-free (mirrors `tests/domain/test_prioritization.py`'s discipline) and
never imports `calculate_priority_score` or any other piece of the
scoring engine — a snapshot's entries are historical facts, already
computed once by Phase 17-18's engine at capture time; comparing two
snapshots is nothing more than comparing those frozen facts pairwise.
This is the one candidate the Phase 21 audit had already established
required no new domain decision, because Phase 21 had already frozen
everything a diff would ever need.

### Four statuses: entered, left, changed, unchanged

A project appearing in only the `to` snapshot is `ENTERED`; only in
`from` is `LEFT`; in both with an identical `(rank, score, category)`
tuple is `UNCHANGED`; in both but differing is `CHANGED`. `CHANGED` is
compared as a tuple, not per-field, matching
`ScenarioPriorityComparisonItem.changed`'s own precedent (ADR 0020) — a
project whose rank moved because a NEW higher-scoring project entered
the ranking (its own score unchanged) is correctly `CHANGED`, not
`UNCHANGED`, since rank is relative to the whole ranked set, not an
intrinsic property of the project alone. Verified both by a dedicated
domain test and live: re-scoring one project and adding a second,
higher-scoring one left the first project's rank at 1 in both snapshots
(the added project scored lower) — reported `UNCHANGED` for rank but the
score change still correctly produced `CHANGED` overall, and a separate
live run confirmed a genuinely `UNCHANGED` case (rank AND score both
identical) by keeping one project's score far enough ahead that a new
entrant never displaced it.

### Same-framework-only, rejected with 422

Comparing two snapshots from different frameworks is rejected with a
`DomainValidationError` (422) — a RICE score and a WSJF score aren't
comparable numbers, so allowing a cross-framework diff would silently
produce a meaningless comparison rather than a useful one. This was
confirmed with the user as part of the implementation-plan sign-off
before any code was written (the alternative — allowing it anyway — was
explicitly offered and declined). Verified live: comparing a RICE
snapshot against a MoSCoW snapshot returned 422.

### Never persisted — computed fresh on every read

The comparison result has no table of its own and is never cached — the
same "derive, never cache" discipline every Phase 17-21 result follows
(`Risk.exposure`, every `ProjectPriorityScore`, every Scenario result,
Phase 20's own comparison). Verified live: reading a snapshot immediately
before and after running a comparison against it showed byte-identical
frozen `entries` — the comparison endpoint never writes anything back to
either snapshot.

### Authorization: `PRIORITIZATION_READ`, no new permission

Both snapshot ids are resolved through the existing org-scoped
`PortfolioSnapshotRepository.get` — a cross-organization id 404s exactly
like every other resource in this router. Read-only, so
`Permission.PRIORITIZATION_READ` (every role, reused unchanged) is the
only gate, matching `GET .../portfolio` and Phase 20's
`GET .../priority-comparison` exactly. Verified live: a Viewer received
200 comparing two snapshots.

### No audit event

Matches this router's own established convention that reads are never
audited — `GET .../portfolio`, `GET .../dependency-graph`, and Phase 20's
`GET .../priority-comparison` are unaudited too; only mutations produce
an `AuditEvent` in this codebase.

### API: one new route on the existing router, no new resource

```text
GET /api/v1/prioritization/snapshots/compare?from_snapshot_id=&to_snapshot_id=
```

No new top-level resource, no path-id collision with a future
`GET /snapshots/{id}` (none exists) — matches every prior phase's "extend
the existing router" precedent.

### Frontend: extends the existing "Portfolio snapshots" card

A From/To snapshot picker and `PortfolioSnapshotComparisonTable` were
added inside the existing `PrioritizationOverviewPage` card Phase 21
built — no new route, no new navigation entry, matching Phase 19-21's own
"extend the existing view" precedent. `PortfolioSnapshotComparisonTable`
mirrors `PriorityComparisonTable`'s (Phase 20) established
"badge + rank + score" table shape closely enough to reuse its visual
language without sharing code, since the two compare genuinely different
things (baseline-vs-scenario vs. snapshot-vs-snapshot). No new charting
dependency (CLAUDE.md §29) — this is a table, matching every prior
prioritization phase's own precedent for the same reasoning.

## Consequences

- 0 new tables, 0 migrations, 0 new permissions, 0 new `AuditAction`
  members. 0 changes to any existing table or permission's grant set.
  Verified: a fresh `alembic upgrade head` on a genuinely empty database
  lands at the unchanged Phase 21 head (`9f73a340f443`).
- New backend module: `app/domain/portfolio_snapshot.py`
  (`SnapshotComparisonStatus`, `SnapshotComparisonItem`,
  `compare_snapshot_entries`). Extended:
  `app/services/portfolio_snapshot.py` (+`compare`),
  `app/schemas/prioritization.py` (+`SnapshotComparisonItemRead`,
  +`PortfolioSnapshotComparisonRead`,
  +`portfolio_snapshot_comparison_to_read`),
  `app/api/v1/prioritization.py` (+1 route).
- New frontend modules:
  `features/prioritization/{hooks/useSnapshotComparison,
  components/PortfolioSnapshotComparisonTable}`. Extended:
  `features/prioritization/types/prioritization.ts`,
  `features/prioritization/api/prioritizationApi.ts`,
  `features/prioritization/views/PrioritizationOverviewPage.tsx`,
  `test/fixtures.ts` (+2 fixture builders).
- Backend: +19 tests (12 domain in
  `tests/domain/test_portfolio_snapshot.py` — entered/left/changed/
  unchanged, a rank change caused solely by a new higher-scoring entrant,
  MoSCoW category changes, incomplete-score comparisons, `project_name`
  preference/fallback, result ordering; 7 API in
  `tests/api/test_portfolio_snapshots.py` — the same set of cases over
  real HTTP plus framework-mismatch rejection, immutability, RBAC-for-read,
  and the explicit cross-organization/IDOR tests every new resource
  requires) — 950 total, all passing. `ruff check` and `uv run pyright`
  (strict) both fully clean.
- Frontend: +5 tests
  (`PortfolioSnapshotComparisonTable.test.tsx`) — 223 total, all passing.
  `oxlint`/`tsc -b --noEmit` clean (the same 2 pre-existing, unrelated
  `AuthContext.tsx` warnings as every prior phase). Production build
  succeeds.
- Live verification: a real uvicorn instance was started against a
  genuinely fresh, migrated, file-backed SQLite database with a real
  Owner account bootstrapped via `scripts/create_first_owner.py`. A real
  authenticated session (cookie login, double-submit CSRF token) walked
  the full golden path over real HTTP — create project → create RICE
  framework → score it (400) → take snapshot 1 → re-score (3600) → add a
  second, lower-scoring project and score it → take snapshot 2 → compare
  1→2 (confirmed the first project `changed`, score 400→3600, rank
  unchanged at 1; the second project `entered`) → create a MoSCoW
  framework and its own snapshot → compare across the two different
  frameworks (confirmed 422, not a silently meaningless diff) → re-read
  snapshot 1 (confirmed its frozen score was still exactly 400, untouched
  by any comparison read) — plus confirmed unauthenticated (401), a
  nonexistent snapshot id (404), and a Viewer successfully reading a
  comparison (200, proving `PRIORITIZATION_READ`'s all-roles reach), and
  a log scan confirming no password or secret value was ever written to
  the server log. No browser or interactive UI walkthrough was
  performed — no such tool is available in this environment (the same
  disclosed limitation as every prior phase).
- **Deferred, not dropped**: scenario snapshots (needs its own product
  decision about `Scenario`'s hard-delete lifecycle, per this ADR's
  Context); an AI explanation of a snapshot comparison; a multi-snapshot
  trend chart beyond a two-point diff; the five remaining Recharts
  visualizations; Risk/Stakeholder import/export (needs its own decision
  about an identity/matching key); a membership/user-management UI.
- **Residual risk**: none newly introduced. No behavior change to any
  existing phase's authorization, audit, capacity, risk, scenario, or
  Phase 17-21 prioritization/snapshot behavior — this phase only reads
  two already-persisted, already-frozen rows and diffs them in memory.
