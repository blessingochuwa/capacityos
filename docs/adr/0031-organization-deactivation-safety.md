# ADR 0031: Phase 31 — Organization deactivation safety & reactivation

- **Status:** Accepted
- **Date:** 2026-08-28

## Context

Phase 30 (ADR 0030) shipped the Organization Settings **rename** UI and
deliberately deferred **deactivation**, because the executable backend
contract was unsafe:

- `OrganizationService.deactivate` set `is_active=False` with **no guard**.
- **No reactivation** service, route, or any code path set
  `is_active=True` again (only `create` did, for new organizations).
- `get_current_membership` (`app/api/deps.py`) re-checks
  `organization.is_active` on **every request**, so after deactivation
  every member — including the Owner who deactivated it — is denied
  (`NoActiveOrganizationError` → 409) on their very next org-scoped
  request.
- `AuthService.switch_organization` also 404s an inactive organization.
- The operation is **not** data-destructive and does **not** cascade —
  only the boolean flips — but it was **irreversible through the
  product**.

Phase 30's recommended next step: a backend reactivation path plus a
deactivation safety guard, established as a backend contract a later
Phase 32 deactivation UI could safely consume. Phase 31 is that backend
slice. **It does not add or change any frontend.**

## Audit — the full lifecycle traced against executable code

`Organization` model, `OrganizationService`, `OrganizationRepository`,
`app/api/v1/organizations.py`, `app/schemas/organization.py`,
`app/api/deps.py` (`get_current_membership`, `_require_active_organization`,
`require_permission`, `require_csrf`), `AuthService.resolve_session`/
`switch_organization`, `authorization.py` (`ROLE_PERMISSIONS`,
`Permission.ORGANIZATION_MANAGE`), Phase 15's `disable_if_safe` /
`change_role_if_safe` / `revoke_if_safe` and `count_active_owners`,
`AuditService`, `tests/api/test_organizations.py`,
`tests/api/test_last_owner_concurrency.py`,
`tests/domain/test_authorization.py`,
`tests/api/test_auth.py` (real-login flow), the Phase 21 head migration.

Traced: `active org → deactivate → get_current_membership 409 for
everyone → switch-organization 404 → (no recovery path) → …`.

Key finding on **why a reactivation route cannot use the normal auth
chain**: every organization-scoped route depends on
`get_current_membership`, which refuses an inactive organization. So the
recovery endpoint must authorize the way `AuthService.switch_organization`
already does — by resolving the caller's membership in the **target**
organization directly, not via the session's active-organization
context.

## The safety problem, precisely

Deactivation had **no invariant** at all. The catastrophic case: a **sole
Owner** deactivates → every route 409s for them and every member → and,
pre-Phase-31, nothing short of a direct database edit could restore it.

Phase 15's last-Owner invariant already guarantees an organization can
never reach **zero** active Owners (its guards hold regardless of
`is_active`), so an inactive organization always retains ≥1 active Owner.
Phase 31 adds the recovery route that lets that Owner act, **and** a
guard so the trap is not even reachable for a lone Owner.

## Decision

### Safety invariant (matches Phase 30's stated preferred direction)

> An organization may be deactivated only while it has **at least one
> other active Owner** besides the actor — i.e. **≥ 2 active Owners**
> total (an `OrganizationMembership` with `role=Owner`, `status=Active`,
> whose linked `User.status` is also `Active` — the exact definition
> Phase 15's `count_active_owners` uses).

The deactivate route is already `ORGANIZATION_MANAGE`-gated (Owner only),
so the actor is always an Owner; `≥ 2` is exactly "there is another
Owner who could reactivate this." **Consequence, deliberate:** a
**single-Owner organization cannot be deactivated at all** until a second
Owner is added. This is stricter than strict recoverability requires
(the reactivation route alone would let a sole Owner recover), but it
eliminates the "every route 409s and you must find the one recovery
endpoint" trap entirely and mirrors Phase 15's philosophy that an
org-lifecycle-critical action requires Owner redundancy. This was judged
to follow the phase brief's explicit "preferred direction" rather than a
materially different ambiguity needing a separate product decision.

### Enforcement — atomic guarded UPDATE (no read-then-write)

`OrganizationRepository.deactivate_if_safe(organization_id) -> bool`
folds the active-Owner-count subquery into the `UPDATE organizations SET
is_active = 0 WHERE id = :id AND (<active owner count>) >= 2` statement
itself, exactly like Phase 15's `change_role_if_safe`. `rowcount == 0`
→ `OrganizationService.deactivate` raises `DomainValidationError` → the
repository's established **422** (the same status Phase 15's guards
return — no new error architecture). A rejected deactivation writes
nothing (`get_db` rolls the request back); the organization is byte-for-
byte unchanged.

### Reactivation route

`POST /api/v1/organizations/{organization_id}/reactivate` →
`OrganizationRead`, `dependencies=[Depends(require_csrf)]` (state-changing
browser mutation, matching `deactivate`/`update`).

- **Authorization** is resolved in the route directly against the
  caller's own membership in the **target** organization (via
  `OrganizationMembershipRepository.get_by_user_and_org`), **not**
  `get_current_membership` / `_require_active_organization` — because a
  deactivated organization provides no active-membership context. Only an
  **active Owner membership** may reactivate.
- Not a member at all → **404** (`NotFoundError` — indistinguishable
  from a nonexistent organization; never confirm one the caller can't
  see exists, Phase 12).
- A member who is **not** an Owner → **403** (`ForbiddenError`).
- Unauthenticated → **401** (`get_current_user`); missing/invalid CSRF →
  **403**.
- `OrganizationService.reactivate` sets `is_active=True` and **nothing
  else** — it never recreates or mutates a membership, project,
  scenario, snapshot, or any other row; organization `id` and `slug`
  and every relationship are preserved. **Idempotent**: an
  already-active organization is returned unchanged (200).
- **Audit**: `AuditAction.ORGANIZATION_REACTIVATE`
  (`"organization.reactivate"`) — a new **open-vocabulary** member
  (`AuditAction` is a plain `String(100)` column, no DB CHECK), so **no
  migration**. Recorded with `organization_id` = the target org, so it
  is queryable through `GET /api/v1/audit` once the org is active again.

### Cross-organization / IDOR

Deactivation keeps its existing `_require_active_organization` guard (a
path id that isn't the caller's active org 404s). Reactivation resolves
the caller's membership in the path organization directly and 404s when
there is none — a caller can neither deactivate nor reactivate an
organization they are not an Owner of, and the response is
indistinguishable from "no such organization."

### Session / switching behavior — unchanged

Phase 31 does **not** touch `get_current_membership`,
`switch_organization`, `resolve_session`, or `list_mine`. A deactivated
organization still: denies every org-scoped request (409); is not
switchable into (404); still appears in `MeRead.organizations` /
`/organizations/mine` (a pre-existing minor wart — `list_by_ids` isn't
`is_active`-filtered — left as-is, since redesigning inactive-org
semantics is explicitly out of scope). After reactivation, the Owner's
existing session (whose `active_organization_id` still points at the
org) works again on the very next request with **no re-login**.

## Concurrency

`deactivate_if_safe`'s guard is evaluated inside its own `UPDATE`, so a
concurrent Owner-removing mutation (role change / revoke / account
disable) either commits first — in which case this `UPDATE` re-evaluates
the subquery and sees `< 2` Owners, `rowcount 0`, 422 — or commits
after, in which case its own Phase 15 guard sees the org's two Owners.
The invariant that must hold under any interleaving —
**an inactive organization always retains ≥ 1 active Owner and is always
reactivatable** — is guaranteed by Phase 15's existing zero-Owner
invariant (unchanged) plus this route.
`tests/api/test_organization_deactivation_safety.py` proves this against
a **real file-backed SQLite database with independent per-thread
connections** (mirroring `test_last_owner_concurrency.py`): concurrent
`deactivate` + `revoke`-the-other-Owner never strands the org, and two
concurrent deactivations of a 2-Owner org are both safe and the result
is reactivatable. As with Phase 15, this is single-machine SQLite
writer-serialization evidence, **not** a PostgreSQL-MVCC guarantee.

## Deactivation behavior: before vs after

| | Before (Phase 12/30) | After (Phase 31) |
|---|---|---|
| Guard | none | ≥ 2 active Owners, atomic |
| Sole-Owner deactivate | succeeds → org unusable, unrecoverable via product | **422**, org untouched |
| Recovery | none (DB edit only) | `POST .../{id}/reactivate` by any active Owner of the org |
| Cascade | none | none (unchanged) |
| Audit | `organization.deactivate` on success | unchanged; `organization.reactivate` added |
| Rejected-op state | n/a | organization byte-for-byte unchanged |

## What remains intentionally deferred to a future UI phase

- **The deactivation / reactivation UI itself** — no button, no frontend
  change in Phase 31. A future Phase 32 can consume this contract:
  deactivate shows a "requires a second Owner" state when 422, and an
  inactive-organization recovery screen calls `reactivate`.
- **Inactive organizations still listed in `MeRead.organizations`** —
  pre-existing, cosmetic, out of scope.
- Everything already deferred by ADRs 0028–0030 (org hierarchies,
  invitations, SSO/OAuth, billing, `USER_WRITE` scoping decision,
  account-directory search, PostgreSQL verification of the guarded-
  UPDATE technique, and the non-organization deferrals).

## Consequences

- **0 new tables, 0 migrations, 0 new permissions, 0 new roles, 0
  frontend changes.** Reuses `Permission.ORGANIZATION_MANAGE`
  (deactivate) and direct Owner-membership resolution (reactivate).
- `docs/openapi.json` regenerated — adds `POST .../{id}/reactivate` and
  its schema. The regen also absorbed two AI routes added in Phases 23
  and 26 whose schema was never regenerated at the time (pre-existing
  drift, now corrected).
- **Residual security risk**: a deactivated organization with exactly
  one remaining active Owner (reachable only via a concurrent
  Owner-removal that commits after a valid 2-Owner deactivation) is a
  weaker state than the guard's intent — but still fully recoverable by
  that Owner and never zero-Owner. No unrecoverable state exists.
- **Technical debt**: none introduced. The guard mirrors Phase 15's
  established pattern; the reactivation route mirrors
  `switch_organization`'s established direct-membership auth pattern.

## Confirmation

Phase 32 was **not** started. Nothing in this phase was committed.
