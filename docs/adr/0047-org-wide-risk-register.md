# ADR 0047: Phase 47 — Org-wide cross-project Risk register

- **Status:** Accepted
- **Date:** 2026-09-09

## Context

Phase 46's roadmap re-audit found the org-wide cross-project Risk
register (named but never built since Phase 13 — ADR 0013 Consequences)
genuinely build-ready: `Permission.RISK_READ` is already granted to
every role, and `RisksOverviewPage`/`StakeholdersOverviewPage` both
still require picking exactly one project via `ProjectFilterPicker`
before showing anything, with no way to see risk across the whole
organization at once. Phase 47 builds it.

### What was audited before implementing

- Git state: `HEAD` at `b4a5f83` ("Document Phase 46 roadmap re-audit
  and next-build decision"), matching `origin/main` exactly (0 ahead / 0
  behind), working tree clean.
- CLAUDE.md §§4, 5, 17, 21, 26–40; `docs/roadmap.md`; `docs/architecture.md`;
  `docs/domain-concepts.md`; `README.md`; ADRs through 0046, especially
  0013 (Risk management — "no org-wide/cross-project risk register")
  and 0046 (this phase's own recommendation).
- Backend, verified directly: `app/models/risk.py` (no numeric field;
  `exposure` deliberately not a column); `app/domain/risk.py::calculate_risk_exposure`
  (the sole place probability×impact becomes exposure — a 3×3 lookup);
  `app/domain/authorization.py` (`RISK_READ` confirmed inside
  `_READ_PERMISSIONS`, granted to every role); `app/repositories/risk.py`
  (found `RiskRepository.list(organization_id, *, limit, offset)` —
  Phase 12's required override of `BaseRepository.list`'s unscoped
  signature — already implements a complete, correct, organization-wide,
  paginated risk query, but is **dead code**: no route or service method
  anywhere calls it); `app/services/risk.py`/`app/schemas/risk.py`
  (`risk_to_read` is the one place `calculate_risk_exposure` is invoked
  for serialization); `app/api/v1/projects.py` (confirmed `GET
  /{project_id}/risks` is the *only* existing risk-read route).
- Frontend: the complete `features/risks/` tree
  (`api/risksApi.ts`, `hooks/useRisks.ts`, `components/RisksTable.tsx`,
  `views/RisksOverviewPage.tsx`); `features/prioritization/hooks/useRisksForProjects.ts`
  and `utils/riskValueMatrix.ts` (Phase 45's N-parallel-per-project
  composition pattern — evaluated and NOT reused here, see Decision);
  `features/insights/components/ProjectFilterPicker.tsx` (an existing,
  complete, optional "All projects" picker, reused verbatim);
  `hooks/useProjects.ts::useProjectsLookup`; `features/audit/views/AuditLogPage.tsx`
  (the real server-side pagination precedent this phase's UI mirrors).

## Decision

### Architecture: a new, small backend endpoint — not N-per-project client composition

Phase 45's `useRisksForProjects` fires one request per project via
`useQueries`, but that pattern is bounded by "projects currently scored
under one prioritization framework" — typically small. An org-wide
register's scope is "every project in the organization," which grows
without bound over the organization's lifetime and is a **primary,
frequently-used view**, not a one-off chart input. Reusing the N-parallel
pattern here would mean issuing one HTTP request per project just to
render the register once — a materially worse scaling shape than Phase
45's use of it, and exactly the case CLAUDE.md's own performance
discipline and this phase's brief warn against defaulting into. A new
endpoint, `GET /api/v1/risks`, was therefore added:

- It is the **smallest possible** endpoint: no new table, no new
  permission, no schema change. It extends `RiskRepository` with one new
  `list_filtered` method and `RiskService` with one new
  `list_for_organization` method, and reuses `RiskRead`/`risk_to_read`
  verbatim for serialization.
- It was made *safer* to build, not riskier, by the discovery that
  `RiskRepository.list(organization_id, limit, offset)` already existed
  as dead code — an org-wide, paginated risk query was already
  anticipated by Phase 12's own repository-scoping convention. This
  phase's `list_filtered` extends that same shape with `project_id`/
  `status` filters rather than inventing a new query pattern.

### Exposure filtering — computed in Python, never duplicated into SQL

`exposure` is not a persisted column (Risk's own model docstring: "Do not
create risk scores that imply false precision"). Filtering by it in SQL
would require re-expressing `calculate_risk_exposure`'s 3×3 lookup table
as a SQL `CASE` expression — a second, parallel implementation of the
same rule, risking silent drift between the two. Instead,
`RiskRepository.list_filtered` filters only `organization_id`/
`project_id`/`status` in SQL (cheap, indexed columns), and
`RiskService.list_for_organization` computes each row's exposure via
`calculate_risk_exposure` — the exact same function `risk_to_read`
already uses for the single-risk read path — filters by it in Python,
and paginates the already-exposure-filtered list so `total` always
reflects what a client will actually see across pages.

### Filters: project, status, exposure — nothing invented

The three filters named in the brief are exactly the three the frontend
exposes: **Project** (the existing `ProjectFilterPicker`, unchanged, an
optional "All projects" narrowing filter — never a new picker), **Status**
(`RISK_STATUSES`, the existing finite, authoritative vocabulary), and
**Exposure** (`RISK_EXPOSURE_LEVELS`, a new small constant array of the
same three values `RiskExposure` already permits — not a new taxonomy,
just an array form of an existing type for populating a `<Select>`).

### Project display names — a client-side join, not a backend field

`RiskRead` has no `project_name` field, and none was added: the register
resolves `project_id -> name` via the existing, already-org-scoped bulk
`GET /api/v1/projects` (`useProjectsLookup`, unchanged, already used
elsewhere in this app for exactly this purpose) rather than modifying
the shared `RiskRead` schema used by both the org-wide and per-project
routes.

### Pagination — real server-side, mirroring the Audit Log precedent

`RISK_REGISTER_PAGE_SIZE = 50`, offset state in the page component,
Previous/Next controls, "Showing X–Y of Z risks," offset reset on every
filter change — the exact shape `AuditLogPage` already established for
the one other view in this app whose data volume can genuinely grow
without bound (as opposed to the "fetch up to 500 once" convention every
small, effectively-bounded list in this app already uses).

### UI: a new Card on the existing Risks page, not a new route

Per the brief's explicit preference to extend existing routes rather
than build new navigation architecture, the register was added as a
**second Card on the existing `RisksOverviewPage`** (`/risks`, unchanged
route, unchanged nav entry), below the existing per-project register.
Zero new routes, zero new nav entries. It is a new, separate, read-only
table component (`OrgRiskRegisterTable`) rather than a reused/repurposed
`RisksTable` — `RisksTable` carries inline status-change and remove
controls appropriate for the per-project management surface, which this
register deliberately does not have (brief: "no editing controls, no
bulk actions"). `EXPOSURE_VARIANT`/`STATUS_LABEL` were extracted from
`RisksTable.tsx` into a new shared `features/risks/constants.ts` so the
two tables' badges can never disagree about what a colour/label means —
a small, behavior-preserving refactor of existing code, not a new
concept.

### No new product semantics

No risk scoring, no aggregation, no new severity scale, no
recommendations, no editing, no export. This is a register — every field
displayed is copied verbatim from the existing, unchanged `RiskRead`
response.

## Authorization & multi-tenancy

- **No new permission.** `Permission.RISK_READ` (already granted to
  every role) gates the new route exactly like the existing per-project
  one.
- **Organization identity comes from the session, never the client.**
  `get_current_membership` resolves `membership.organization_id`
  server-side; the frontend passes no organization id anywhere.
- **A `project_id` filter naming a project in another organization
  cannot leak anything.** The SQL always additionally requires
  `Risk.organization_id == membership.organization_id`; a Risk row's
  `project_id` can only ever belong to a project in that same
  organization (Phase 12's own invariant), so a foreign `project_id`
  filter simply matches zero rows — verified directly by
  `test_organization_risks_project_filter_from_another_organization_returns_empty`.
  It returns `200` with an empty list, never a `403`/`404` that would
  confirm the foreign project's existence.
- **A sweeping status/exposure filter (no project filter at all) still
  cannot surface another organization's risk** — verified by
  `test_organization_risks_status_and_exposure_filters_cannot_bypass_org_scoping`.
- Read-only: the endpoint issues no mutation, so there is no CSRF or
  write-permission surface to consider.

## Consequences

- **Backend:** 1 new file (`app/api/v1/risks.py`), 2 files edited
  (`app/repositories/risk.py` — 1 new method; `app/services/risk.py` —
  1 new method), 1 file edited to register the router (`app/main.py`).
  **0 new tables, 0 migrations, 0 new permissions, 0 schema changes.**
- **Frontend:** 6 new files (`hooks/useOrgRisks.ts`, `constants.ts`,
  `components/OrgRiskFilterBar.tsx` + test,
  `components/OrgRiskRegisterTable.tsx` + test), 3 files edited
  (`api/risksApi.ts`, `components/RisksTable.tsx` — constants
  extraction only, `views/RisksOverviewPage.tsx`), 1 new page-level test
  file (`views/RisksOverviewPage.test.tsx`).
- **Tests, lint, typecheck, build:** see the Phase 47 Final Report for
  exact totals.
- **API/OpenAPI:** the contract changed (one new route) — see the Final
  Report for whether `docs/openapi.json` was regenerated in this
  environment.
- **Backend test/type-check verification:** `pytest` and `pyright`
  remain blocked in this sandbox by a pre-existing Application Control
  policy (confirmed this phase to also block core CPython native
  extensions — `import asyncio` itself fails via `_overlapped.pyd`,
  unrelated to any code in this repository); `ruff check .` (whole
  backend) and `python -m py_compile` on every changed file both passed
  cleanly, the maximum verification available in this environment. See
  the Final Report for the full disclosure.
- **Browser verification:** not performed — no browser-automation tool
  is available in this environment.

### Known limitations

- Exposure filtering computes every project/status-matching row's
  exposure in Python before paginating, rather than filtering in SQL —
  for an organization with an unusually large total risk count, this is
  less efficient than a SQL-native filter would be. Given a risk
  register's realistic scale (this codebase's own Risk entity is a
  deliberately lightweight per-project register, not a
  capacity-engine-scale table), this was judged the correct trade-off
  against duplicating the exposure lookup table into SQL (see Decision).
- The register's Project filter (`ProjectFilterPicker`) lists every
  project in the organization regardless of whether it has any risks
  recorded — matching that component's existing, unchanged behavior
  everywhere else it's used in this app.
- No bulk actions, export, or edit affordance on the register — by
  design (brief's explicit scope boundary), not an oversight.

### Deferred, not dropped

Org-wide Stakeholder register (the natural structural follow-up, not
started this phase, per the brief's explicit scope boundary), Scenario
Snapshots (still blocked on the FK-lifecycle product decision — ADR
0046), and every other item this phase's brief listed out of scope.

## Confirmation

Phase 48 was **not** started. See the Phase 47 Final Report for the
exact commit/push status.
