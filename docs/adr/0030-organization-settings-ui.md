# ADR 0030: Phase 30 — Organization settings UI (rename only)

- **Status:** Accepted
- **Date:** 2026-08-28

## Context

Phases 28–29 built the membership and `User`-account admin UIs and named
an organization-settings UI (rename / deactivate) as the remaining
backend-ready admin surface. Phase 30 builds a bounded slice of it.

Per the phase brief's audit-first instruction, the organization-
management backend was audited against executable code before any code
was written: `app/api/v1/organizations.py`, `OrganizationService`,
`OrganizationRepository`, `Organization` (model), `OrganizationCreate`/
`OrganizationUpdate`/`OrganizationRead`, `app/api/deps.py`
(`get_current_membership`, `require_permission`, `require_csrf`),
`authorization.py` (`ROLE_PERMISSIONS`), `AuthService.switch_organization`,
`tests/domain/test_authorization.py`, `tests/api/test_organizations.py`.
The current working tree was confirmed clean (Phases 28–29 committed as
`bc86e7f` / `4da448b` at the user's explicit request after each report).

## Audit findings — the executable contract

| # | Question | Finding |
|---|---|---|
| 1 | Endpoints for read/update/deactivate | `GET /api/v1/organizations/{id}`, `PATCH /api/v1/organizations/{id}`, `POST /api/v1/organizations/{id}/deactivate` — all three in `app/api/v1/organizations.py`. |
| 2 | Request/response schemas & validation | `OrganizationUpdate` = `{ name: str \| None, min_length=1, max_length=200 }`. `slug` and `is_active` deliberately excluded (`slug` immutable; `is_active` has its own endpoint). All three routes return `OrganizationRead` = `{ id, name, slug, is_active, created_at, updated_at }`. Name has no uniqueness constraint (rename cannot 409). |
| 3 | Authorization | All three gated by `_require_active_organization` (path id must equal the caller's active org, **else 404** — no 403, no IDOR) **and** `_require_manage(ORGANIZATION_MANAGE)`. `ORGANIZATION_MANAGE` is **Owner-only** — `ROLE_PERMISSIONS[OWNER] − ROLE_PERMISSIONS[ADMIN] == {ORGANIZATION_MANAGE}` (`test_authorization.py`). Admin/Manager/Member/Viewer → 403; unauthenticated → 401; no active org → 409. `PATCH` and `deactivate` require CSRF; `GET` does not. |
| 4 | Safety/invariant checks on deactivation | **None.** `OrganizationService.deactivate` is `organization.is_active = False; flush`. No last-Owner-style guard, no "projects exist" check, no confirmation token. |
| 5 | Effect on memberships/users/sessions/projects/allocations/scenarios/snapshots | **None directly** — only the `organizations.is_active` flag flips; every other row is untouched, no cascade. But `get_current_membership` re-checks `is_active` **on every request**, so every member (including the acting Owner) is denied on their next request (409 "This organization is no longer active."). `switch_organization` re-checks it too → cannot switch back in. |
| 6 | Reversible? | **No — via the product.** Nothing anywhere in the codebase sets `Organization.is_active` back to `True` except creating a new organization. `OrganizationUpdate` excludes it; there is no reactivate endpoint or service method. Only a direct database write could undo a deactivation. |
| 7 | Rename while preserving relationships? | **Yes.** `OrganizationService.update` `setattr`s `name` only; the row's `id`/`slug` and every FK pointing at it are untouched. |
| 8 | Cross-org / IDOR risk? | **No.** `_require_active_organization` 404s any path id that isn't the caller's own active organization, matching the Phase 12 "look like not-found" rule. |
| 9 | Destructive / soft-delete / status change? | A **soft status flag** — not data-destructive, no cascade — but **product-irreversible** and **globally locking** (see #5, #6). |
| 10 | Safe to expose directly through UI? | **Rename: yes.** **Deactivation: not as a bounded UI slice** — see Decision. |

## Product decision

Deactivation's lifecycle is now fully understood, but the operation is
irreversible through the product, locks out every member including the
Owner who triggers it, and has no backend guard. Whether to put that
behind a settings-page button is a genuine product decision, so it was
put to the user with three concrete options (rename only; rename +
stark inline confirm; rename + type-to-confirm).

**The user chose: rename only; defer deactivation.**

Rationale (user-selected): exposing a one-click, product-irreversible,
self-locking action with no undo path is disproportionate for a bounded
UI slice, and CLAUDE.md §26/§33 discourage shipping a control whose
consequences the backend cannot walk back. Deactivation stays
backend-only until a reactivation path and/or a backend safety guard
exists.

## Decision: rename-only Organization Settings surface, zero backend changes

A new frontend feature (`apps/web/src/features/organization/`) and one
route, `/admin/organization`, gated on `can('organization.manage')` —
mirroring `features/members/` (Phase 28) and `features/users/`
(Phase 29) one-for-one:

- **Read** the current organization via `GET /api/v1/organizations/{id}`
  (the id is `useAuth().user.active_organization.id` — the session-
  authoritative active org, never a client-supplied selector).
- **Display**: the name (in the rename field), the immutable `slug`
  (read-only, labelled "Cannot be changed"), and an Active/Inactive
  status `Badge`.
- **Rename** via `PATCH /api/v1/organizations/{id}` `{ name }`. The form
  enforces exactly `OrganizationUpdate`'s constraint (`1..200` chars,
  and "changed from current") and nothing more. On success it
  invalidates both `['organization', id]` and the `['session']` query,
  so `/auth/me`'s `active_organization.name` — which the header switcher
  and user menu render — refetches and the new name shows everywhere.
- **No deactivation control** anywhere on the page. A one-line note
  states the identifier is fixed; deactivation is simply absent.
- **Nav entry** ("Organization"), rendered only when
  `can('organization.manage')` — identical treatment to "Access",
  "Members", "Accounts".

### Authorization

`can('organization.manage')` gates the page and nav for UX only (else
`ViewOnlyNotice`). The backend re-checks `ORGANIZATION_MANAGE` + the
active-org match on every request and is the sole boundary
(CLAUDE.md §21). The frontend re-implements none of it and surfaces the
backend's 403/404/422 verbatim.

### Multi-tenancy

Unchanged. The page can only ever read or rename the caller's own active
organization — the backend 404s any other path id
(`_require_active_organization`), and the frontend never constructs one.
No `Organization` relationship, membership, or owned row is touched by a
rename.

### Backend: test-only additions

No production code changed. `tests/api/test_organizations.py` gained
five tests documenting the already-existing `GET`/`PATCH` contract the
UI now consumes (there was previously **zero** direct API coverage for
either): Owner read + rename round-trip (slug unchanged); empty-name
422; `organization.update` audit event; non-Owner (Admin/Manager/
Member/Viewer) → 403; a non-active-org path id → 404.

## Consequences

- **0 new backend tables, migrations, permissions, routes, or production
  files.** `git diff --stat` against `apps/api/` shows only
  `tests/api/test_organizations.py`. `docs/openapi.json` unchanged (no
  API change).
- New frontend modules under `apps/web/src/features/organization/`; one
  new child route in `app/routes.tsx`; one new `NavLink` in
  `components/layout/AppShell.tsx`.
- **Last-Owner invariant (Phase 15)** and **global `USER_WRITE`
  semantics (Phase 29)**: untouched.
- **Audit**: unchanged — `PATCH /organizations/{id}` already records
  `ORGANIZATION_UPDATE` with `{fields: ["name"]}`.
- **Verification**: frontend-only — no backend behavior changed, so
  migration verification is **not applicable** and no new live API
  verification is necessary. The `GET`/`PATCH` contract is now covered
  by the five new tests plus the full suite; deactivation lifecycle is
  unchanged and covered by its existing `deps`/`auth` re-verification
  tests. Browser automation is unavailable in this environment;
  verification was unit/component-test and build-level only — no
  visual/browser claim is made.
- **Deferred, not dropped**: organization **deactivation** UI (pending a
  backend reactivation path and/or safety guard); an organization
  **reactivation** endpoint itself (backend); everything the brief's
  scope-discipline list already defers (authorization redesign,
  invitations, email verification, password reset, SSO/OAuth, billing,
  org hierarchies, external integrations, Scenario snapshots, blocked
  import/export registration, blocked PRD visualizations, rank-over-time
  trend variant, PostgreSQL verification of the Phase 15 concurrency
  guard).
- **Known limitation**: `slug` is shown but not editable (backend treats
  it as immutable — correct). A deactivated organization would render
  the page's "Inactive" badge, but since a deactivated org denies the
  request that loads the page (409), that state is effectively
  unreachable through the UI — the badge exists for completeness only.
- **Residual risk**: none newly introduced. No backend behavior, table,
  migration, permission, or API contract changed. The page is a purely
  additive, Owner-gated read + single-field rename over an endpoint that
  was already authorized, CSRF-protected, and audited.

## Confirmation

Phase 31 was **not** started. Nothing in this phase was committed.
