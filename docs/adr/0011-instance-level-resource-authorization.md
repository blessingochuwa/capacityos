# ADR 0011: Phase 11 instance-level resource authorization

- **Status:** Accepted
- **Date:** 2026-08-19

## Context

Phase 10 gave CapacityOS type-level RBAC: `has_permission(role, permission)`
only ever asks "does this role hold this permission," never "is this the
specific instance this user is trusted with." That gap was deliberate and
documented (ADR 0010 §D, §Consequences) — there was no ownership/access
model yet to make instance-scoping meaningful, and `has_permission`'s
`resource` parameter was left accepted-but-unused as an explicit
forward-compat seam for exactly this phase.

Concretely, before this phase: `PATCH /projects/{id}` succeeded for *any*
Manager, regardless of whether they had ever touched that project before.
Phase 11 closes that gap.

## Audit findings (before any code changed)

Read in full: `app/domain/authorization.py`, `app/api/deps.py`, `app/core/
database.py`, `app/models/base.py`, `app/models/team_membership.py`,
`app/models/enums.py`, `app/schemas/allocation.py`; every model relationship,
every one of ~70 routes across 16 router files, the repository/service
layering, the Alembic migration chain, and the existing RBAC test suite;
the frontend `AuthContext`, `RequireAuth`, `client.ts`'s 401/403 handling,
and every existing role-gated UI affordance.

**No explicit User↔Team or User↔Project access relationship existed.**
`Project` has no FK to `Team` at all. `TeamMembership` links `Person↔Team`,
not `User↔Team`. `Allocation` is the only table joining `Person` and
`Project`. There was nothing safe to derive instance-level scope from — an
explicit new grant model was required (CLAUDE.md's own instruction: don't
infer authorization from unrelated business relationships like Person↔Team
membership).

**Every route's authorization was exactly `Depends(require_permission
(Permission.X))`** — a pure role/type check, zero resource-instance checks
anywhere. `AuditEvent` already had `resource_type`/`resource_id` fields, so
no schema change was needed to record resource-scoped denials/grants.

## Decisions

### Resource-access model

Two new tables, `team_access_grants` and `project_access_grants`, each an
explicit `(user_id, resource_id)` grant row with a unique constraint,
mirroring `TeamMembership`'s shape (`UUIDPrimaryKeyMixin`, `created_at`
only — a grant is added or removed, not edited in place). A `Manager` is
authorized to write/delete a specific Team/Project only if a matching grant
row exists for them; `Owner`/`Admin` bypass this check unconditionally
(their authority is role-based, not grant-based — unchanged from Phase 10);
`Member`/`Viewer` never reach the check at all, since they hold no
`team.write`/`project.write`/etc. permission to begin with.

Grants attach to **User**, not Person — it's the authenticated User who
performs the action being authorized, and Phase 10 already established
User↔Person as a deliberately separate, optional link. A `granted_by_
user_id` (nullable, `ON DELETE SET NULL`) records who created the grant
directly on the row, in addition to the append-only audit trail.

**Revocation is a hard delete of the grant row.** A grant is a pure
access-control record, not a business entity with retained history value —
the audit trail (`access_grant.create`/`access_grant.revoke`, both with
`resource_id` populated) is what preserves history, not the grants table.

### Manager read access stays global

Only mutating actions (create/update/delete) on Team and Project become
scoped. Reads (`GET`) are unaffected for every role, including Manager —
the same as Member/Viewer today. Three reasons:

1. It matches the concrete threat this phase actually names: `PUT /projects/2`
   succeeding for any Manager. The threat is unauthorized *mutation*, not
   visibility.
2. CapacityOS is explicitly a single-org internal tool (CLAUDE.md §3's
   "systems thinking, not isolated individual utilization") — broad
   cross-team read visibility supports that; narrow write authority is the
   actual sensitive boundary.
3. Scoping Manager reads while leaving Member/Viewer reads global would be a
   role-ordering inversion (a "higher" role seeing *less* than a "lower"
   one) worth a much larger, more deliberate design than this phase's scope
   — and it was not requested.

This decision is also what keeps 401/403/404 semantics simple (see below).

### No Team→Project inheritance

`Project` has no FK to `Team` in the existing schema, and adding one is a
domain-model change beyond an authorization phase's scope. Team-grants and
Project-grants are two fully independent axes: granting Team access never
implies Project access, and vice versa. This is the simplest model
consistent with the existing domain, and avoids silently creating broad
transitive access a security reviewer wouldn't expect.

### Which resources are scoped, and which are deliberately deferred

Only resources with an unambiguous, directly-stored FK to Team or Project
are instance-scoped:

- **Team-scoped** (resolved via the `team_id` path parameter): `Team`
  update/delete; `TeamMembership` add/remove.
- **Project-scoped**: `Project` update/delete; `ProjectSkillRequirement`
  add/update/remove (resolved via the `project_id` path parameter);
  `Allocation` create (resolved from `project_id` in the request body) and
  update/delete (resolved from the *existing* row's `project_id` —
  `AllocationUpdate` has no `project_id` field, confirmed by reading the
  schema, so an allocation can never be re-pointed to a different project
  as an authorization-bypass vector).

**Explicitly NOT scoped in this phase** (role-only, unchanged from Phase
10): `Person`, `WorkingSchedule`, `AvailabilityException`, `PersonSkill` —
all key off `Person`, which has an ambiguous *many-to-many* relationship to
Team via `TeamMembership`, with no single unambiguous parent to derive
scope from without inventing a derived-authorization chain not backed by a
stored grant (exactly the "don't infer from unrelated relationships"
warning this phase's own brief raised). Also unscoped: `Skill` (a global
catalog, not owned by any Team/Project), `Scenario` (no Team/Project FK
exists — `Scenario.created_by` is free text, already flagged in ADR 0010 as
a deferred future actor-FK conversion), imports/exports, AI, insights,
capacity reads. Each is a deliberate, documented deferral, not an
oversight — a future phase can add a `PersonAccessGrant` or similar if
Person-level scoping is ever required, once there's a real, unambiguous
ownership model to key it on.

### Authorization API: `ResourceScope`, not a parallel mechanism

`has_permission`'s Phase-10-unused `resource` parameter is now real, but
`app/domain/authorization.py` stays pure/DB-free (its Phase 10 invariant):

```python
@dataclass(frozen=True)
class ResourceScope:
    granted: bool

def has_permission(role, permission, resource: ResourceScope | None = None) -> bool:
    if permission not in ROLE_PERMISSIONS[role]:
        return False
    if resource is None:
        return True
    if role in (UserRole.OWNER, UserRole.ADMIN):
        return True
    return resource.granted
```

The caller — `AccessGrantService.enforce_team_access`/`enforce_project_
access` — resolves the DB-backed grant lookup *before* calling
`has_permission`, so all I/O stays outside the pure domain module. This one
service method is the single call site every authorization path goes
through: two new FastAPI dependency factories in `app/api/deps.py`
(`require_team_access`/`require_project_access`, drop-in replacements for
`require_permission` on routes with a `team_id`/`project_id` path param —
`require_permission` runs first as the inner dependency, so Member/Viewer
are denied by the existing type check and never reach the grant query at
all) for path-resolved resources, and one inline call in
`app/api/v1/allocations.py`'s create/update/delete handlers for the
body/existing-row-resolved case. The *decision logic* is never
reimplemented per route; only the *invocation site* differs.

### Access-grant management: Owner/Admin only

A new `Permission.ACCESS_MANAGE`, granted to nobody but Owner/Admin in
`ROLE_PERMISSIONS`, gates a new small router
(`app/api/v1/access_grants.py`): `GET/POST /api/v1/teams/{id}/access-grants`,
`DELETE .../access-grants/{user_id}`, and the Project equivalents. This
makes self-escalation structurally impossible — a Manager's grant/revoke
request 403s at the type-level permission check before any resource logic
runs, with no delegation hierarchy needed. Verified with an explicit test
(`tests/api/test_access_grants.py::test_manager_cannot_grant_themselves_
team_access`) that also confirms a *subsequent* write attempt by that same
Manager is still 403 afterward — proving the escalation attempt had no
effect end-to-end, not just that the grant request itself was rejected.

### 401 / 403 / 404 semantics: unchanged contract

`401` (no/invalid session), `403` (authenticated, insufficient
type-level or instance-level authority), `404` (resource genuinely doesn't
exist, checked before the resource-scope check runs) — exactly Phase 10's
existing contract, extended rather than changed. **403, not a disguised
404, for an existing-but-unauthorized Team/Project**: since reads stay
global, every authenticated user can already see via `GET` that the
resource exists — a fake 404 on the write path would be security theater,
not real enumeration protection, given the resource's existence is never
actually hidden.

### Audit integration

Two new `AuditAction` members (an open, non-DB-constrained `StrEnum` — a
pure code change, matching `AuditAction`'s Phase 10 design): `resource_
access.denied` (fired by `AccessGrantService`'s enforce methods, always
carrying `resource_id` — unlike Phase 10's `permission.denied`, which never
knows a specific instance) and `access_grant.create`/`access_grant.revoke`
(fired by the grant-management routes, with `metadata={"target_user_id":
...}` only — never an email, never a role, keeping the same minimal-
metadata discipline Phase 10 established).

## Threat model additions

| Threat | Mitigation |
|---|---|
| IDOR — Manager acts on a resource they were never granted | Every scoped mutating route resolves and checks the *specific* resource id, not just the permission type; verified by an explicit cross-resource test in each of `test_team_access_scope.py`, `test_project_access_scope.py`, and `test_allocations.py` ("granted Team/Project A, still denied on B/cross-project"). |
| Privilege escalation via self-grant | `Permission.ACCESS_MANAGE` is never held by Manager — structurally impossible, not merely checked at runtime. |
| Owner/Admin accidentally becoming grant-dependent | Regression tests assert Owner/Admin can act on a resource with **zero** grant rows ever created for it. |
| Concurrent grant race (duplicate grant, or a grant/revoke/grant sequence deadlocking against a real file) | `tests/api/test_access_grant_concurrency.py` drives genuinely concurrent threads against a real file-backed SQLite database (not the shared in-memory test fixture) — exactly the class of bug Phase 10's `AuditService` deadlock was only caught by manual testing against a live server, not the in-memory suite. |
| Audit tampering of the new event types | Same append-only guarantee as every other `AuditEvent` — no update/delete path exists at the service or API layer. |

## Concurrency

The unique constraint on `(user_id, team_id)`/`(user_id, project_id)` is
the actual correctness guarantee under concurrent grant attempts — SQLite's
`PRAGMA busy_timeout` (already set for every SQLite connection since Phase
10) absorbs write contention rather than failing immediately, and the
constraint ensures exactly one concurrent grant attempt wins, the rest
observing either the service-layer `ConflictError` (pre-check) or a raw
`IntegrityError` (a genuine race where two requests both pass the pre-check
before either commits) — both are treated as "did not create a duplicate"
by the test suite, and the global `IntegrityError` handler already converts
the latter to a client-facing 409 at the API layer. Verified against a real
file-backed database with genuinely independent connections per thread, not
the in-memory `StaticPool` fixture used everywhere else in this suite,
which shares one physical connection and structurally cannot reproduce
cross-connection contention.

## Frontend

`CurrentUser` gains `accessible_team_ids`/`accessible_project_ids` (backend:
`UserRead`, populated only by `/auth/login` and `GET /auth/me` — every
other place a `User` is serialized, e.g. the admin user-list endpoints,
leaves them empty deliberately, since those responses describe *other*
users, not "my own" access scope). `AuthContext` gains `canManageResource
(resourceType, resourceId)`, mirroring the backend's two-layer check
exactly: Owner/Admin always true, everyone else needs both the underlying
`can('team.write'|'project.write')` *and* the id present in their
accessible-ids list. Still UX-only — the backend re-checks independently on
every request regardless of what this returns (CLAUDE.md §21).

A new `features/access/` directory (following the existing `features/*`
convention) provides the grant-management admin surface — genuinely new UI,
since no Team/Project write affordance existed anywhere in the frontend
before this phase to retrofit. Mounted at `/admin/access`, gated on
`can('access.manage')` both for the nav link (hidden, not disabled) and a
defense-in-depth `ViewOnlyNotice` render if navigated to directly. No
changes were needed to `api/client.ts` — a resource-scope 403 already falls
through to the same generic `ApiError` path a type-level 403 does, which is
the correct behavior for both.

## Future multi-tenancy seam

This model composes cleanly under a future `Organization` layer without
rework: grants are already resource-instance-keyed (not global), so an
`Organization → Membership → User → Person` hierarchy (the seam ADR 0010
already described) would sit *above* this phase's grants unchanged — a
future tenant-isolation check would filter which Teams/Projects a request
can even resolve to, and this phase's grant check would still apply
identically within that filtered set.

## Consequences

- 2 new tables, 1 migration (`69270a626bfc`, chained after Phase 10's
  `332ca8583f5f`), 0 changes to any existing table.
- New backend modules: `app/models/{team_access_grant,project_access_
  grant}.py`, `app/repositories/{team_access_grant,project_access_grant}.py`,
  `app/services/access_grant.py`, `app/schemas/access_grant.py`,
  `app/api/v1/access_grants.py`. Extended: `app/domain/authorization.py`
  (`ResourceScope`, `Permission.ACCESS_MANAGE`), `app/models/enums.py`
  (+3 `AuditAction` members), `app/models/__init__.py`, `app/api/deps.py`
  (+`get_access_grant_service`, +`require_team_access`, +`require_project_
  access`), `app/api/v1/{teams,projects}.py` (one-line dependency swaps on
  the mutating routes each), `app/api/v1/allocations.py` (inline
  `enforce_project_access` calls), `app/api/v1/auth.py` and `app/schemas/
  user.py` (`accessible_*_ids`), `app/main.py` (mount the new router).
- New frontend module: `apps/web/src/features/access/` (types, api, hooks,
  components, views). Extended: `features/auth/types/auth.ts`,
  `features/auth/context/AuthContext.tsx` (`canManageResource`),
  `app/routes.tsx` (+`/admin/access`), `components/layout/AppShell.tsx`
  (+nav link).
- 0 new backend or frontend dependencies.
- Backend: 615 tests total, all passing (up from 583 before this phase) —
  new coverage across `tests/domain/test_authorization.py` (ResourceScope
  cases replacing the Phase 10 no-op test), `tests/models/test_{team,
  project}_access_grant.py`, `tests/services/test_access_grant.py`,
  `tests/api/test_{team,project}_access_scope.py`,
  `tests/api/test_access_grants.py`, `tests/api/test_access_grant_flow.py`
  (end-to-end integration flow with audit-trail assertion),
  `tests/api/test_access_grant_concurrency.py` (real file-backed SQLite),
  plus extensions to `tests/api/test_allocations.py` and `tests/api/
  test_audit.py`. `ruff check` and `pyright` both clean. Frontend: 140
  tests total, all passing (up from 130) — new coverage in
  `features/access/components/TeamAccessSection.test.tsx`,
  `features/access/views/AccessManagementPage.test.tsx`, and extensions to
  `features/auth/context/AuthContext.test.tsx` for `canManageResource`.
  `tsc -b`, `oxlint`, and `vite build` all clean (the two pre-existing
  `only-export-components` warnings in `AuthContext.tsx` predate this
  phase and are unrelated to it).
- Live-verified against a real file-backed SQLite server (not just tests):
  login, Manager read-without-grant (200), Manager write-without-grant
  (403), grant (201), immediate write success (200), revoke (204),
  immediate write denial again (403), the full ordered audit trail via
  `GET /api/v1/audit`, no secrets in server logs, `GET /auth/me` reflecting
  the live grant state, a privilege-escalation attempt (403), and a
  cross-team IDOR attempt (403). Browser/UI verification was **not**
  performed — no browser-automation tooling was available in this
  environment; this is stated explicitly rather than claimed.
- **Deferred, matching the phase boundary**: Person/WorkingSchedule/
  AvailabilityException/PersonSkill instance-scoping, Scenario
  instance-scoping (blocked on the same `Scenario.created_by` real-actor-FK
  conversion ADR 0010 already deferred), Team→Project inheritance,
  multi-tenancy/Organization, external identity providers, a general-
  purpose policy engine, distributed authorization infrastructure.
