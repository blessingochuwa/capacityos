# ADR 0036: Phase 36 — Import/export registration for Risk, Stakeholder, and Prioritization

- **Status:** Accepted
- **Date:** 2026-08-29

## Context

ADR 0013 and ADR 0014 explicitly deferred registering Risk and
Stakeholder into the Phase 6 import/export pipeline, both stating the
same reason: *"Every phase since Phase 7 that introduced a new
source-data entity registered it into the Phase 6 import/export
pipeline... Recorded as recommended future work, not implemented."*
Every phase from 17 onward (Prioritization) repeated the same
deferral, and `docs/roadmap.md` has carried "Risk, Stakeholder,
Prioritization & Project Dependency Import/Export registration" as an
open, named gap since Phase 22, with one specific blocking sub-question
flagged: *"neither entity has a Person/Project-style natural identity
key for CSV upsert-matching, which would need its own decision before
implementation."*

Per the phase brief's audit-first instruction, the complete existing
import/export architecture, the Risk/Stakeholder/Prioritization domain
implementations, and every relevant ADR were read before any code was
written (see "What was audited" in the final report). This ADR records
what that audit found and the resulting registration decisions.

## Existing import/export architecture (as found)

**A single, central registry — not per-route configuration.** Adding an
entity means: (1) a new `ImportEntityType` enum member
(`app/domain/import_export_parsing.py`), (2) an `ENTITY_COLUMNS` entry
(the same list drives import header validation, export column order,
and template generation), (3) a `_TEMPLATE_EXAMPLES` entry, (4) a
`normalize_<entity>_row` function (`app/domain/import_export_diff.py`)
doing Level 2/3 validation and diffing, (5) dispatch wiring in
`ImportService`/`ExportService`. **No new route is ever needed** —
`GET /api/v1/imports/{entity_type}/template`,
`POST /api/v1/imports/{entity_type}/validate`,
`POST /api/v1/imports/{entity_type}/apply`, and
`GET /api/v1/exports/{entity_type}` all take `entity_type` as a path
parameter typed directly against the enum, so a new member is
automatically a valid, working path value the moment it's added.

**Authorization is uniform and enum-independent.** Every import route is
gated by `Permission.IMPORT_USE`; every export route by
`Permission.EXPORT_USE`. Both are in `_WRITE_PERMISSIONS`/granted from
Manager upward (Member+ for `EXPORT_USE`) in
`app/domain/authorization.py`'s `ROLE_PERMISSIONS` — identical to
`RISK_WRITE`, `STAKEHOLDER_WRITE`, and `PRIORITIZATION_SCORE`. Nothing
project-instance-scoped (`require_project_access`/`ProjectAccessGrant`)
gates import/export — ADR 0011 names "imports/exports" explicitly as
**"Explicitly NOT scoped in this phase (role-only)... a deliberate,
documented deferral, not an oversight."** Registering a project-scoped
entity into this pipeline therefore means it becomes reachable by
*any* Manager+ with `IMPORT_USE`, not only Managers holding an explicit
grant on that specific project — the exact same characteristic
`ProjectSkillRequirement` (Phase 7) already has today. This is a
pre-existing, deliberate architectural property, not something this
phase introduces or could "fix" without an out-of-scope authorization
redesign.

**Identity/upsert-matching follows one of three established shapes**,
chosen per-entity from what already exists — never invented fresh:
1. An existing real unique column (Person's `email`, Team's `name`).
2. A resolved-reference composite pair, when both halves of the pair
   are always present (`TeamMembership`'s `(person_id, team_id)`,
   `PersonSkill`'s `(person_id, skill_id)`,
   `ProjectSkillRequirement`'s `(project_id, skill_id)`).
3. A new nullable, unique `external_id` column (Project, Allocation,
   WorkingSchedule, AvailabilityException — Phase 6), for an entity with
   no natural key at all. A row without one always creates; re-importing
   the same file without external ids produces duplicates by design,
   documented per-field, matching `test_project_import_without_external_
   id_always_creates_on_reimport`'s established precedent.

**Reference resolution is literal-id-or-natural-key → `INVALID_REFERENCE`,
resolved via a batch-loaded `ReferenceLookup`, never a per-row query and
never a soft skip** (`resolve_person_reference`, `resolve_project_
reference`, `resolve_team_reference`, `resolve_skill_reference`). Every
lookup map is built **organization-scoped** — `_person_lookup_maps`/
`_project_lookup_maps`/etc. all thread `organization_id` into the
repository call, so a reference to another organization's row is
unresolvable, not silently cross-tenant.

## Candidate audit — what was missing per domain

### Risk

`app/models/risk.py`: `organization_id`, `project_id` (required FK, one
Risk belongs to exactly one Project), `description` (required),
`cause`/`potential_effect`/`response` (optional text),
`probability`/`impact`/`status` (enums with defaults), `owner_person_id`
(optional FK to Person, nullable/SET NULL). **No natural key of any
kind** — `description` is free text, not unique. Route:
`POST/PATCH/DELETE /projects/{project_id}/risks[/{risk_id}]`, gated by
`require_project_access(Permission.RISK_WRITE/_DELETE)` on its own
direct route (Phase 13, post-dates ADR 0011) — the import path bypasses
this exactly like `ProjectSkillRequirement`'s own import path already
does, per the "role-only, deliberate deferral" finding above.

### Stakeholder

`app/models/stakeholder.py`: `organization_id`, `project_id` (required),
`name` (required, always the stakeholder's own recorded identity),
`person_id` (**optional** FK to Person, nullable/SET NULL — "many real
stakeholders... are never a Person row at all"), `role` (required),
`influence`/`interest`/`decision_authority` (enums with defaults),
`communication_needs` (optional text). **A genuine, if partial, natural
key**: `UniqueConstraint("project_id", "person_id")` — this constraint
exists on the table today, was simply never used for import matching.
It only covers the subset of rows where `person_id` is set (SQL UNIQUE
permits unlimited NULLs); a person-less stakeholder has no natural key
at all, same shape as Risk. Route:
`POST/PATCH/DELETE /projects/{project_id}/stakeholders[/{stakeholder_id}]`,
`require_project_access(Permission.STAKEHOLDER_WRITE/_DELETE)` — same
pattern as Risk.

### Prioritization

Not a single table. Audited every prioritization-related model:
`PrioritizationFramework`/`PrioritizationCriterion` (the framework
*definition* — gated by `Permission.PRIORITIZATION_MANAGE`, **Admin/Owner
only**, deliberately **not** in `_WRITE_PERMISSIONS`, per ADR 0017:
*"a framework change reshuffles every project's rank across the whole
organization at once... closer in blast radius to
MEMBERSHIP_MANAGE/ORGANIZATION_MANAGE"*); `ProjectPriorityScore`
(one project's recorded inputs against one framework — **holds no
`score`/`rank` column at all**, per its own docstring: *"the computed
score is always derived at read time... exactly like Risk.exposure"*);
`ProjectPriorityCriterionValue` (*"the only fact this phase actually
persists for scoring purposes"* — the real, human-entered source data);
`ProjectDependency` and `PortfolioSnapshot` (named in the same roadmap
sentence as a "Prioritization" import/export candidate, but **out of
this phase's named three-domain scope** — see Strict exclusions below).

`ProjectPriorityScore` has a genuine composite natural key —
`UniqueConstraint("project_id", "framework_id")` — the exact same shape
as `ProjectSkillRequirement`'s `(project_id, skill_id)`. Its write path
(`POST/PATCH /projects/{project_id}/priority-scores`) is gated by
`require_project_access(Permission.PRIORITIZATION_SCORE)` — **in**
`_WRITE_PERMISSIONS`, the same tier as `RISK_WRITE`/`STAKEHOLDER_WRITE`/
`IMPORT_USE`. `PrioritizationFramework` is **not** — gated by
`PRIORITIZATION_MANAGE`, a materially higher tier no other registered
import/export entity has ever crossed.

## Decision

### Three entities registered: `risk`, `stakeholder`, `project_priority_score`

**Risk gets a new nullable `external_id` column** (Phase 6's
established Option 3 — mechanical application of existing precedent, not
a fresh product decision): `organization_id, external_id` unique
constraint, plain index, matching Project/Allocation's exact shape.
Migration `b8b6cb4c08bf`. Also exposed on the normal
`RiskCreate`/`RiskUpdate`/`RiskRead` API (not import-exclusive), matching
Project's own precedent, with the same create/update conflict-check
(`ConflictError`) `ProjectService`/`AllocationService` already perform.

**Stakeholder needed no schema change.** Matched by the resolved
`(project_id, person_id)` pair (Option 2) when a person reference is
supplied; a row with none has no natural key and always creates (Option
3's *behavior*, without needing Option 3's *column* — the already-real
`UniqueConstraint` supplies the key for the covered case). A subtlety
caught and fixed before it shipped: a person-less Stakeholder row must
get `identity=None` (not a compound string embedding "person_id=None"),
or two different person-less stakeholders on the same project would be
wrongly flagged `duplicate_in_file` — this mirrors, byte for byte, how
Project/Allocation already represent "no natural key" as `identity=None`
rather than a colliding placeholder string.

**Prioritization registers `ProjectPriorityScore`
(`project_priority_score`), not `PrioritizationFramework`.** This is the
one place the audit found a genuine authorization boundary that
registration must not cross: `PrioritizationFramework` is `PRIORITIZATION_
MANAGE`-gated (Admin/Owner) specifically *because* a framework edit
reshuffles the whole portfolio's ranking; registering it into the
`IMPORT_USE`-gated (Manager+) pipeline would let any Manager mutate
frameworks without holding `PRIORITIZATION_MANAGE` — an actual privilege
escalation, not the pre-existing "role-only, not instance-scoped"
characteristic every other registered entity already accepts.
`ProjectPriorityScore`/`ProjectPriorityCriterionValue`, by contrast, are
gated by `PRIORITIZATION_SCORE` — the same tier as `IMPORT_USE` itself —
so registering them introduces no escalation, exactly like
`ProjectSkillRequirement`. This also happens to be the correct semantic
target regardless: `ProjectPriorityScore`/`Value` is the actual
"source data" a spreadsheet-onboarding organization would bulk-load
(a project's RICE/ICE/WSJF/Weighted inputs, or its MoSCoW category);
the score itself is derived, never stored, so there is nothing to
import for it, matching Risk.exposure's own precedent of never
appearing in `ENTITY_COLUMNS`.

### Field contracts

- **`risk`**: `id, external_id, project_id, project_external_id,
  description*, cause, potential_effect, probability, impact, response,
  owner_person_id, owner_person_email, status, review_date, created_at,
  updated_at` (`*` = required header). `owner_person_id`/
  `owner_person_email` is a new, generalized **optional** person
  reference (`resolve_optional_person_reference`) — the existing
  `resolve_person_reference` is hardcoded to required semantics and to
  the column names `person_id`/`person_email`; Risk's owner is both
  optional and differently named, so a parameterized sibling function
  was added (used by Stakeholder's `person_id`/`person_email` too),
  never a second resolution mechanism.
- **`stakeholder`**: `id, project_id, project_external_id, name*,
  person_id, person_email, role*, influence, interest,
  decision_authority, communication_needs, created_at, updated_at`.
- **`project_priority_score`**: `id, project_id, project_external_id,
  framework_id, framework_name, category, values, notes, created_at,
  updated_at`. `values` is a packed cell —
  `"criterion_key:value,criterion_key:value,..."` for CSV, a native
  array of `{criterion_key, value}` objects for JSON — the exact
  convention `WorkingSchedule.entries` already established for "one row,
  packed child rows" (`coerce_criterion_values_cell` mirrors
  `coerce_entries_cell` line for line). `category` is MoSCoW-only;
  submitting it against a non-MOSCOW framework is rejected with the
  service's own message, reused verbatim rather than re-derived
  (`validate_category_for_framework_type`'s one-line rule, inlined —
  not called directly, since it raises and normalize functions
  communicate via `ImportFieldError`, matching PersonSkill's identical
  "is_active" inline-check precedent). An unknown `criterion_key` is
  rejected against the resolved framework's *actual* criteria
  (`PrioritizationFrameworkFact.criterion_keys`), never a
  re-implemented copy of `_apply_values`'s rule.

### Relationship/reference handling

Every reference resolves via literal id or natural key against an
organization-scoped, batch-loaded lookup — no new mechanism. `framework_
id`/`framework_name` reuses the existing `PrioritizationFramework.name`
(unique per organization) exactly like Skill/Team's own name-based
resolution; `resolve_framework_reference` is a new function, but it is
the same shape as `resolve_skill_reference`/`resolve_team_reference`,
not a new kind of thing.

### Multi-tenancy / IDOR

Unchanged mechanism, extended to three more entities: every new lookup
map (`_person_lookup_maps`'s owner-column extension, the new
`_framework_lookup_maps`) threads `organization_id` into its repository
call, so a reference to another organization's row is unresolvable —
verified live (a cross-organization `project_external_id` resolves to
`INVALID_REFERENCE`, never a hit) and by test
(`test_risk_import_cross_organization_project_reference_is_unresolvable`,
`test_risk_export_never_returns_another_organizations_rows`). Export
inherits the existing `_check_cap`/organization-scoped repository
pattern unchanged.

### Compatibility

Zero changes to any existing entity's columns, identifiers,
authorization, error codes, or response shape. `ImportEntityType`,
`ENTITY_COLUMNS`, `ReferenceLookup`, and the `ImportService`/
`ExportService` dispatch chains are all **additive** — every existing
branch (`if entity_type == ...`) is untouched; the previously-implicit
final `else` (which was `PROJECT_SKILL_REQUIREMENT`, the prior last
enum member) was made an explicit `elif` so it isn't accidentally
absorbed by the new branches. `ReferenceLookup` gained two required
fields (`frameworks_by_id`/`frameworks_by_name`); every existing call
site (production and test) was updated to pass `{}`/`{}` where
frameworks aren't needed — a mechanical, behavior-preserving change,
confirmed by the full pre-existing suite passing unchanged.

## Backend changes

`app/models/risk.py` (+`external_id` column/constraint),
`app/schemas/risk.py` (+`external_id` field, three schemas),
`app/services/risk.py` (+external_id conflict guard, mirroring
Project/Allocation), `app/repositories/risk.py` (+`get_by_external_id`,
`list_by_external_ids`), `app/repositories/stakeholder.py`
(+`list_for_projects`), `app/repositories/project_priority_score.py`
(+`list_filtered`, `list_for_projects`),
`app/repositories/prioritization_framework.py` (+`list_by_ids`,
`list_by_names`), `app/domain/import_export_parsing.py` (+3
`ImportEntityType` members, `ENTITY_COLUMNS`/`_TEMPLATE_EXAMPLES`
entries, `coerce_criterion_values_cell`), `app/domain/import_export_
diff.py` (+4 Fact dataclasses, +3 Payload wrappers, +`resolve_optional_
person_reference`, +`resolve_framework_reference`, +`_values_key`, +3
`normalize_*_row` functions), `app/services/import_service.py` (+3
repository/service constructor params, +4 fact converters, +`_framework_
lookup_maps`, +3 `_prepare_*` methods, +3 `_write_row` branches),
`app/services/export_service.py` (+4 repository constructor params, +3
row-serializer functions, +3 `_collect_rows` branches, +`_frameworks_
by_id`), `app/api/v1/imports.py`/`exports.py` (factory wiring only).

## Frontend changes

`apps/web/src/features/import-export/types/importExport.ts`: +3
`ImportEntityType` union members, +3 `IMPORT_ENTITY_TYPES` picker
entries (the frontend's own registry the existing `EntityTypePicker`
already consumes — required by the phase brief's own "only touch the
frontend if it consumes a registry it can't work without" rule).
`components/ExportPanel.tsx`: `scopeFieldFor` (which already documents
itself as *"mirrors `ExportService._collect_rows` exactly"*) extended so
`risk`/`stakeholder`/`project_priority_score` show the existing Project
filter — no new UI primitive, no redesign. `ImportExportPage.tsx` and
every other component needed **zero** changes — both are entirely
generic over `ImportEntityType`.

## API/schema changes

`docs/openapi.json` regenerated — a 40-line diff: the shared
`ImportEntityType` component gains 3 enum values (automatically applied
everywhere it's referenced — no per-route diff, confirming the
"one central registry" finding), and `RiskCreate`/`RiskUpdate`/`RiskRead`
each gain the new `external_id` field. Nothing else changed; diff
inspected directly.

## Database/migration impact

One migration, `b8b6cb4c08bf` (`risks.external_id` + its index + its
`(organization_id, external_id)` unique constraint, via `batch_alter_
table` — SQLite cannot add a named UNIQUE constraint outside batch mode,
mirroring the Phase 12 migration's identical technique for `Project`).
No other schema change — Stakeholder and ProjectPriorityScore needed
none. Verified: fresh SQLite → `alembic upgrade head` reaches this
migration; `downgrade -1` then `upgrade head` again both succeed
cleanly (batch-mode round-trip confirmed, not merely upgrade-only).

## Tests and totals

- **Backend**: new file
  `tests/api/test_risk_stakeholder_prioritization_import_export.py`, 30
  tests (create/update/reimport-unchanged/no-natural-key-always-creates
  for all three entities; owner/person email resolution and its
  unresolvable-reference case; unknown-criterion-key and
  wrong-framework-type-category rejections for scoring; template
  round-trips; Member-403/Member-can-export authorization; cross-
  organization reference-resolution and export-scoping IDOR checks;
  a no-sensitive-fields export-shape assertion). Plus 2 pre-existing
  fixes required for compile correctness (not new behavior):
  `tests/domain/test_import_export_diff.py`'s 8 `ReferenceLookup(...)`
  literals updated for the two new required fields;
  `tests/factories.py::make_risk` gained an `external_id` parameter.
  Full suite: **1037 passed** (was 1007). `ruff check .` clean.
  `uv run pyright` (strict) **0 errors**.
- **Frontend**: new `ExportPanel.test.tsx` (3 parameterized cases —
  Risk/Stakeholder/ProjectPriorityScore each show the Project filter,
  not Person/Team). Full suite: **321 passed** (was 318). `oxlint`
  clean (2 pre-existing warnings, unrelated file). `tsc -b --noEmit`
  clean. `vite build` succeeds (pre-existing >500kB bundle warning, out
  of scope).

## Fresh DB / live verification

Fresh SQLite → `alembic upgrade head` reached `b8b6cb4c08bf`; a real
`uvicorn` server was started against it, bootstrapped via `scripts/
create_first_owner.py`. Exercised over real HTTP: Risk CSV import
(create) and JSON export; Stakeholder JSON import with no person
reference; a RICE framework created through the real prioritization
route; `project_priority_score` JSON import of RICE criterion values,
CSV export, and — critically — a live call to the real, unchanged
`GET /prioritization/portfolio` route confirming the imported values
feed the **existing, unmodified** scoring engine
((8000 × 2 × 80) / 5 = 256000, matching RICE's formula exactly, never a
second calculation); a Member account added and confirmed to receive
403 on import while still able to export; a second organization created
and a cross-organization `project_external_id` confirmed unresolvable
(`invalid_reference`, never a leak) while Org A's risk export stayed at
1 row. Server log scanned for `password|token|hash|secret|csrf` (beyond
expected CSRF field-name mentions) — no matches. Server stopped and the
scratch database removed afterward.

## Browser verification

Not performed — browser automation is unavailable in this environment
(the same disclosed limitation as every prior phase). Frontend
verification was unit/component-test, typecheck, and build-level only.

## Deviations

None from the audited, established patterns.

## Assumptions

`ProjectPriorityScore`/`ProjectPriorityCriterionValue` (not
`PrioritizationFramework`) is the correct interpretation of
"Prioritization" for this phase's named three-domain scope — justified
above by both the authorization-tier finding (no escalation) and the
"source data vs. derived/configuration" distinction every other
registered/excluded entity already follows.

## Known limitations

Import/export remains role-only for all three new entities, exactly
like every entity already in the pipeline (ADR 0011's deliberate,
documented deferral) — a Manager with `IMPORT_USE` can write a Risk/
Stakeholder/score on any project in the organization via import, not
only projects they hold an explicit `ProjectAccessGrant` on, identical
to `ProjectSkillRequirement`'s existing behavior. Re-opening this
requires a new, explicit product requirement about import/export's
authorization model as a whole, not a per-entity decision.

## Residual risks

None newly introduced. The one property that could plausibly have
introduced a real risk — `PrioritizationFramework`'s escalation — was
identified and explicitly excluded rather than shipped.

## Technical debt

None added. A pre-existing, latent characteristic of the whole Phase 6
system was *discovered*, not created, while writing this phase's own
tests: `_unchanged`/`_entries_key`-style comparisons treat a `Numeric`
column's DB-rounded trailing zeros as a real change on a re-import that
doesn't match that exact precision (e.g. submitting `"8000"` against a
`Numeric(12, 3)` column previously stored as `"8000.000"`). This is
already `_entries_key`'s own documented, deliberate behavior
("`trailing-zero formatting differences... are treated as a real
change`") — not a bug — but no existing test happened to exercise it
against a `Numeric` field before this phase's `values` cell did. Left
untouched, per the brief's "do not fix unrelated technical debt"
instruction; the new tests were written to respect this existing
convention rather than work around it.

## Explicitly deferred work

`ProjectDependency` and `PortfolioSnapshot` import/export registration
— named in the same roadmap sentence as a candidate, but outside this
phase's explicit three-domain scope (`Risk, Stakeholder & Prioritization`)
and each carrying its own open question (`PortfolioSnapshot` is
immutable/append-only, like `AuditEvent` — never a natural import
target; `ProjectDependency`'s own natural key and cycle-detection
interaction with import was not audited here). An org-wide cross-project
Risk/Stakeholder register (ADR 0013/0014's own separately-named
deferral, unrelated to import/export). Instance-level (`ProjectAccessGrant`)
scoping for the whole import/export system — ADR 0011's deliberate,
still-standing deferral, not something this phase was asked to revisit.

## Confirmation

Phase 37 was **not** started. Nothing in this phase was committed or
pushed.
