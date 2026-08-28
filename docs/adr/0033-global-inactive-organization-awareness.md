# ADR 0033: Phase 33 — Global inactive-organization awareness & switcher cleanup

- **Status:** Accepted
- **Date:** 2026-08-28

## Context

The inactive-organization lifecycle was built across three phases:

- **Phase 31** (ADR 0031) made deactivation a safe, reversible **backend**
  lifecycle: a ≥2-active-Owner atomic guard on
  `POST /api/v1/organizations/{id}/deactivate` (422 otherwise), a new
  Owner-of-the-target-org-only, CSRF-protected, idempotent
  `POST /api/v1/organizations/{id}/reactivate`, no cascade, no forced
  logout. `get_current_membership` re-checks `Organization.is_active`
  per request, so an inactive org 409s every org-scoped route while
  `/auth/me` keeps resolving.
- **Phase 32** (ADR 0032) added the **settings UI**: a `Deactivate`
  section and an `InactiveOrganizationPanel` recovery surface on the
  existing Owner-gated `/admin/organization` page, detecting the inactive
  state from a **scoped** 409 on that page's own
  `GET /organizations/{id}`. It surfaces the backend's 422/403/404
  verbatim and re-derives no safety logic.

Two gaps remained, both named in ADR 0032's Known Limitations:

1. **No global awareness.** `OrganizationSummary` (the org shape in
   `/auth/me`) carries only `id`/`name`/`slug` — **no `is_active`**. So
   outside `/admin/organization`, the frontend cannot proactively know
   its active org went inactive; the Owner lands on a generic
   "no longer active" error at `/capacity` first and must find the
   "Organization" nav link.
2. **Switcher still lists deactivated orgs.** `MeRead.organizations`
   (from `list_active_for_user` memberships → `list_by_ids`, unfiltered
   by `is_active`) still contains a deactivated org, and
   `OrganizationSwitcher` / `SelectOrganizationPage` offer it as a normal
   choice — selecting it just 404s (`switch-organization` re-checks
   `is_active`).

Phase 33 closes both.

## Audit findings

- `app/schemas/auth.py::OrganizationSummary` has `ConfigDict(from_attributes=True)`
  and is **only ever built via `model_validate(<Organization>)`** (two
  call sites in `me_to_read`). Adding `is_active: bool` therefore
  auto-populates from the ORM object — **no `_build_me` / `me_to_read`
  change, no direct constructors to update, no migration** (`Organization.is_active`
  exists since the Phase 12 migration).
- `GET /api/v1/organizations/mine` already returns **`OrganizationRead`**
  (which has `is_active`), and has **no frontend consumer** — no change
  needed there.
- Frontend: `OrganizationSwitcher` reads `user.organizations` +
  `user.active_organization` straight from `/auth/me`; no fetch of its
  own. `SelectOrganizationPage` reads `user.organizations`. `AppShell`
  already calls `useAuth()`. `RequireAuth` renders `AppShell` for
  `status === 'authenticated'`, which an inactive-active-org still is
  (`active_organization` is non-null). No existing shared "Banner"
  primitive; feature components compose `components/ui` primitives + a
  `<Link>`.
- Phase 32's scoped 409 handling on `OrganizationSettingsManager` is
  independent of this work and must stay.

## Decision

### A. `OrganizationSummary.is_active` (backend)

Add a read-only `is_active: bool` to `OrganizationSummary`, populated
straight from `Organization.is_active` via the existing
`model_validate`. It appears on both `active_organization` and every
entry of `organizations` in `/auth/me` (and `/auth/login`,
`/auth/switch-organization`, which share the schema). **Never derived
from a 409** — it is the persisted flag. Informational session state
only; `get_current_membership` re-checking `is_active` per request
remains the authorization boundary. No new endpoint, permission, role,
migration, or change to deactivation/reactivation/CSRF/active-org
enforcement.

### B. Global inactive-organization banner (frontend)

`features/organization/components/InactiveOrganizationBanner.tsx` — a
feature component (composed from a `role="alert"` `<div>` + a
react-router `<Link>`, not a new `components/ui` primitive), rendered in
`AppShell` **between the header and `<main>`**, only when
`useAuth().user?.active_organization?.is_active === false`. It is
**persistent** (not a toast, not dismissible, not a modal) and clears
by itself the moment `is_active` returns to `true`.

- Names the inactive organization (from `active_organization.name`,
  still present in the session) and states org-scoped features are
  unavailable.
- **Owner** (`can('organization.manage')` — the existing Owner-only
  permission): a `<Link to="/admin/organization">` to the **existing**
  Phase 32 recovery panel. No new recovery route, no new endpoint, no
  duplicated reactivation call.
- **Non-Owner**: "Ask an organization Owner to reactivate it." — no
  action they cannot perform (CLAUDE.md §21).

The banner is **not** an authorization boundary: it renders from session
state the backend already vouches for, offers only a navigation link,
and the backend independently rejects a non-Owner reactivation (403).

### C. Switcher cleanup (frontend)

- **`OrganizationSwitcher`**: `selectable = user.organizations.filter(o => o.is_active || o.id === activeOrgId)`
  — active orgs, plus the current one even if inactive (so the
  `<Select>`'s `value` always has a matching option and the user can see
  which org they're in). The current org is labelled `"{name} (inactive)"`
  when inactive. Renders `null` when `selectable.length <= 1` (unchanged
  "nothing to switch to" behavior). A deactivated org the caller is a
  member of but not currently in is simply omitted.
- **`SelectOrganizationPage`**: there is no "current" org on this page
  (it's the no-active-org state), so it filters to `o.is_active` with
  nothing kept. The "create an organization" form always remains.

**Frontend filtering is UX only** — it removes an option that would 404
anyway. The backend still 404s any `switch-organization` into an inactive
org regardless of what the UI shows. The current inactive org stays in
`MeRead.organizations` (needed for the `<Select>` value and unaffected —
the banner reads `active_organization`, a separate field).

### Session / cache behavior

Phase 32's `useDeactivateOrganization` / `useReactivateOrganization`
already call `queryClient.invalidateQueries()` (all) on success, which
refetches `['session']` (`/auth/me`). So after reactivation
`active_organization.is_active` flips `false → true` and the banner
disappears with **no re-login and no new invalidation code** — verified
by test and live. `AuthContext`'s `staleTime: Infinity` on the session
query is fine: the explicit invalidation is what refreshes it.

## Consequences

- **Backend:** 1 file — `app/schemas/auth.py` (+`is_active: bool` on
  `OrganizationSummary`). **0 migrations, 0 new endpoints/permissions/
  roles.** `docs/openapi.json` regenerated (7-line diff: the field + its
  `required` entry + the docstring).
- **Frontend:** new `InactiveOrganizationBanner.tsx`; `AppShell.tsx`
  renders it; `OrganizationSwitcher.tsx` + `SelectOrganizationPage.tsx`
  filter inactive orgs; `features/auth/types/auth.ts` mirrors the new
  field; `test/fixtures.ts` + 2 inline test builders updated.
- **Multi-tenancy / IDOR:** `is_active` comes from the organization the
  authenticated session already resolves to — a client cannot supply an
  id to influence it. Org names/slugs still render only from authorized
  session data. Reactivation still uses the Phase 31 target-org
  authorization. No inactive org's private data is newly exposed.
- **Lifecycle preserved and verified** (test + live uvicorn): active →
  `is_active: true`, no banner, org selectable; Owner deactivates →
  next `/auth/me` has `active_organization.is_active: false`, session /
  role / permissions intact, banner appears, org no longer a normal
  switcher choice; Owner opens `/admin/organization` → Phase 32 panel →
  reactivate → `/auth/me` `is_active: true`, banner gone, no re-login,
  org selectable again.
- **Known limitations:**
  - An account whose **only** memberships are all to deactivated orgs
    *and* none auto-selected at login (needs ≥2 such memberships) lands
    on `SelectOrganizationPage` with an empty selection list and only
    the create-org form — it cannot self-recover any of them from there
    (recovery requires another Owner, or the single-membership
    auto-select path, which does work and shows the banner). Rare;
    unchanged risk vs. the pre-Phase-33 "click it and get a 404".
  - On `/admin/organization` an Owner sees **both** the global banner
    and the Phase 32 recovery panel — mildly redundant, deliberately
    kept (the banner is "persistent while inactive").
- **Deferred:** everything on the phase brief's exclusion list, plus a
  friendlier all-memberships-inactive recovery surface.

## Confirmation

Phase 34 was **not** started. Nothing in this phase was committed.
