# ADR 0032: Phase 32 — Organization deactivation / reactivation UI

- **Status:** Accepted
- **Date:** 2026-08-28

## Context

Phase 31 (ADR 0031) made organization deactivation a safe, reversible
**backend** lifecycle: a ≥2-active-Owner atomic guard on
`POST /api/v1/organizations/{id}/deactivate` (422 otherwise) and a new
`POST /api/v1/organizations/{id}/reactivate` (Owner-of-the-target-org
only, CSRF-protected, idempotent, no cascade). Phase 31 explicitly
deferred the frontend. Phase 32 is that frontend — it **consumes the
Phase 31 contract without changing a single backend file**.

## Audit findings

- **A. Where Organization Settings lives:** `apps/web/src/features/organization/`,
  route `/admin/organization`, nav entry "Organization" — all gated on
  `can('organization.manage')` (Owner-only, `ROLE_PERMISSIONS`). Added in
  Phase 30 (ADR 0030), currently rename-only.
- **B. Current-organization frontend state:** `useAuth().user.active_organization`
  (`{ id, name, slug }` — `OrganizationSummary` in `app/schemas/auth.py`).
  **It has no `is_active` field.** `/auth/me` (`SESSION_QUERY_KEY = ['session']`,
  `staleTime: Infinity`) is the source of truth for the active org,
  `role`, and `permissions`.
- **C. Behavior when the active org goes inactive:** `/auth/me` still
  returns 200 with `active_organization` populated and `role`/`permissions`
  intact (the Owner membership is untouched by deactivation; `_build_me`'s
  `list_by_ids` doesn't filter `is_active`). Every **org-scoped** route —
  including `GET /api/v1/organizations/{id}` — returns **409**
  (`NoActiveOrganizationError`, "This organization is no longer active.")
  because `get_current_membership` re-checks `is_active` per request.
  `AuthContext` status therefore stays `'authenticated'` (not
  `'no-organization'`), so `RequireAuth` renders the normal `AppShell`.
- **D. What the frontend can reliably know:** organization **id** and
  **name** (from `active_organization`); **whether the user is an Owner**
  (`can('organization.manage')`, backed by `/auth/me` permissions);
  **whether the org is active** — only indirectly, by observing a 409
  from an org-scoped request. **The ≥2-active-Owner count is NOT
  available** from any endpoint usable here: `/auth/me` doesn't carry it,
  and `GET /organizations/{id}/memberships` exposes membership `role`/
  `status` but not the linked `User.status` that Phase 31's guard also
  requires — so a frontend count would be an incomplete duplicate of
  backend business logic.
- **E. active-Owner-count API:** none suitable — see D.
- **F. Inactive org in the session response:** yes — `active_organization`
  stays populated; `/auth/me` keeps working.
- **G. How an Owner reaches recovery:** the "Organization" nav link
  stays visible (permissions intact) → `/admin/organization`. Right after
  the Owner clicks Deactivate, they are already on that page.
- **H. Global endpoint usable while inactive:** `/auth/me`,
  `/auth/logout`, and (Phase 31) `POST .../{id}/reactivate` itself.
- **I. Existing router can host the recovery state:** yes — the existing
  `/admin/organization` route renders it; no new route or routing
  architecture is needed.
- **J. Existing inline-confirm pattern:** yes —
  `ScenarioWorkspacePage` (delete scenario) and `features/users`'
  `UsersTable` (disable account) both use a two-step "button → prompt +
  Confirm/Cancel" inline pattern with no modal primitive. Reused here.

## Decision

### Scope (frontend-only)

1. **Deactivation section** on `/admin/organization`, rendered inside the
   already-Owner-gated `OrganizationSettingsManager`. Explains that
   deactivation is immediate, stops org-scoped access for everyone,
   deletes nothing, and is reversible only by an Owner while another
   active Owner remains. Two-step inline confirm
   (`DeactivateOrganizationSection`) → `POST .../deactivate`.
2. **No frontend Owner-count check.** The frontend cannot reliably know
   the count (audit D/E), so per CLAUDE.md §21 and the phase brief it
   does **not** disable the button on a guess — it lets the backend's
   **422** be authoritative and surfaces that message **verbatim** on the
   section, with no false "success".
3. **Recovery surface** (`InactiveOrganizationPanel`): when
   `useOrganization(id)` (i.e. `GET /organizations/{id}`) returns a
   **409**, and the caller still holds `organization.manage` (so it can
   only mean "deactivated", never "membership revoked" — a revoked
   membership nulls out `role`/`permissions` and never reaches this
   component), the page renders the panel in place of the settings form.
   The panel names the org (from `active_organization.name`, still
   available), explains recovery, and offers **Reactivate** →
   `POST .../reactivate`.
4. **Cache handling.** `useDeactivateOrganization` /
   `useReactivateOrganization` call `queryClient.invalidateQueries()`
   (all) on success — every org-scoped surface then refetches into its
   correct state: this page into the recovery panel (deactivate) or back
   into the settings form (reactivate), other pages into a clean
   "no longer active" error (deactivate) or fresh data (reactivate). No
   forced logout; the existing session keeps working after reactivation
   with **no re-login**, matching Phase 31's verified behavior.
5. **409 is not reinterpreted globally.** Only `OrganizationSettingsManager`
   treats a 409 specially, and only from its own `useOrganization` query.
   Every other page keeps the existing generic `ErrorState`
   (which already renders the backend's "This organization is no longer
   active." message).

### Authorization / security

- Page + nav gated on `can('organization.manage')` — **UX only**. The
  backend re-checks `ORGANIZATION_MANAGE` + `_require_active_organization`
  + CSRF on deactivate, and active-Owner-membership-of-target + CSRF on
  reactivate. A non-Owner never sees an actionable control (they get
  `ViewOnlyNotice`); if one somehow calls either endpoint, the backend
  returns 403/404 and the UI surfaces it verbatim.
- **No new permission, no new role, no new modal/dialog primitive, no new
  route.**
- **Multi-tenancy / IDOR:** every call uses `useAuth().user.active_organization.id`
  — the session's own active org, never a user-supplied id. `reactivate`
  targets that same id; the backend independently 404s a caller who is
  not an Owner-member of it. The UI never renders another tenant's data.
- CSRF is handled by the existing `apiPost` (double-submit header) — the
  UI adds nothing and bypasses nothing.

### Why backend enforcement stays authoritative

The frontend performs **zero** safety logic: it does not compute the
Owner count, does not decide whether deactivation is allowed, and does
not gate reactivation on anything but the existing permission (UX). The
422 guard, the reactivation authorization (403/404), CSRF, and the
active-organization boundary are all enforced server-side and surfaced,
not re-implemented (CLAUDE.md §4/§21).

## Consequences

- **0 backend files changed. 0 migrations. 0 new permissions/roles. 0
  new routes. 0 API contract changes.** `docs/openapi.json` unchanged.
- New frontend: `DeactivateOrganizationSection.tsx`,
  `InactiveOrganizationPanel.tsx`; `useOrganization.ts` gains
  `useDeactivateOrganization`/`useReactivateOrganization`;
  `organizationApi.ts` gains `deactivate`/`reactivate`;
  `OrganizationSettingsPage.tsx` wires the section + 409 recovery
  detection. No nav change (the "Organization" entry already exists).
- **Known limitations:**
  - **No global inactive-org banner.** If an Owner returns to a cold app
    with the active org already deactivated, `/` → `/capacity` shows a
    generic "no longer active" error first; recovery is one click away
    via the still-visible "Organization" nav link, but it is not
    surfaced automatically. A clean global banner needs
    `OrganizationSummary.is_active` on `/auth/me` (a small, read-only,
    backwards-compatible backend addition) — deliberately **not** done
    in this frontend-only phase; recommended for Phase 33.
  - **Non-Owner members of a deactivated org** see "no longer active"
    error states everywhere and a `ViewOnlyNotice` on
    `/admin/organization`, with no recovery affordance — correct, since
    reactivation is Owner-only, but a dedicated "ask an Owner to
    reactivate" message would be friendlier (Phase 33).
  - **Deactivated orgs still appear in `MeRead.organizations` / the
    `OrganizationSwitcher`** (pre-existing; ADR 0031 Consequences). The
    recovery flow does **not** depend on this being fixed — it works
    entirely through `/admin/organization` + `POST .../reactivate` — so
    per the phase brief it was left untouched. Selecting a deactivated
    org in the switcher already fails gracefully (`switch-organization`
    → 404, surfaced by `OrganizationSwitcher`'s existing error handling).
    Recommended for Phase 33.
- **Residual risk:** none new. A purely additive, Owner-gated frontend
  over already-authorized, already-audited endpoints. The backend stays
  safe even if the UI is bypassed.

## Confirmation

Phase 33 was **not** started. Nothing in this phase was committed.
