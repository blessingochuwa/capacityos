# ADR 0038: Phase 38 — PortfolioSnapshot export decision (Outcome A: neither import nor export)

- **Status:** Accepted
- **Date:** 2026-08-30

## Context

Phase 37 registered `ProjectDependency` into the import/export pipeline
and deliberately left `PortfolioSnapshot` unregistered on both sides,
concluding that import is categorically unsound (immutable, derived,
historical) but flagging that export was "not unsafe in principle" and
deserved its own dedicated audit — one Phase 37's own scope explicitly
excluded. Phase 38 exists to perform that audit and decide, deliberately,
whether `PortfolioSnapshot` should be export-only, and if so, to design
the smallest capability distinction that would make that safe.

Per the phase brief's own first instruction, actual repository state was
checked before any audit began — not assumed from the prior report:

```
git status --short   → (empty — clean working tree)
git log -5 --oneline → 53bc563 Implement Phase 37 ... (HEAD)
git diff --stat      → (empty)
git diff --name-only → (empty)
```

Phase 37 (`53bc563`) was already committed and pushed to `origin/main`
— contrary to the brief's premise that it was "uncommitted." The actual,
verified state was used, not the assumption. No newer ADR exists beyond
0037.

## Audit — the import/export architecture, re-verified directly

Re-read (not merely re-cited from the Phase 37 report) `app/domain/
import_export_parsing.py`, `import_export_diff.py`, `app/services/
import_service.py`, `export_service.py`, `app/api/v1/imports.py`,
`exports.py`. Confirmed directly:

- `ImportEntityType` has exactly 14 members (`person` through
  `project_dependency`), all "operational source data" entities — every
  one of them something a spreadsheet-onboarding organization would
  plausibly already have and want backed up, per ADR 0006's own founding
  charter (quoted below).
- Both `/api/v1/imports/{entity_type}/...` and `/api/v1/exports/
  {entity_type}` validate `entity_type` against the **same** shared
  enum, with no per-route or per-entity capability distinction. This is
  the exact coupling Phase 37 flagged.
- `ImportService._prepare`'s `preparers` dict is a plain `dict[
  ImportEntityType, Callable]` — confirmed by reading it directly.
  Adding an enum member without a corresponding entry would raise
  `KeyError` on `preparers[entity_type](...)`.
- **Refinement of Phase 37's own claim, verified by reading `app/core/
  exceptions.py` directly**: this would *not* be a raw, unhandled crash.
  `register_exception_handlers` installs a catch-all `@app.
  exception_handler(Exception)` that logs the real exception server-side
  and returns a generic `500 {"detail": "An unexpected error occurred.
  Please try again."}` to the client — no stack trace leak (CLAUDE.md
  §27 is honored). It is still an **undignified, generic 500** rather
  than a designed, informative rejection, and still the kind of gap
  worth avoiding deliberately rather than by accident.

## Audit — PortfolioSnapshot itself, re-verified directly

`app/models/portfolio_snapshot.py`'s own class docstring, read in full
this phase: *"An explicit, user-triggered, **immutable** record of one
framework's computed portfolio ranking at a point in time... Deliberately
**NOT** read back as an input to any live computation... No PATCH/DELETE
route exists for this entity — immutable and append-only, **matching
AuditEvent's own shape exactly**."* No `UniqueConstraint` exists on the
table — no natural key, and none was invented (per the brief's explicit
instruction). `app/services/portfolio_snapshot.py::PortfolioSnapshotService.
create` takes **only** `framework_id`; every other field (`entries`:
each ranked project's `score`/`rank`/`breakdown`/`missing_criteria`/
`category`) is computed server-side from `ProjectPriorityScoreService.
rank_portfolio` and frozen — there is no user-supplied content of any
kind. `app/api/v1/prioritization.py`: creation is `PRIORITIZATION_MANAGE`
-gated (Admin/Owner), but the **read** route
(`GET /api/v1/prioritization/snapshots`) is `PRIORITIZATION_READ`-gated
— granted to **every role including Viewer**. `PortfolioSnapshotRepository.
list_` is already organization-scoped, paginated, newest-first.

## The product-evidence audit — why export was NOT approved

Five independent, converging pieces of evidence were checked, each read
directly this phase rather than assumed:

1. **`AuditEvent` — the entity `PortfolioSnapshot` is explicitly modeled
   after — has never been exportable, anywhere, in this codebase's
   history.** `app/api/v1/audit.py` was read directly: it exposes
   exactly one route, `GET /api/v1/audit` (a paginated JSON list) — no
   CSV/download route, no dedicated export mechanism of any kind,
   despite `AuditEvent` being the single entity in this system most
   plausibly needing compliance/backup export if any did. Since
   `PortfolioSnapshot`'s own docstring explicitly claims this exact
   analogy, the absence of any export path for its named precedent is
   direct, on-point evidence against building one here.
2. **The PRD's own words, read directly from `docs/PRD-phase-17-
   prioritization.md` §7-8**: *"stored as a genuine historical record
   (like `AuditEvent`)... for **trend/history purposes**."* "Trend/
   history" describes an **in-app** viewing need, not an external
   backup/reporting one — and nowhere in the PRD, across every section,
   does "export," "download," "CSV," or "backup" appear in connection
   with snapshots.
3. **ADR 0006's own founding charter, re-quoted directly**: *"a team
   onboarding CapacityOS... has no way to get **current** data back out
   for backup, inspection, or reuse elsewhere."* This describes
   operational **source** data — the facts a team would have had before
   adopting the tool. A `PortfolioSnapshot` is definitionally the
   opposite: a derived artifact the tool itself produces *after*
   adoption, never something migrated in from a spreadsheet or needed
   to migrate back out for onboarding purposes.
4. **The specific "see the trend" need is already built and shipped**:
   `docs/adr/0024-portfolio-snapshot-trend.md` — a dedicated, in-app
   multi-snapshot score-over-time chart, consuming the existing `GET
   .../snapshots` route directly, with **zero backend changes**. Export
   would not fill a gap this feature doesn't already close; it was
   purpose-built for exactly the historical-comparison need snapshots
   exist to serve.
5. **Zero frontend signal.** Every frontend file consuming
   `PortfolioSnapshot` was grepped for `export`/`download`/`csv`
   (case-insensitive) this phase — the only hits were TypeScript's own
   `export function` keyword. No button, no disabled placeholder, no
   TODO comment, nothing hinting a download feature was ever
   contemplated for this entity.

No evidence — in the PRD, any ADR, the roadmap, the domain model, or the
frontend — establishes a genuine backup/reporting/audit need for
snapshot export. Every one of the five checks points the same direction,
independently.

## Decision

**Outcome A: `PortfolioSnapshot` remains intentionally neither
importable nor exportable.** No capability architecture is built. No
production code changes. The Phase 37 deferral is now closed with an
explicit, evidence-backed "no," not merely left as an open question.

This resolves the phase brief's own explicit gate directly: *"If the
evidence does not justify PortfolioSnapshot export, document that
decision and stop without introducing capability infrastructure
unnecessarily."* The evidence does not justify it, so no capability
architecture — generic or special-cased — was built. Building an
`importable`/`exportable` capability model now, for a single entity that
turns out not to need either, would be exactly the "architecture without
a need" the brief warned against; it remains a reasonable, cheap thing
to build **when** a second entity's registration genuinely requires the
distinction, not preemptively.

## Why import is (still) prohibited

Unchanged from Phase 37, reconfirmed by this phase's own re-read of the
model: no natural key exists or could be invented without misrepresenting
what a snapshot *is*; `create()` accepts no content a row could supply;
accepting a file-uploaded `score`/`rank`/`breakdown` would let an import
fabricate a historical ranking that never existed, the exact failure ADR
0006's own "import must not become a second capacity engine or a second
set of business rules" principle forbids.

## Capability architecture decision

**Not built.** The `importable`/`exportable`/`both` distinction the
brief sketched as Option B was evaluated and found premature: it would
be built for a single entity (`PortfolioSnapshot`) that this same audit
concluded doesn't need *either* capability, which is not "the smallest
coherent capability architecture" for any real need — it would be
architecture built on spec, for nothing. If a future phase registers a
genuinely export-only (or import-only) entity, that phase should build
the distinction then, sized to what that entity actually requires.

## Exact implementation scope

Two regression tests only, added to lock the decision in as intentional
and tested rather than an implicit absence someone could accidentally
reverse without noticing — the same discipline ADR 0035's
(`USER_WRITE`) single locking test already established for a
zero-production-code decision:

- `tests/api/test_imports.py::test_portfolio_snapshot_import_is_
  deliberately_unsupported` — `POST /imports/portfolio_snapshot/
  validate` → 422.
- `tests/api/test_exports.py::test_portfolio_snapshot_export_is_
  deliberately_unsupported` — `GET /exports/portfolio_snapshot` → 422.

Both 422s are FastAPI's own enum-path-parameter validation (`"portfolio_
snapshot"` is not a member of `ImportEntityType`) — **not** a
special-cased rejection, since none was built. Both tests exist purely
to document and lock in the decision; neither required a single line of
production code.

## Backend changes

None to production code. Two new test functions (above).

## Frontend changes

None. No frontend code was touched.

## API/OpenAPI changes

None. `docs/openapi.json` was not regenerated — the API contract is
byte-for-byte unchanged (no enum member added, no schema touched).

## Authorization/security

Unchanged — verified live. `Permission.EXPORT_USE` (Member+) continues
to gate every export route exactly as before; `Permission.IMPORT_USE`
(Manager+) continues to gate every import route exactly as before.

One incidental, pre-existing FastAPI behavior was observed and is
recorded here rather than silently noticed and dropped: for an
**authorized** caller (Owner), `GET /exports/portfolio_snapshot`
returns 422 (the enum validation error surfaces, since the permission
check passes and dependency resolution continues to the path-parameter
coercion). For an **unauthorized** caller (Viewer, who lacks
`EXPORT_USE`), the same request returns 403 instead — because FastAPI's
dependency solver invokes `Depends()` callables *during* its solve pass,
and `require_permission`'s raised `ForbiddenError` short-circuits before
the framework gets to also notice the invalid `entity_type`. This is
existing FastAPI/Starlette dependency-resolution behavior, not something
this phase introduced (0 production code changed) — and it is not a
security concern: an unauthorized caller is denied (403) regardless of
what garbage `entity_type` they supply; the authorization boundary holds
in every observed case, it merely reports a different (also-correct)
reason first.

## Multi-tenancy/IDOR verification

Not applicable to what changed (nothing was registered), but reconfirmed
this phase, live, that the unmodified system's boundary holds: an
existing entity (`project`) still exports correctly and only for the
caller's own organization; `portfolio_snapshot` is rejected identically
regardless of caller or organization, since the rejection happens before
any organization-scoped query would ever run.

## Database/migration impact

None. Verified: `git status apps/api/alembic/` empty (no new migration
file); fresh SQLite → `alembic upgrade head` reaches the same head
(`b8b6cb4c08bf`, unchanged since Phase 36) with zero pending migrations.

## Tests added and full totals

Backend: **+2** (both described above). Full suite: **1060 passed**
(was 1058). `ruff check .` clean. `uv run pyright` (strict) **0
errors**.

Frontend: **0** changes — per the brief's own conditional instruction
("Run the full frontend test suite if frontend code changes"), the
frontend suite was not re-run, since no frontend file was touched.

## Lint/typecheck/build results

Backend: `ruff check .` clean, `uv run pyright` (strict) 0 errors,
full `pytest` 1060 passed. Frontend: not applicable — unchanged.

## Fresh DB verification

Fresh SQLite → `alembic upgrade head` → `b8b6cb4c08bf` (unchanged) —
confirmed directly.

## Live/API verification

A real `uvicorn` server was started against that freshly-migrated
database, bootstrapped via `scripts/create_first_owner.py`. Exercised
over real HTTP: an existing export (`project`, CSV) confirmed still
working for the Owner; `portfolio_snapshot` confirmed rejected (422) on
both `/imports/portfolio_snapshot/validate` and `/exports/
portfolio_snapshot` for the Owner; a Viewer account added and confirmed
denied (403) on export generally, including for `portfolio_snapshot`
specifically (surfacing the incidental dependency-ordering behavior
documented above). Server log scanned for `password|token|hash|secret|
csrf` (beyond expected CSRF field-name mentions) — no matches. Server
stopped and the scratch database removed afterward.

## Browser verification

Not performed — browser automation is unavailable in this environment
(the same disclosed limitation as every prior phase). No frontend
change was made regardless.

## Deviations

None from the audited evidence.

## Assumptions

None requiring a blocking question. The decision was resolved
mechanically from five independently-converging, directly-read sources
(the model's own docstring, the PRD, ADR 0006, the already-shipped trend
chart, and the frontend's actual code) — never from product taste.

## Known limitations

`PortfolioSnapshot` history remains viewable only in-app (`GET .../
snapshots`, the trend chart, the comparison view) — an organization
wanting to archive snapshot history externally has no built-in path to
do so today. This is a deliberate, documented limitation, not an
oversight.

## Residual risks

None. No new surface was added; the pre-existing gap Phase 37 flagged
(a naive symmetrical registration crashing on import) was closed by
*not* registering the entity at all, the simplest possible closure.

## Technical debt

None added.

## Explicitly deferred work

The `importable`/`exportable` capability distinction itself remains
unbuilt — deliberately, since no entity currently needs it. A future
phase registering a genuinely import-only or export-only entity should
build the smallest version of that distinction sized to what that
entity actually requires, not speculatively now. If organization-level
snapshot archival is ever explicitly requested as a product need, it
should be evaluated on its own terms (e.g., a dedicated read/export
route scoped to `PortfolioSnapshot` specifically, outside the generic
Phase 6 pipeline that models operational source data) rather than
retrofitted into this system.

## Confirmation

Phase 39 was **not** started. Nothing in this phase was committed or
pushed.
