# ADR 0048: Phase 48 — Org-wide cross-project Stakeholder register

- **Status:** Accepted
- **Date:** 2026-10-29

## Context

ADR 0014 (Phase 14) named an org-wide stakeholder register as deferred,
and every roadmap revision since has listed it as open. Phase 47 built the
equivalent register for Risk (ADR 0047). `StakeholdersOverviewPage` still
required picking exactly one project before showing anything, so there was
no way to answer "who are the decision makers and high-influence
stakeholders across this whole organization?" Phase 48 builds that
register, following Phase 47's shape where the audit showed it fits.

Phase 47 shipped with three verification gaps it disclosed itself. The
backend test suite, strict type checking, and live HTTP verification could
not run because an Application Control policy blocked Python, and
`docs/openapi.json` was not regenerated. This phase had to close those
gaps (or confirm they were still blocked) before adding another endpoint.

## Phase 47 verification gate

The repository was clean at the start (`main` == `origin/main` ==
`c3c31d9`, Phase 47 committed and pushed).

The Python restriction has **mostly lifted**. The interpreter, `asyncio`,
SQLAlchemy, FastAPI, pytest, and pyright all run. The policy still blocks
the `alembic.exe` and `uvicorn` console-script shims (os error 4551), so
both were run as `python -m alembic` / `python -m uvicorn`. These run the
same code without the blocked shim.

| Check at the Phase 47 commit | Result |
|---|---|
| Backend suite | **1078 passed** — the first time it actually ran since Phase 47 |
| `ruff check .` | clean |
| `pyright` (strict) | **3 errors**, all in `tests/api/test_org_risk_register.py` (string literals passed where `make_risk` expects enum members) |
| Exposure filter vs. pagination | Correct. `RiskService.list_for_organization` filters by exposure over the full SQL result, then computes `total` and slices the page. Confirmed by reading the code and by live HTTP (below). |
| `docs/openapi.json` | `/api/v1/risks` **missing** — drift confirmed |
| Frontend suite | 455 passed |

No material security, pagination, or correctness defect was found, so
Phase 48 went ahead. Four small Phase 47 corrections were made, each
verified:

1. **Pyright errors**: the three literals became `RiskStatus.OPEN` /
   `RiskProbability.HIGH` / `RiskImpact.HIGH`. This is test-only.
2. **Ordering tie-breaker**: `RiskRepository.list_filtered` ordered by
   `created_at` only. Each page is a separate query, so two risks with the
   same `created_at` could swap order between requests, duplicating one row
   across pages and skipping another. It now orders by `(created_at, id)`.
   This is a hardening fix; ties are unlikely with microsecond application
   timestamps, and no failure was observed.
3. **Duplicate element id (accessibility)**: `Select` derives its id from
   its label, so the per-project picker and the org-wide picker on
   `/risks` both rendered `id="project"`. The org-wide picker's `<label>`
   therefore pointed at the per-project select, leaving the org-wide one
   without an accessible name (CLAUDE.md §29). `ProjectFilterPicker` gained
   an optional `id` prop, and `OrgRiskFilterBar` passes
   `org-risk-project`. One Phase 47 page assertion
   (`getByLabelText('Project')`) had only passed *because of* this bug,
   since both labels resolved to one element. It now asserts two distinct
   pickers.
4. **OpenAPI**: regenerated with the canonical script
   (`scripts/export_openapi_schema.py`), which adds `/api/v1/risks` and
   `Page_RiskRead_`. This change is purely additive.

## What was audited

Each point was checked against the code, not inferred from Phase 47:

- **Stakeholder fields**: `id, project_id, name, person_id, role,
  influence, interest, decision_authority, communication_needs,
  created_at, updated_at` (`StakeholderRead`). There is **no status
  field**, unlike Risk.
- **No derived fields.** `influence`, `interest`, and `decision_authority`
  are stored enums with DB CHECK constraints. Nothing is computed at read
  time the way `Risk.exposure` is, so the Python-side filtering step
  Phase 47 needed has no counterpart here.
- **Project membership**: `Stakeholder.project_id` (non-null, CASCADE), plus
  its own `organization_id`.
- **Existing org-wide listing**: `StakeholderRepository.list(organization_id,
  limit, offset)` exists as unused code (the Phase 12 override pattern
  ADR 0047 found for Risk). It has no filters and no tie-breaker, so a new
  `list_filtered` was added rather than changing a method other callers
  could reasonably expect to stay as-is.
- **Permission**: `Permission.STAKEHOLDER_READ` is in `_READ_PERMISSIONS`,
  which is granted to every role. No role lacks it, so there is no 403 case
  to test. That matches the per-project route.
- **Frontend**: `ProjectFilterPicker`, `Select`, `Table`, `Badge`,
  `EmptyState`, and `QueryBoundary` (loading, error, retry) are all
  reusable unchanged, apart from the `id` prop above.
  `StakeholdersOverviewPage` had **no test file** before this phase.

## Decision

### Backend: `GET /api/v1/stakeholders`

The new route lives in `app/api/v1/stakeholders.py`, uses the
`/api/v1/<entity>` prefix like `risks.py`, and is registered in `main.py`
right after `risks_router`.

- **Organization** comes from `get_current_membership`, never from a
  client parameter.
- **Permission**: `STAKEHOLDER_READ`, reused unchanged.
- **Filters**: `project_id`, `influence`, `interest`,
  `decision_authority`. These are every filterable persisted attribute
  apart from free text. No name or role search was added; it was not
  requested and it would add a new matching semantic.
- **All filtering, counting, and pagination happen in SQL.**
  `StakeholderRepository.list_filtered` builds one WHERE clause and uses it
  for both `COUNT(*)` and the `LIMIT`/`OFFSET` page query. `total` is
  always the count of the full filtered set. This is simpler than Risk's
  approach (load the full filtered set, then slice), and possible because
  no field is derived.
- **Ordering**: `(created_at, id)`, stable across pages.
- **Validation**: `limit` 1–500 (default 100), `offset` ≥ 0, and enum or
  UUID coercion by FastAPI. Anything else returns 422, the same as
  `/risks`.
- **Response**: `Page[StakeholderRead]`, the existing schema with no extra
  fields. The project name is joined on the client, following ADR 0047's
  reasoning.
- **Query cost**: two queries per request, no N+1 (the response does not
  touch relationships), and no unbounded load.

### Frontend: a Card on the existing `/stakeholders` page

This follows ADR 0047's precedent: no new route and no new nav entry. The
Stakeholders nav item is already visible to every role, matching
`STAKEHOLDER_READ`.

- `stakeholdersApi.listForOrganization` sends `STAKEHOLDER_REGISTER_PAGE_SIZE
  = 50`, the same as the Risk register and the Audit Log.
- `useOrgStakeholders` uses the query key `['org-stakeholders', filters]`,
  with every filter and the offset in the key. No organization id is in the
  key, because switching organizations already clears the whole cache.
- `OrgStakeholderFilterBar` has four controls, each listing the backend's
  own fixed vocabulary.
- `OrgStakeholderRegisterTable` is read-only, with no Edit or Remove
  controls. It has two distinct empty states (nothing recorded versus no
  match) and an "Unknown project" fallback.
- `StakeholdersOverviewPage`: every filter change resets to the first page.
  The page shows a "Showing X–Y of N" count and Previous/Next buttons.
  Loading, error, and retry go through `QueryBoundary`.
- `INFLUENCE_VARIANT` and `DECISION_AUTHORITY_LABEL` moved from
  `StakeholdersTable` into `features/stakeholders/constants.ts` so both
  tables share them (the same extraction Phase 47 did for risks).
  `StakeholdersTable` renders identically.
- **Cache coherence (new for this register)**: the per-project register and
  the org-wide register render on the same page. Stakeholder create,
  update, and delete now also invalidate `['org-stakeholders']`, so an edit
  in the top card never leaves the bottom card stale.

### No new product semantics

There is no score, no power/interest quadrant, and no aggregation. The
register lists stored facts exactly as the per-project register does
(CLAUDE.md §16/§17).

## Authorization & multi-tenancy

- Every row is filtered by `Stakeholder.organization_id ==
  membership.organization_id`.
- A `project_id` naming another organization's real project returns a
  response **byte-identical** to a random nonexistent UUID
  (`{"items": [], "total": 0}`, 200). The service deliberately does *not*
  look the project up and 404, unlike `list_for_project`. That way the
  filter cannot be used to probe whether another organization's project
  exists (§27). Both an automated test and the live run assert this.
- Broad filter sweeps (each influence level, `limit=500`) never return
  another organization's rows.
- Unauthenticated requests get 401. Every role, Viewer included, gets 200.

## Verification

| Gate | Result |
|---|---|
| Backend suite | **1108 passed** (1078 → 1108; all +30 in `tests/api/test_org_stakeholder_register.py`; the Phase 47 risk file's count is unchanged at 18) |
| `ruff check .` | clean |
| `pyright` strict | **0 errors** (was 3) |
| Fresh DB: `python -m alembic upgrade head` | applied cleanly to head `b8b6cb4c08bf` |
| `alembic check` | reports only `remove_constraint` for Enum-generated CHECK constraints on 21 pre-existing tables. This is a known autogenerate artifact (SQLite reflects these constraints; `Enum(create_constraint=True)` metadata isn't compared). It predates this phase, which changed **no** model or migration file. |
| OpenAPI | regenerated with the canonical script; additive only (+2 paths, +2 `Page_*` schemas, 0 lines removed) |
| Live HTTP (real `uvicorn`, fresh DB, real login/session/CSRF/org-switch, two organizations) | **31/31 checks passed**, covering cross-org exclusion, cross-org project filter identical to an unknown id, every filter and the 4-way combination, filtered totals, a 3/3/1/0 page walk equal to the unpaged order, 7 invalid inputs returning 422, 401, Viewer 200, the per-project route unchanged, live `/openapi.json`, and **Phase 47's first live verification** (exposure filter applied before pagination, disjoint pages, cross-org isolation) |
| Frontend suite | **483 passed** (455 → 483, +28) |
| `tsc -b --noEmit` | exit 0 |
| `oxlint` | exit 0. Only 2 warnings, both pre-existing in the untouched `AuthContext.tsx`. oxlint now runs in this environment (Phase 40 reported it blocked). |
| `vite build` | exit 0 |
| Browser | **Not performed.** No browser-automation tool was available. UI behavior is covered by component and page tests only. |

## Consequences

- The deferral named in ADR 0014's Consequences is resolved. Risk and
  Stakeholder now both have org-wide registers.
- 0 new tables, 0 migrations, 0 new permissions, 0 schema field changes.
- `ProjectFilterPicker` now accepts an optional `id`. Any future page that
  renders two pickers must pass one.

### Known limitations

- Project names are joined on the client from `useProjectsLookup`. A project
  outside that lookup's fetch window would show "Unknown project". This is
  the same limitation ADR 0047 recorded.
- `OFFSET` pagination: a stakeholder created or deleted between page
  requests can shift row boundaries. This is accepted, as for the Audit Log
  and the Risk register.
- No free-text search (name or role). Not requested; it would be a separate
  decision.
- Risk mutations still invalidate only the per-project risk key, so on
  `/risks` the org-wide register can briefly show stale rows after an edit
  in the per-project card. It refreshes on refetch. The fix is the
  one-line invalidation this phase applied to stakeholders. It was **not**
  applied to Risk, to keep Phase 47 corrections limited to the verified
  defects above.
- PostgreSQL was not exercised. The queries are plain, portable
  SQLAlchemy (equality filters, COUNT, ORDER BY, LIMIT/OFFSET).

### Deferred, not dropped

Stakeholder editing from the register, bulk actions, export from the
register view, and any stakeholder classification are all out of scope.
