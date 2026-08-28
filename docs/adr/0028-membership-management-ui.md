# ADR 0028: Phase 28 — Membership management UI (first slice)

- **Status:** Accepted
- **Date:** 2026-08-28

## Context

Phase 27 (ADR 0027) shipped the Priority-vs-Effort scatter and did not
select what Phase 28 should be. Per the phase brief's explicit
audit-first instruction, the repository was audited before any code was
written: CLAUDE.md (§§4, 21, 31, 39), `docs/roadmap.md`,
`docs/architecture.md`, `docs/domain-concepts.md`, every ADR through
0027, `docs/PRD-phase-17-prioritization.md`, the complete Phase 17–27
implementation, the Scenario lifecycle/delete path, the complete
prioritization frameworks/scoring/ranking/snapshot/comparison/trend/
WSJF-breakdown/scatter/AI-explanation surface, the Phase 6 import/export
infrastructure and `ImportEntityType`, and — in depth this time, per the
brief's §3 — the organization/membership/user backend
(`app/api/v1/organizations.py`, `app/api/v1/users.py`,
`app/api/v1/auth.py`, `OrganizationMembershipService`/`Repository`,
`UserService`, `authorization.py`, `enums.py`) and every organization-
related frontend surface (`AuthContext`, `OrganizationSwitcher`,
`SelectOrganizationPage`, the Phase 11 `features/access` admin feature,
`AppShell` nav, `routes.tsx`).

## Candidate set — re-verified directly against current code

Per the brief's instruction not to repeat a prior phase's conclusion
without re-checking:

- **Membership / user-management UI** — **fully backend-ready, not
  blocked.** `app/api/v1/organizations.py` exposes list / add / change-
  role / revoke / reactivate memberships, all gated by
  `Permission.MEMBERSHIP_MANAGE` (Admin/Owner), all organization-scoped
  by `_require_active_organization` (a path `organization_id` that isn't
  the caller's active org 404s), all audited
  (`MEMBERSHIP_CREATE`/`ROLE_CHANGE`/`REVOKE`/`REACTIVATE`), and all
  enforcing the Owner-escalation rule (only an Owner may grant or change
  an Owner/Admin role → 403) and the Phase 15 last-Owner invariant
  (atomic guarded `UPDATE` → 422). Zero frontend surface exists. Deferred
  by the Phase 22/25/26/27 audits **for size only**, never for a missing
  capability.
- **Capacity-vs-Priority matrix** (PRD §15) — still blocked. No
  specification anywhere defines "a project's capacity" (which people,
  which period, which aggregation). Unchanged since the Phase 27 audit.
- **Risk-vs-Value quadrant** (PRD §15) — still blocked. `Risk` is a
  project-scoped *set* with no aggregation rule; "Value" is undefined.
  Unchanged.
- **Dependency timeline** (PRD §15) — still blocked.
  `app/models/project_dependency.py` still has only `created_at`; no date
  or duration field exists. Unchanged.
- **Scenario snapshots** — still blocked. `ScenarioService.delete`
  (`app/services/scenario.py:107`) still performs a genuine hard delete;
  the "what happens to a scenario snapshot when its scenario is deleted"
  product decision is unresolved.
- **Risk/Stakeholder/Prioritization/`ProjectDependency`/
  `PortfolioSnapshot` Import/Export** — still blocked.
  `ImportEntityType` (`app/domain/import_export_parsing.py`) still has the
  same 10 members; the missing-natural-identity-key gap for CSV
  upsert-matching is unresolved.
- **Rank-over-time trend variant** — explicitly declined by Phase 24 as a
  settled product decision, not re-litigated (the brief also instructs
  not to add it unless explicitly selected).

**Only one viable, non-blocked candidate: the membership management UI.**
Every other candidate is blocked on an unresolved product decision or was
explicitly declined. No "which candidate" blocking question was
warranted.

## Decision

### Selection: the membership management UI — first bounded slice

The candidate was unambiguous. What genuinely remained was the
**first-slice boundary** of a "materially larger multi-flow vertical
slice," which materially changes what gets built. Per CLAUDE.md §31 and
the brief's §4, this was put to the user as a blocking question with
three concrete bounded options (read-only roster; roster + role/status
management; roster + full user-account lifecycle). The user chose
**roster + role/status management**.

### In scope

A new frontend feature (`apps/web/src/features/members/`) and one new
route, `/admin/members`, gated on `can('membership.manage')` — mirroring
the Phase 11 `features/access` admin feature's shape exactly:

- **Member roster** — every membership in the active organization (active
  **and** revoked), showing display name, email, role, and status. Reads
  `GET /api/v1/organizations/{id}/memberships` (already paginated,
  already returns the composed `email`/`display_name` from the linked
  `User`).
- **Change a member's role** — an inline 5-role `<select>`, one
  `PATCH .../memberships/{user_id}/role` per change.
- **Revoke a member** — `DELETE .../memberships/{user_id}` (active →
  revoked).
- **Reactivate a member** — `POST .../memberships/{user_id}/reactivate`
  (revoked → active).
- **Add an existing account** — an email field plus an initial-role
  `<select>`, `POST .../memberships`.
- **Nav entry** ("Members"), rendered only when `can('membership.manage')`
  — identical treatment to the existing "Access" entry.

### Out of scope (explicit)

- **Creating or disabling `User` accounts.** `app/api/v1/users.py` is not
  touched. "Add member" takes the email of an **existing** account; a
  nonexistent email returns the backend's honest 404 and **no account is
  created** (CLAUDE.md §26). This was the distinguishing line between the
  chosen slice and the larger option.
- **Organization rename / deactivation** (`ORGANIZATION_MANAGE`) — a
  separate surface; the brief's §5 explicitly forbids combining the
  membership UI with unrelated organization features.
- **Any invitation / email-delivery / password-reset / activation /
  onboarding flow.** The backend defines none (`MembershipCreate`'s own
  docstring: "No invitation/email delivery"), so the brief's §3 forbids
  inventing one.
- **A cross-organization member or account directory.** The page only
  ever shows the active organization's own memberships.

### Zero backend changes

Every route consumed already exists (Phases 12/15), is already
`MEMBERSHIP_MANAGE`-gated, is already organization-scoped, is already
audited, and already enforces both the Owner-escalation rule and the
last-Owner invariant. The frontend re-implements **none** of this — it
surfaces the backend's 403 / 422 / 404 / 409 responses inline as
form-/row-level alerts, exactly as `ProjectAccessSection` already
surfaces a grant failure. This mirrors `AccessManagementPage`'s own
stance: the page is gated by `can(...)` for UX only (nav hidden,
`ViewOnlyNotice` fallback); the backend is the security boundary
(CLAUDE.md §21).

### Active-organization source

The organization id for every request is
`useAuth().user.active_organization.id` — the same session-authoritative
active organization the rest of the app already scopes to, re-verified
server-side on every request (Phase 12). It is never a client-supplied
selector.

### Add-member uses a plain email field, not a `/users` directory picker

Deliberately keeps Phase 28 strictly within
`/organizations/{id}/memberships` and avoids any dependency on the
cross-organization account directory (`GET /api/v1/users`), which was the
larger option's territory. The `features/access` `UserPicker` is **not**
reused for this reason.

### Patterns followed, not introduced

`features/members/{api,hooks,components,types,views}` mirrors
`features/access` one-for-one. react-query `useQuery`/`useMutation` with
`['memberships', organizationId]` invalidation. `QueryBoundary`,
`Table`/`Th`/`Td`, `Select`, `Button`, `Badge`, `Card`, `PageHeader`,
`ViewOnlyNotice` reused verbatim. No new UI primitive, no new dependency,
no new architectural convention.

## Consequences

- **0 new backend tables, migrations, permissions, routes, or files.**
  `git diff --stat` against `apps/api/` is empty for this phase.
- New frontend modules under `apps/web/src/features/members/`; one new
  child route in `app/routes.tsx`; one new `NavLink` in
  `components/layout/AppShell.tsx`.
- **Multi-tenancy**: unchanged and preserved. The UI can only ever act on
  the caller's active organization — the backend 404s any other path
  `organization_id` (`_require_active_organization`), and the frontend
  never constructs one.
- **Instance authorization (Phase 11/16)**: untouched — membership
  management is role-gated (`MEMBERSHIP_MANAGE`, Admin/Owner), never
  `ProjectAccessGrant`-scoped, and this phase adds no grant logic.
- **Last-Owner invariant (Phase 15)**: untouched and now has its first
  UI surface — a demotion/revocation that would remove the last active
  Owner returns 422 from the unchanged backend, which the page renders
  inline. No client-side re-derivation of the invariant.
- **Audit**: unchanged — every mutation this UI triggers is already
  audited by the existing routes.
- **Deferred, not dropped**: user-account creation/disable UI and an
  organization-settings UI (both fully backend-ready, both a deliberate
  next slice); the remaining three PRD §15 visualizations (all still
  blocked); Scenario snapshots (still blocked on the `Scenario`
  hard-delete decision); Import/Export registration (still blocked on a
  missing natural identity key); a rank-over-time trend variant (already
  declined).
- **Known limitation**: the role `<select>` offers all five roles even to
  an Admin, who cannot actually assign or change an Owner/Admin role
  (only an Owner can). This is surfaced as the backend's inline 403 after
  the fact rather than by pre-filtering the options from `user.role`. A
  future slice can tighten the option list; it is a UX nicety, not a
  security gap (the backend rejects the write regardless).
- **Residual risk**: none in the backend — no behavior, table, migration,
  permission, or contract changed. Frontend risk is limited to a
  purely additive, role-gated admin page over already-authorized,
  already-audited routes.
- **Verification**: frontend-only phase — no backend behavior changed, so
  no new live API verification was necessary. The routes this UI consumes
  are already covered by `tests/api/test_organizations.py`,
  `tests/services/test_organization_membership.py`, and
  `tests/api/test_cross_organization_boundaries.py`. Browser automation
  is unavailable in this environment (the same disclosed limitation as
  every prior phase); verification was unit/component-test and
  build-level only.

## Confirmation

Phase 29 was **not** started. Nothing in this phase was committed.
