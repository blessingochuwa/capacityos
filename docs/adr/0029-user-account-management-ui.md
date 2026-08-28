# ADR 0029: Phase 29 — User account management UI

- **Status:** Accepted
- **Date:** 2026-08-28

## Context

Phase 28 (ADR 0028) shipped the membership-management UI and named a
`User`-account create/disable/re-enable UI as its natural companion
slice, fully backend-ready and deliberately excluded. Phase 29 builds
that slice.

Per the phase brief's audit-first instruction, the repository was audited
before any code was written: CLAUDE.md (§§4, 21, 26, 29, 31, 39),
`docs/roadmap.md`, `docs/architecture.md`, `docs/domain-concepts.md`,
every ADR through 0028, the complete Phase 28 `features/members/`
implementation, and the `User` backend —
`app/api/v1/users.py`, `UserService`, `UserUpdate`/`UserCreate`/`UserRead`,
`UserRepository` (`list_filtered`, `disable_if_safe`), `AuthService.login`/
`resolve_session`, `authorization.py`'s `ROLE_PERMISSIONS`
(`USER_READ`/`USER_WRITE`), `OrganizationMembershipRepository`, and the
existing test suites (`tests/api/test_users.py`, `test_rbac.py`,
`test_auth.py`, `test_organizations.py`,
`test_cross_organization_boundaries.py`).

## Candidate verification (re-checked directly against current code)

Every Phase 28 deferred candidate was re-verified, not assumed from the
roadmap:

- **`User`-account management UI** — **still fully backend-ready, no
  backend change required.** `POST /api/v1/users` creates an `active`
  account (`User.status` defaults to `ACTIVE`; `UserCreate` doesn't set
  it). `PATCH /api/v1/users/{id}` with `status: disabled` routes through
  `UserRepository.disable_if_safe` (the Phase 15 last-Owner guard); with
  `status: active` it is a plain re-enable (idempotent). `GET
  /api/v1/users` is a paginated global account directory. All three are
  gated by `Permission.USER_WRITE` / `USER_READ` (Admin/Owner only).
  `UserRead` exposes `status`, `person_id`, `last_login_at`. Nothing was
  missing.
- **Organization rename/deactivate UI** — still backend-only; explicitly
  out of scope here (brief §"Do not bundle").
- **Scenario snapshots** — still blocked. `ScenarioService.delete` still
  hard-deletes; the lifecycle product decision is unresolved.
- **Import/Export registration** — still blocked. `ImportEntityType`
  still has the same 10 members; no natural identity key for CSV
  upsert-matching.
- **The three remaining PRD §15 visualizations** — still blocked on
  unspecified cross-domain semantics (Capacity-vs-Priority,
  Risk-vs-Value) or missing data (`ProjectDependency` still has only
  `created_at`).
- **Rank-over-time trend variant** — already declined by Phase 24.

No unresolved product decision materially affects scope. No hard stop.

## Decision

### Scope: a bounded user-account lifecycle UI, zero backend changes

A new frontend feature (`apps/web/src/features/users/`) and one route,
`/admin/users`, gated on `can('user.write')` — mirroring
`features/members/` (Phase 28) and `features/access/` one-for-one:

- **Account directory** — `GET /api/v1/users`, paginated. Table columns:
  display name, email, status (Active / Disabled / Invited badge),
  linked Person, last login. Reads the **global** account list (see
  "Multi-tenancy" below) — labelled as such, never as "this
  organization's members."
- **Create an account** — `POST /api/v1/users`: email, password
  (min 10, max 128 — exactly `UserCreate`'s constraint, nothing more),
  display name (1–200), and an optional link to a Person in the active
  organization. The created account is `active` — there is no status
  choice on the form.
- **Disable an account** — `PATCH .../{id}` `{status: "disabled"}`,
  behind an inline "Disable this account? / Confirm / Cancel"
  confirmation (the exact pattern `ScenarioWorkspacePage` and
  `ImportExportPage` already use — no modal, no new primitive). A 422
  from the Phase 15 last-Owner guard is rendered **verbatim** on the
  row.
- **Enable an account** — `PATCH .../{id}` `{status: "active"}` for a
  `disabled` **or** `invited` account (both block login identically —
  `AuthService.login` refuses any non-`active` status). No confirmation
  (constructive action, matching "Reactivate" in Phase 28).
- **Nav entry** ("Accounts"), rendered only when `can('user.write')` —
  identical treatment to "Access" and "Members".

### Out of scope (explicit)

Organization rename/deactivation; invitations; email verification;
password-reset; SSO/OAuth; billing; external identity providers; any
redesign of the cross-organization account directory; any backend
authorization change; any new permission. The form invents **no**
password-strength, onboarding, invitation, or activation semantics
beyond `UserCreate`'s own `min_length=10` — CLAUDE.md §26.

### Authorization

Gated by `can('user.write')` for UX only (page + nav hidden, else
`ViewOnlyNotice`). `USER_READ` and `USER_WRITE` have **identical** grant
sets in `ROLE_PERMISSIONS` (Admin/Owner), so one gate is sufficient and
correct — a role that cannot write cannot usefully use the page. The
backend re-checks `require_permission(USER_WRITE)` / `USER_READ` on every
request independently; the frontend re-derives none of it and surfaces
the backend's own 403/404/409/422 messages inline (CLAUDE.md §21). No
client-side permission logic diverges from `Permission.USER_WRITE`.

### Multi-tenancy: `User` management is global, not organization-scoped

Determined from the actual backend, not assumed from Phase 28:

- `GET /api/v1/users`, `GET /api/v1/users/{id}`, `POST /api/v1/users`,
  and `PATCH /api/v1/users/{id}` all operate on the **global** account /
  login identity with **no organization filter** (ADR 0012 Decision 8 —
  the directory is deliberately cross-organization so an admin's "add an
  existing account by email" flow, which Phase 28's add-member and
  Phase 11's access grants both depend on, can find any account). This
  is a pre-existing, documented contract; Phase 29 preserves it and does
  not change it.
- The **only** organization-scoped element is the optional `person_id`
  link: `UserService.create`/`update` validate `person_id` against the
  **acting** organization's People. The UI's Person picker therefore
  offers only People in the active organization that aren't already
  linked to an account; the list's "Linked Person" column resolves
  `person_id` against the active organization's People and shows
  "Linked to a person in another organization" when the id is set but
  not resolvable locally (an honest statement of the boundary, not a
  leak of the other org's data — no name, no id is shown).
- The **last-Owner invariant** on disable is enforced by
  `disable_if_safe` across **every** organization the account is an
  active Owner of, not just the acting one.
- A pre-existing property surfaced by this audit and left unchanged: an
  Admin/Owner of organization A can, through this global contract,
  rename or disable an account whose only membership is organization B.
  This is the existing `USER_WRITE` contract (since Phase 10/12), it is
  guarded by the global last-Owner check, and the brief forbids
  redesigning authorization. It is recorded here as a known property and
  a candidate for a future explicit product decision, not something
  Phase 29 alters.

`User` vs `OrganizationMembership` vs `Person` vs active organization:
a **User** is a global login identity (unique email, account status,
lockout) with no role and no organization; an **OrganizationMembership**
is where a User gets a role within one organization (Phase 28's UI);
a **Person** is an organization-scoped planning entity a User may
optionally link to; the **active organization** is the session's current
tenant context, which scopes the Person picker but not the account list.

### Frontend architecture

`features/users/{types,constants,api,hooks,components,views}` mirrors
`features/members/` exactly. react-query `useQuery`/`useMutation` with
`['users']` invalidation. `QueryBoundary`, `Table`/`Th`/`Td`, `Select`,
`Button`, `Badge`, `Card`, `PageHeader`, `ViewOnlyNotice`, and the
inline-confirm pattern reused verbatim. `usePeopleLookup` (existing
`@/hooks/usePeople`) resolves the Person link. No new UI primitive, no
new dependency, no new architectural convention.

## Consequences

- **0 new backend tables, migrations, permissions, routes, or files.**
  `git diff --stat` against `apps/api/` is empty for this phase.
  `docs/openapi.json` is unchanged (no API change).
- New frontend modules under `apps/web/src/features/users/`; one new
  child route in `app/routes.tsx`; one new `NavLink` in
  `components/layout/AppShell.tsx`.
- **Multi-tenancy**: unchanged. The Person picker and the "Linked
  Person" column are the only organization-scoped elements; the account
  list is global by the existing contract.
- **Last-Owner invariant (Phase 15)**: untouched; now has a second UI
  surface (the first was Phase 28's role change / revoke). A blocked
  disable renders the backend's 422 message verbatim.
- **Audit**: unchanged — `PATCH /users/{id}` already records
  `USER_STATUS_CHANGE` / `USER_UPDATE` and `POST /users` records
  `USER_CREATE`, all with `organization_id = acting org`.
- **Verification**: frontend-only — no backend behavior changed, so no
  new live API verification is necessary. The account lifecycle and its
  security boundaries are already covered by `tests/api/test_users.py`
  (create, duplicate-email 409, last-Owner protection on both demote and
  disable including sole-owner-of-a-second-organization, non-owner
  disable, `USER_STATUS_CHANGE` audit), `tests/api/test_rbac.py` (a
  Manager gets 403 on `/users`; Admin can manage users),
  `tests/api/test_auth.py` (a disabled account cannot log in and gets
  the generic message), and `tests/api/test_cross_organization_
  boundaries.py`. Browser automation is unavailable in this environment
  (the same disclosed limitation as every prior phase); verification was
  unit/component-test and build-level only — no visual/browser claim is
  made.
- **Known limitation**: the account list is the full global directory
  with no server-side filter; on an instance with many organizations it
  can be long. Pagination is wired (`limit`/`offset`), but there is no
  search/filter box in this slice. `invited` accounts are displayed with
  their own badge and offered "Enable" (→ `active`); the UI never *sets*
  `invited` (no invite flow exists to justify it).
- **Deferred, not dropped**: an organization-settings UI (rename/
  deactivate); a search/filter box for the account directory; an
  explicit product decision on whether `USER_WRITE` should be
  organization-scoped rather than global; the remaining Phase 28
  deferrals (Scenario snapshots, Import/Export registration, the three
  PRD visualizations, the rank-over-time trend variant), all still
  blocked.
- **Residual security risk**: none newly introduced. No backend
  behavior, table, migration, permission, or API contract changed. The
  page is a purely additive, `USER_WRITE`-gated admin surface over
  routes that were already authorized and audited. The pre-existing
  global `USER_WRITE` scope is unchanged and explicitly recorded above.

## Confirmation

Phase 30 was **not** started. Nothing in this phase was committed.
