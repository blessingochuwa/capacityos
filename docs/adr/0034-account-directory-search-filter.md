# ADR 0034: Phase 34 — Account directory search & filtering

- **Status:** Accepted
- **Date:** 2026-08-29

## Context

Phase 29 (ADR 0029) shipped the `/admin/users` account-directory UI and
named its own known limitation directly: "the account list is the full
global directory with no server-side filter... there is no search/filter
box in this slice." Every roadmap audit since (Phases 30–33) re-confirmed
this as a real, named, unscheduled gap — distinct from, and explicitly not
entangled with, the separate unresolved product decision on whether
`USER_WRITE` should become organization-scoped (ADR 0029's "Multi-tenancy"
section, reconfirmed still open by every subsequent phase's audit).

Per the phase brief's audit-first instruction, the following were read
before any code was written: CLAUDE.md §§4, 21, 26–29, 31–39;
`docs/roadmap.md`; `docs/architecture.md`; `docs/domain-concepts.md`;
`README.md`; ADR 0010 (auth/RBAC/audit), ADR 0012 (organizations/
multi-tenancy, Decision 8 — the account directory is deliberately
cross-organization), ADR 0015 (last-owner invariant), ADR 0028
(membership UI), ADR 0029 (user account UI, the direct predecessor); the
full `apps/api/app/api/v1/users.py`, `app/services/user.py`,
`app/repositories/user.py`, `app/schemas/user.py`, `app/api/deps.py`, and
every other repository's `list_filtered` method (`skill.py`, `scenario.py`,
`availability_exception.py`, `audit_event.py`, `allocation.py`) for the
existing filter-shape convention; the full `apps/web/src/features/users/`
tree and every `apps/web/src/components/ui/*` primitive; and the existing
test suites (`tests/api/test_users.py`, `tests/services/test_user.py`,
`tests/api/test_rbac.py`, `tests/domain/test_authorization.py`,
`tests/api/test_cross_organization_boundaries.py`,
`UsersPage.test.tsx`, `UsersTable.test.tsx`, `CreateUserForm.test.tsx`).

## Audit findings — the executable contract

| # | Question | Finding |
|---|---|---|
| 1 | Who can reach `GET /api/v1/users` today? | `Permission.USER_READ` (Admin/Owner only — `ROLE_PERMISSIONS` gives `USER_READ`/`USER_WRITE` identical grant sets), via `require_permission`, which transitively requires an active-organization context (`get_current_membership`) even though the directory itself isn't org-filtered. Manager/Member/Viewer → 403 (`test_rbac.py::test_manager_can_create_a_person_but_cannot_manage_users`). |
| 2 | Global or organization-scoped? | **Global, deliberately** — ADR 0012 Decision 8, reconfirmed unchanged by ADR 0029: "an admin's 'add an existing user to my organization' flow needs to find any account by email, not just accounts already in the acting organization." Phase 34 must preserve this exactly. |
| 3 | Fields exposed today | `UserRead`: `id, email, display_name, status, person_id, last_login_at, created_at, updated_at`. `password_hash` is never selected into this schema or any other (`UserRead`'s own docstring, verified — `user_to_read` calls `UserRead.model_validate(user)` against the Pydantic schema, which has no `password_hash` field to leak). |
| 4 | Existing filter conventions elsewhere | Every other `list_filtered` in this codebase (`skill.py`'s `is_active`, `scenario.py`'s `status`, `availability_exception.py`'s `person_id`, `allocation.py`'s `person_id`/`project_id`, `audit_event.py`'s `actor_user_id`/`action`/`resource_type`/`start`/`end`) is an **exact-match** filter over an already-indexed/enum column, built with `stmt.where(...)` conditionally applied, `select(func.count()).select_from(stmt.subquery())` for the total, then `.order_by(...).limit(...).offset(...)`. **No free-text/substring search (`ilike`) exists anywhere in this codebase yet** — Phase 34 is the first. |
| 5 | Pagination shape | `Page[UserRead]` (`items`, `total`); backend `limit`/`offset` (`ge=1,le=500` / `ge=0`), matching every other list route. **The frontend has no pagination UI anywhere in this application** — every list feature (`Person`, `Team`, `Project`, `Skill`, `Scenario`, `Member`, `User`, access-grant picker) fetches up to a fixed `LIST_ALL_LIMIT = 500` in one request and never sends a second page. This is the established, app-wide convention, not something specific to Users. |
| 6 | URL query-param / debounce conventions | **Neither exists anywhere in the frontend.** No `useSearchParams` usage, no shared debounce hook/utility, no dedicated `Input`/`Pagination` UI primitive — every existing form (`CreateUserForm`, `AddMemberForm`, `RenameOrganizationForm`) uses a raw `<input>` with a locally-defined Tailwind class string. |
| 7 | Does implementing search require an unresolved authorization decision? | **No.** Search/filter are additive query parameters on an already-authorized, already-global route; nothing about them touches who can reach the route, what organization it's scoped to, or the separate, still-open `USER_WRITE` org-scoping question (left untouched — see "Strict exclusions" below). |

No unresolved product or authorization decision blocks this phase. No
blocking question was needed.

## Decision

### Scope: server-side `q` (substring) + `status` (exact) filters on the existing `GET /api/v1/users`, zero new endpoints

- **`q`** — case-insensitive substring match against `email` **OR**
  `display_name` only, via SQLAlchemy's portable `.ilike()` (native
  `ILIKE` on PostgreSQL, `lower() LIKE lower()` on SQLite — the existing
  database abstraction, not a database-specific workaround). These are
  the only two identity fields the directory already shows in its
  "Account" column (`UsersTable`); `person_id` is a link/UUID, not a
  natural text-search target, and was deliberately not added as a third
  search field — no product requirement names it and CLAUDE.md §17
  forbids inventing scope.
- **`status`** — exact match against the existing `UserStatus` enum
  (active/invited/disabled), the same shape as `Skill.is_active`/
  `Scenario.status` elsewhere in this codebase.
- **No other filter** was added. `last_login_at`/`created_at`/`person_id`
  range or presence filters were considered and rejected — none is named
  by ADR 0029, the roadmap, or any UI element already on the page,
  and adding them would be exactly the unrequested-scope expansion
  CLAUDE.md §32/§14's "do not invent arbitrary filters" instruction (this
  phase brief §4) warns against.
- **Never queryable or returned:** `password_hash`, or any other
  credential — unchanged, since `q`/`status` only add `WHERE` clauses
  against `User.email`/`User.display_name`/`User.status`; `UserRead`'s
  schema (what can ever be serialized back) is untouched.

### Backend: one repository method extended, one service passthrough, two new optional query params

`UserRepository.list_filtered(*, q=None, status=None, limit=100, offset=0)`
builds `select(User)`, conditionally adds
`.where(or_(User.email.ilike(f"%{q.strip()}%"), User.display_name.ilike(...)))`
when `q` is non-empty after stripping, and `.where(User.status == status)`
when `status` is given — filtering happens entirely in the SQL layer,
never by fetching the full table into Python. `UserService.list` passes
both through unchanged. `GET /api/v1/users` gains
`q: str | None = Query(default=None, max_length=200)` and
`status_filter: UserStatus | None = Query(default=None, alias="status")`
(the `status_filter`/alias split mirrors `scenarios.py`'s `status_filter`
exactly — avoiding a name collision with this router's own
`from fastapi import status` import). `limit`/`offset`/pagination
semantics, `Permission.USER_READ` gating, and the "global, not
organization-scoped" behavior are byte-for-byte unchanged.

### Frontend: filter controls on the existing `/admin/users` page, no new route

`UsersFilterBar` (new, `features/users/components/`) — a search `<input
type="search">` (styled with the same locally-defined Tailwind class
string `CreateUserForm` already uses — no new shared `Input` primitive)
and a `Select` (the existing `components/ui/Select`) for status, offering
the same Active/Invited/Disabled options `STATUS_BADGE` already defines.
`UsersPage`'s `UsersManager` holds the raw search text in local state,
debounces it 300ms before it becomes the value actually sent to
`useUserAccounts` (a small local `useEffect`/`setTimeout` — no new shared
debounce utility invented, since none exists to extend), and passes
`status` straight through (a `<select>` change needs no debouncing).
`usersApi.list` and `useUserAccounts` both gained an optional
`{ q?, status? }` filters parameter, included in the React Query key
(`['user-accounts', filters]`) so a filter change is a distinct cached
query — never a client-side re-filter of an already-fetched page.
Existing mutations still `invalidateQueries({ queryKey: ['user-accounts'] })`,
which (TanStack Query's default prefix matching) still invalidates every
filtered variant.

**A correctness interaction found and fixed, not part of the requested
scope but required to preserve existing behavior**: the create-account
form's "eligible People" picker (`CreateUserForm`'s `eligiblePeople`) was
computed from the same `usersQuery` the table renders — filtering that
query would have silently narrowed which already-linked `person_id`s the
picker excludes, letting an admin pick a Person who already has an
account whenever a search/status filter happened to hide that account.
Fixed by adding a second, always-unfiltered `useUserAccounts()` call
(`allUsersQuery`) used only to compute `linkedPersonIds`; the visible
table continues to use the filtered query. This is the smallest change
that keeps the picker's existing correctness guarantee intact under the
new filtering feature — CLAUDE.md §16's "maintain existing user-management
actions and their authorization behavior" applied to a picker's data
scope, not just its permission gate.

### Pagination

Unchanged, deliberately. Since no page-index/offset state exists anywhere
in the frontend today (every list, including the pre-Phase-34 account
directory, fetches up to `LIST_ALL_LIMIT = 500` once with `offset` fixed
at `0`), there is no "invalid page after a filter change" state to
reconcile — `offset` never moves. Building real pagination controls
purely to demonstrate filter/pagination interaction would have been
scope creep the phase brief explicitly warns against ("do not redesign
pagination if the current implementation is already sound"). The backend
`limit`/`offset` parameters already compose correctly with the new
filters (verified live and by test — see below); a future phase that
adds real pagination UI anywhere in this app will get that composition
for free.

### Empty state

`UsersTable` gained an `isFiltered?: boolean` prop. An empty result while
a search/status filter is active renders "No accounts match your
search." instead of the unfiltered "No accounts yet." (which implies
account creation, misleading when the directory isn't actually empty).
No new `EmptyState` primitive — same component, different props.

## Multi-tenancy / IDOR

Unchanged. `q`/`status` are additional `WHERE` clauses over the same
already-global, already-`USER_READ`-gated query — they narrow the result
set, never widen its authorization boundary or leak a second
organization's data (the directory never carried organization-scoped
data to begin with, per ADR 0012 Decision 8). A Manager/Member/Viewer
still gets 403 regardless of what `q`/`status` are set to (verified live
and by test). No client-side check of any kind was added or relied upon
— the backend independently re-validates `Permission.USER_READ` on every
request exactly as before.

## Consequences

- **Backend:** 3 files changed (`app/api/v1/users.py`,
  `app/repositories/user.py`, `app/services/user.py`). **0 new tables, 0
  migrations, 0 new permissions, 0 new routes, 0 change to any existing
  permission's grant set.** `docs/openapi.json` regenerated — a
  10-line-of-diff-context addition (two new optional query parameters
  plus an updated route docstring on `GET /api/v1/users`; verified no
  other route in the diff).
- **Frontend:** 2 new files
  (`features/users/components/UsersFilterBar.tsx` + its test), 5 files
  edited (`usersApi.ts`, `useUserAccounts.ts`, `UsersTable.tsx`,
  `UsersPage.tsx`, plus their existing test files updated for the new
  behavior). No new route, no new nav entry, no new shared UI primitive,
  no new dependency.
- **No index added.** `q` matches via `ilike('%...%')` (a leading
  wildcard), which cannot use a B-tree index regardless; `status` is a
  low-cardinality enum, for which an index would not measurably help a
  full scan at this table's expected size (admin accounts, not one row
  per `Person` — no evidence of a performance problem, and CLAUDE.md §12
  explicitly warns against speculative indexing). Documented here per
  the phase brief's instruction, not deferred silently.
- **No wildcard-character escaping.** A literal `%` or `_` typed into the
  search box is interpreted as a SQL `LIKE` wildcard (matches more
  broadly than a literal search would), not rejected or sanitized beyond
  the parameterization SQLAlchemy already provides (which is what
  prevents SQL injection — a separate, already-satisfied concern from
  wildcard semantics). A known, minor UX limitation, not a security gap;
  left unescaped to keep this a bounded change, and named here rather
  than silently accepted.
- **Tests:** Backend — 12 new tests in `tests/api/test_users.py`
  (default-directory baseline, case-insensitive email search,
  display-name search, no-match, clear-restores-full-directory,
  status filter, combined search+status, invalid-status 422,
  password-field-never-exposed, Manager-still-403-with-search-params —
  full list in the diff). Backend suite: **1006 passed** (was 994 before
  this phase; net +12, no regressions). `ruff check .` clean. `uv run
  pyright` (strict) **0 errors** (a direct `pyright app` invocation
  bypassing `uv run`'s environment resolution was tried first and
  produced ~6000 errors identical in kind on files this phase never
  touched — e.g. `working_schedule.py` — confirming that invocation
  doesn't reproduce this repo's actual, clean, `uv run pyright` gate;
  the documented command is what was ultimately verified clean).
  Frontend — 1 new test file (`UsersFilterBar.test.tsx`, 3 tests) plus
  new/updated tests in `UsersTable.test.tsx` (filtered empty state) and
  `UsersPage.test.tsx` (filter controls render, debounced search reaches
  the query, status filter applies immediately, clearing search restores
  the unfiltered query, the Person picker stays correct under an active
  filter). Frontend suite: **318 passed** (was 309 before this phase; net
  +9 across 4 files: 3 new in `UsersFilterBar.test.tsx`, 1 new in
  `UsersTable.test.tsx`, 5 new in `UsersPage.test.tsx`). `oxlint` clean
  (2 pre-existing warnings in
  `AuthContext.tsx`, untouched by this phase). `tsc -b --noEmit` clean.
  Production build succeeds (`vite build`; the existing single-bundle
  >500kB warning is pre-existing and out of this phase's scope per the
  brief's "no speculative performance work" exclusion).
- **Fresh-DB verification:** `alembic upgrade head` against a brand-new
  SQLite file applied cleanly through the existing migration chain with
  **no new migration to apply** — confirming the "no schema change"
  claim directly, not just by absence of a new file.
- **Live verification:** a real `uvicorn` server was started against
  that freshly-migrated database; `scripts/create_first_owner.py`
  bootstrapped an Owner; three accounts were created over the real API;
  `GET /api/v1/users?q=LOVELACE` (case-insensitive), `?q=hopper`
  (display-name match), `?status=active`, a no-match search, and
  `?status=bogus` (→ 422) were all exercised over real HTTP against the
  real database, confirming the behavior end-to-end beyond what the
  in-memory test suite alone shows. Server stopped and the scratch
  database removed afterward.
- **Browser verification:** unavailable in this environment (the same
  disclosed limitation as every prior phase). Verification was
  unit/component-test, API/live-server, and build-level only — no
  visual/browser claim is made.

## Strict exclusions confirmed untouched

The `USER_WRITE` organization-scoping product decision (ADR 0029), any
membership-management redesign, new roles, new permissions, invitations,
organization hierarchies, billing, SSO/OAuth, email verification,
password reset, external integrations, Scenario snapshots, Import/Export
registration, the remaining prioritization visualizations, a
rank-over-time trend variant, PostgreSQL concurrency work, and any
unrelated cleanup. None were touched.

## Deferred, not dropped

Real pagination controls for the account directory (or any other list
page — this app-wide gap was found, not created, by this phase);
wildcard-character escaping in the search box, if ever judged worth the
added complexity; a shared debounce utility, if a second feature needs
one (this phase's is deliberately local/small, not generalized); the
`USER_WRITE` org-scoping decision itself (ADR 0029, still open,
deliberately not resolved here).

## Confirmation

Phase 35 was **not** started. Nothing in this phase was committed.
