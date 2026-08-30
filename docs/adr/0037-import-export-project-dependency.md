# ADR 0037: Phase 37 — Import/export registration for ProjectDependency (PortfolioSnapshot deferred)

- **Status:** Accepted
- **Date:** 2026-08-30

## Context

Phase 36 registered Risk, Stakeholder, and `ProjectPriorityScore` into the
existing Phase 6 import/export pipeline, deliberately deferring
`ProjectDependency` and `PortfolioSnapshot` as outside its own named
three-domain scope, each flagged as carrying "its own unaudited open
question." Phase 37's brief asked for exactly that audit, with an
explicit, repeated instruction not to force `PortfolioSnapshot` into the
pipeline merely for symmetry with `ProjectDependency`. This ADR records
what the audit found for each entity and the resulting decision — to
register the first and leave the second deferred.

Per the phase brief's own starting instruction, `git status`/`git log`
were checked before any audit began: the working tree was clean and
Phase 36 (`01225d0`) was already committed and pushed to `origin/main`,
contrary to the brief's premise that it was "uncommitted" — the actual,
verified state was used, not the assumption.

## Audit findings — ProjectDependency

`app/models/project_dependency.py`: `organization_id`, `from_project_id`,
`to_project_id` (both required FKs, `ON DELETE CASCADE`),
`dependency_type` (`blocks`/`related`/`enables`), `created_at` only —
**no `updated_at` at all**, matching `TeamMembership`'s precedent
exactly: *"Created/added or removed only — no 'updated_at' ... a
grant-shaped row, not a business entity with an editable history."*
**A genuine, complete natural key already exists**:
`UniqueConstraint(from_project_id, to_project_id, dependency_type)` —
the table's own identity, needing no new column. `ProjectDependencyService.
create` independently enforces: both projects exist and are
same-organization (`NotFoundError` otherwise), self-dependency rejected
unconditionally for every `dependency_type`
(`DomainValidationError("A project cannot depend on itself.")`), the
exact-triple duplicate rejected (`ConflictError`), and — for `BLOCKS`
edges only — a DFS cycle check (`app/domain/prioritization.py::
detects_cycle`) against every existing `BLOCKS` edge in the organization.
Route: `POST/DELETE /projects/{project_id}/dependencies`, gated by
`require_project_access(Permission.PRIORITIZATION_SCORE)` — the same
Manager+ tier already proven safe to register in Phase 36 for
`ProjectPriorityScore`. `ProjectDependencyRepository.list_for_organization`
(org-wide, unfiltered by project) and `list_blocks_edges` (the exact
`(from, to)` shape `detects_cycle` expects) already exist, built for the
Dependency Graph view — both reused verbatim, not reimplemented.

**Decision: register `project_dependency`.** Every one of the phase
brief's five gate questions (identity, references, lifecycle,
authorization, multi-tenancy) resolves mechanically from executable code
already on disk — no blocking question was needed.

## Audit findings — PortfolioSnapshot

`app/models/portfolio_snapshot.py`'s own docstring states the disposition
directly: *"An explicit, user-triggered, **immutable** record of one
framework's computed portfolio ranking at a point in time... Deliberately
**NOT** read back as an input to any live computation... No PATCH/DELETE
route exists for this entity — immutable and append-only, **matching
AuditEvent's own shape exactly**."* `PortfolioSnapshotService.create`
takes only a `framework_id` — every other field (`entries`: each ranked
project's `score`/`rank`/`breakdown`/`missing_criteria`/`category`) is
computed server-side from `ProjectPriorityScoreService.rank_portfolio`
and frozen; there is **no user-supplied content of any kind** a CSV row
could represent. No natural key exists on the table at all (no
`UniqueConstraint`) — unsurprising, since nothing about "the ranking as
it stood at this moment" has an independent identity to upsert-match
against; every capture is, by definition, a new historical fact.

**A: Identity** — none exists, and none could be invented without
misrepresenting what a snapshot *is* (a frozen instant, not a mutable
record with its own life to key on).

**C: Lifecycle** — this is the phase brief's own named disqualifying
case, quoted directly: *"If a snapshot is fundamentally historical,
immutable, derived, tied to a particular database state... do not force
it into the existing import pipeline."* Every one of those four
conditions is independently true here, each confirmed against executable
code, not inferred. Accepting a file-uploaded `score`/`rank`/`breakdown`
into this table would let an import fabricate a historical portfolio
ranking that never actually existed — the exact failure mode ADR 0006's
own founding principle warns against: *"import must not become a second
capacity engine or a second set of business rules."* Import is
therefore **unsound** categorically, not merely under-specified.

**Export considered independently, per the brief's explicit instruction
to weigh it separately.** `entries`' contents (`score`/`rank`/`breakdown`)
are already-frozen literal JSON on the row — reading them back out isn't
the same act as `ExportService`'s own documented prohibition on
*computing* a derived value at export time (its docstring: *"no derived
value... can accidentally leak into an export"*, aimed at injecting a
live-computing service like `CapacityService`, which this would not do).
So export in isolation is not the same category of problem import is.
**But the existing architecture provides no mechanism to offer export
without also offering import**: `/api/v1/imports/{entity_type}/...` and
`/api/v1/exports/{entity_type}` both validate `entity_type` against the
*same* shared `ImportEntityType` enum with no per-route capability
distinction — every entity currently in that enum is reachable on both
paths. Adding `PORTFOLIO_SNAPSHOT` to the enum without a corresponding
`ImportService._prepare` dispatch entry would leave
`POST /imports/portfolio_snapshot/validate` hitting an unhandled
`KeyError` (an accidental crash path, not a designed rejection) unless a
new "this entity doesn't support import" guard were built —
which is new generic infrastructure, explicitly out of this phase's
scope (§1/§5: *"This is NOT a request to introduce generic import/export
infrastructure"*; *"Do NOT silently invent an import contract just to
make the feature symmetrical"*).

**Decision: `portfolio_snapshot` is NOT registered — neither import nor
export.** Not because export is unsafe in principle, but because
offering it safely, today, would require building exactly the kind of
new infrastructure this phase was told not to build. This is a
mechanically-derived conclusion from executable code and the phase
brief's own stated constraints, not a product-taste call — no blocking
question was needed here either.

## Import vs. export decision for each

| Entity | Import | Export | Basis |
|---|---|---|---|
| `ProjectDependency` | Yes | Yes | Complete natural key, no mutable fields, safe authorization tier, org-scoped references — every gate question resolves from existing code. |
| `PortfolioSnapshot` | No | No (deferred) | Import: categorically unsound (immutable/derived/historical, no user-supplied content to import). Export: not unsafe in principle, but the shared-enum architecture offers no way to expose it without simultaneously exposing an unguarded, crash-prone import path — closing that gap is new infrastructure, out of scope. |

## Existing architecture reused

Identical registration shape to every entity Phase 6/7/36 already
established: one new `ImportEntityType` member, one `ENTITY_COLUMNS`
entry, one `_TEMPLATE_EXAMPLES` entry, one `normalize_project_dependency_
row` function, dispatch wiring in `ImportService`/`ExportService`. **Zero
new routes** — `/api/v1/imports/project_dependency/...` and
`/api/v1/exports/project_dependency` work immediately once the enum
member exists, exactly as documented in ADR 0036.

**No update case exists for this entity** (mirrors `TeamMembership`
exactly, not the create-or-update shape Risk/Stakeholder/
`ProjectPriorityScore` use): `normalize_project_dependency_row` returns
only `"create"` or `"unchanged"`, matching `normalize_team_membership_
row`'s identical two-outcome shape — an existing exact-triple match is
always `"unchanged"`, never `"update"`, since there is nothing on the row
that could be updated.

**Two references per row under different column names** — the existing
`resolve_project_reference` is hardcoded to the single `"project_id"`/
`"project_external_id"` pair every other entity uses; `ProjectDependency`
needs `"from_project_id"`/`"from_project_external_id"` and
`"to_project_id"`/`"to_project_external_id"`. A new, parameterized
`resolve_named_project_reference(row, lookup, *, id_field,
external_id_field)` was added and used for both — the same
generalization technique Phase 36 already established with
`resolve_optional_person_reference`, not a new mechanism.
`ImportService._project_lookup_maps` was extended to scan all three
column-name pairs (plain, `from_`, `to_`) into the same `Project`
catalog, mirroring how Phase 36 extended `_person_lookup_maps` for
Risk's `owner_person_id`/`owner_person_email`.

**Self-dependency vs. cycle detection — two different checks, two
different places, matching the service's own division exactly.**
Self-dependency (`from == to`) applies to every `dependency_type` and
needs no cross-row state, so it is checked inside
`normalize_project_dependency_row` itself (Level 2/3, pure). Cycle
detection applies only to `BLOCKS` edges and — because a later row in
the same file must see a cycle an *earlier* row in that same file would
already close — needs batch-order simulation across the whole file. This
lives in `ImportService._check_project_dependency_cycle`, a new method
built as a structural mirror of `_check_working_schedule_overlap`
(WorkingSchedule's own overlap pre-check): seed the organization's
existing `BLOCKS` edges (`list_blocks_edges`, already built for the
Dependency Graph view), then walk the file in order, calling
`app/domain/prioritization.py::detects_cycle` — the *exact* function
`ProjectDependencyService.create` already uses, never a second
implementation — and appending each newly-accepted edge to the same
mutable list so the next row sees it. Verified live: a three-row batch
where row 3 closes a cycle rows 1–2 introduced (with none of it in the
database yet) is correctly rejected only on row 3.

## Backend changes

`app/domain/import_export_parsing.py` (+1 `ImportEntityType` member,
`ENTITY_COLUMNS`/`_TEMPLATE_EXAMPLES` entries — no packed-cell field
needed, unlike Phase 36's `values` column); `app/domain/import_export_
diff.py` (+`ProjectDependencyFact`, +`ProjectDependencyPayload`,
+`resolve_named_project_reference`, +`normalize_project_dependency_row`
— **no change to `ReferenceLookup`'s shape**, unlike Phase 36, since the
new resolver reads the existing `projects_by_id`/`projects_by_external_id`
fields, so no existing `ReferenceLookup(...)` call site needed updating
this time); `app/repositories/project_dependency.py`
(+`list_for_projects`, batched, mirroring
`ProjectSkillRequirementRepository.list_for_projects`);
`app/services/import_service.py` (+2 constructor params, +1 fact
converter, extended `_project_lookup_maps`, +`_prepare_project_dependency`,
+`_check_project_dependency_cycle`, +1 `_write_row` branch — always
`.create()`, no update branch, matching `TeamMembership`'s dispatch
shape); `app/services/export_service.py` (+1 constructor param, +1
row-serializer function, +1 `_collect_rows` branch — reuses the
already-existing `list_for_project`/`list_for_organization` verbatim, **no
new repository read method needed for export**);
`app/api/v1/imports.py`/`exports.py` (factory wiring only).

## Frontend changes

`features/import-export/types/importExport.ts`: +1 `ImportEntityType`
union member, +1 `IMPORT_ENTITY_TYPES` picker entry.
`components/ExportPanel.tsx`: `scopeFieldFor` +1 entry, mapping
`project_dependency` to the existing `'project'` filter (both directions
via the direct API's own `list_for_project`/`list_for_organization`
shape). No other component changed. **`PortfolioSnapshot`: zero frontend
changes**, since it was not registered.

## API/schema changes

`docs/openapi.json` regenerated — a 2-line diff: the shared
`ImportEntityType` component gains one enum value
(`"project_dependency"`). Nothing else changed; diff inspected directly.
No schema (`ProjectDependencyCreate`/`Read`) was touched — it already
had everything import needed.

## Database/migration impact

**None.** `ProjectDependency`'s existing `UniqueConstraint(from_project_id,
to_project_id, dependency_type)` already supplied a complete natural key
— no `external_id` or any other column was added. Verified: no new file
under `alembic/versions/`; a fresh SQLite database reaches the same head
(`b8b6cb4c08bf`, unchanged from Phase 36) via `alembic upgrade head`
with zero pending migrations.

## Authorization/security

No new permissions. `Permission.PRIORITIZATION_SCORE` (Manager+, already
in `_WRITE_PERMISSIONS`, the same tier as `IMPORT_USE`/`EXPORT_USE`) —
verified live: a Member gets 403 on import, 200 on export, matching
Phase 36's established pattern exactly. `PortfolioSnapshot` not being
registered means no authorization surface was added or considered for it
at all.

## Multi-tenancy/IDOR behavior

Every lookup remains organization-scoped, including the newly-extended
`_project_lookup_maps` (all three column-name pairs resolve through the
same org-scoped `ProjectRepository` calls) and the new `_check_project_
dependency_cycle`'s existing-edges seed (`list_blocks_edges(organization_id)`).
Verified live: a `to_project_external_id` belonging to another
organization is `invalid_reference`, never a hit; an export from Org A
never includes an edge created directly in the database for Org B.
Backed by 2 dedicated regression tests, mirroring ADR 0016's/ADR 0036's
identical cross-org test shape.

## Tests and new totals

Backend: new file `tests/api/test_project_dependency_import_export.py`,
**21 tests** — create via external ids; existing-edge match reported as
`unchanged` (never `update`); repeated-identical-file determinism;
self-dependency rejection; duplicate-triple-in-file rejection; two
different `dependency_type`s between the same pair both creating
independently (proving the triple, not the pair, is the key); missing/
unresolvable from- and to-project references (each asserted against the
correct `field` name); missing-required-column and invalid-enum
rejection; a cycle against the **existing database graph**; a cycle
introduced **entirely within one file's own batch** (proving the
sequential-simulation mechanism, not just the pre-existing-edges seed);
`related`-type edges correctly exempt from cycle detection; template
round-trip; CSV/JSON export shape and content; export→reimport round-trip
reporting `unchanged`; an export field-set assertion (no field beyond the
documented seven ever appears); Member-403-on-import/200-on-export;
cross-organization reference rejection; cross-organization export
isolation. Full backend suite: **1058 passed** (was 1037). `ruff check .`
clean (one import-ordering issue auto-fixed via `--fix`, verified
unchanged afterward with a full suite re-run). `uv run pyright` (strict)
**0 errors**.

Frontend: extended the existing `ExportPanel.test.tsx` parameterized case
(+1, now covering `project_dependency` alongside Risk/Stakeholder/
`ProjectPriorityScore`). Full suite: **322 passed** (was 321). `oxlint`
clean (2 pre-existing, unrelated warnings). `tsc -b --noEmit` clean.
`vite build` succeeds (pre-existing >500kB bundle warning, out of scope).

No test was added for `PortfolioSnapshot` behavior, per the brief's own
instruction to test only "behaviors actually supported by the audited
lifecycle" — its existing, unmodified test coverage (creation, listing,
comparison) is untouched and was re-verified passing via the full suite
run above.

## Lint/typecheck/build results

Backend: `ruff check .` clean, `uv run pyright` (strict) 0 errors,
`uv run pytest` 1058 passed. Frontend: `npm run lint` (oxlint) clean
(2 pre-existing warnings), `npm run typecheck` clean, `npm run test` 322
passed, `npm run build` succeeds.

## Fresh DB verification

Fresh SQLite → `alembic upgrade head` reaches `b8b6cb4c08bf` (Phase 36's
head, unchanged) — confirmed directly, not assumed, since this phase's
own audit concluded no migration was required.

## Live/API verification

A real `uvicorn` server was started against that freshly-migrated
database, bootstrapped via `scripts/create_first_owner.py`. Exercised
over real HTTP: three projects created; a `project_dependency` JSON
import (A blocks B) applied and exported back out; a **live cross-row
cycle check** — with A→B already in the database, a two-row batch
(B→C, then C→A) correctly created row 1 and rejected row 2 with
`domain_rule_violated`, proving the existing-edges seed and the
batch-order simulation compose correctly together, not merely in
isolation; a Member account confirmed to receive 403 on import and 200
on export; a second organization created and a cross-organization
`to_project_external_id` confirmed unresolvable while Org A's export
stayed at 1 row. Server log scanned for
`password|token|hash|secret|csrf` (beyond expected CSRF field-name
mentions) — no matches. Server stopped and the scratch database removed
afterward.

## Browser verification

Not performed — browser automation is unavailable in this environment
(the same disclosed limitation as every prior phase). Frontend
verification was unit/component-test, lint, typecheck, and build-level
only.

## Deviations

None from the audited, established patterns for `ProjectDependency`. For
`PortfolioSnapshot`, the deviation is the deliberate one the brief itself
anticipated and permitted: leaving it deferred rather than forcing
either half of the pipeline onto it.

## Assumptions

None requiring a blocking question. Both the `ProjectDependency`
registration and the `PortfolioSnapshot` non-registration were resolved
mechanically from executable code, database constraints, and the phase
brief's own explicit constraints (no new generic infrastructure) — never
from product taste.

## Known limitations

Import/export remains role-only for `ProjectDependency`, identical to
every other entity in the pipeline (ADR 0011's deliberate, still-standing
deferral) — a Manager with `IMPORT_USE` can create a dependency edge
between any two projects in the organization via import, not only
projects they hold an explicit `ProjectAccessGrant` on, matching
`ProjectPriorityScore`'s and every other Phase-36-registered entity's
identical existing behavior.

## Residual risks

None newly introduced. `PortfolioSnapshot` was specifically evaluated for
the risk a naive symmetrical registration would have introduced
(fabricable historical data) and was not built.

## Technical debt

None added.

## Explicitly deferred work

`PortfolioSnapshot` import/export — deferred for the reasons stated
above (categorically unsound for import; export blocked by a
shared-enum architecture gap that would require new infrastructure to
close safely). Closing it would need either (a) a per-entity
import-capability flag in the existing registry (a small, genuine
architecture extension, not something this bounded phase was asked to
build) or (b) a deliberate product decision to accept the current
crash-on-import risk in exchange for export-only access, which was not
put to the user since the brief explicitly said not to force symmetry
and no evidence suggested export-only was actually wanted. An org-wide
cross-project Risk/Stakeholder register and instance-level import/export
authorization redesign remain open, exactly as ADR 0036 already recorded
— untouched by this phase.

## Confirmation

Phase 38 was **not** started. Nothing in this phase was committed or
pushed.
