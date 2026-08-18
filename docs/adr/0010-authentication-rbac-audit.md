# ADR 0010: Phase 10 authentication, RBAC & audit foundation

- **Status:** Accepted
- **Date:** 2026-08-18

## Context

Phases 1–9 built CapacityOS's functionality and made the running process
itself trustworthy — but the API has no concept of "who is calling." Every
route's only dependency was `Depends(get_db)`. This was deliberate (ADR
0009, CLAUDE.md §39): authentication was explicitly deferred until the
domain, engine, and observability foundation were stable. Phase 10 is that
next phase: identity, session management, role-based authorization, and a
persistent audit trail, without touching the deterministic engine, without
multi-tenancy, and without fake/partial authentication.

## Audit findings (before any code changed)

Read in full: CLAUDE.md, all 9 prior ADRs, `docs/architecture.md`,
`docs/domain-concepts.md`, `docs/production-readiness.md`; every backend
core module (`config`, `database`, `exceptions`, `logging`,
`api/middleware.py`), `main.py`, every model, every route file, the
repository/service layering, `pyproject.toml`, `.env.example`,
`SECURITY.md`, both CI workflows; the full frontend routing/API-client/
state-management/test architecture.

**Confirmed clean slate**: zero auth-adjacent code anywhere in the backend
or frontend (grepped for `auth`, `session`, `token`, `password`,
`jwt`, `cookie`, `login`, `current_user` — every hit was either a false
positive or an explicit "no auth yet" comment). Exactly one "who did
this"-shaped field exists in the entire schema: `Scenario.created_by`, free
text, explicitly documented as deliberately not a foreign key. `Person`
already has a unique, indexed, required `email` — structurally
login-identity-ready, but Person is a planning resource, not a system
actor, and conflating them breaks the moment a login needs to exist
without a staffed Person, or vice versa.

**Route pattern**: every router file follows `def get_x_service(db: Session
= Depends(get_db)) -> XService`, called as a route-parameter default. This
is the exact seam Phase 10 uses — `current_user`/permission checks are
additional `Depends()` parameters on the same factories, not a rewrite.

**Frontend**: one HTTP chokepoint (`apps/web/src/api/client.ts`), one
centralized error handler, TanStack Query for all server state, no route
guards, no login route, no global auth-shaped state.

## Decisions

### B. Authentication architecture

**Opaque server-side session token in an httpOnly, Secure, SameSite=Lax
cookie — not JWT, not an external identity provider.**

| Option | Verdict |
|---|---|
| Session cookie (chosen) | Fully revocable (delete the DB row), the token never touches JS-accessible storage, no new crypto/JWT dependency — the token is `secrets.token_urlsafe(32)`, only its SHA-256 hash is ever persisted. |
| JWT access/refresh | Rejected — real revocation still needs a blocklist or short-lived-access/rotating-refresh complexity, for a problem the session-cookie approach solves more simply. Would need a new dependency for no corresponding benefit here. |
| External IdP (Auth0/Clerk/Cognito/OIDC) | Not proposed — this is the CLAUDE.md §33/§34 "STOP and get approval" case (external service, data leaves CapacityOS, vendor lock-in, cost). A self-hosted option is clearly sufficient for this phase. |

Password hashing: **argon2-cffi (Argon2id)**, not passlib (maintenance-only
since 2020) — actively maintained, prebuilt wheels, no wrapper needed.

**No `SESSION_SECRET_KEY` exists anywhere.** Tokens are random opaque
values compared by hash, never signed/encrypted — one fewer secret to
provision, rotate, or leak.

**Cross-origin note**: `localhost:5173` → `localhost:8000` are same-site
(SameSite cares about scheme+registrable-domain, not port), so
`SameSite=Lax` works in dev without `SameSite=None`. Production is expected
to share a registrable domain between frontend/backend; a genuinely
cross-domain deployment would need `SameSite=None; Secure` plus stronger
CSRF handling — documented as a future need, not built.

**CSRF**: primary defense is architectural (JSON-only routes + the
existing CORS allowlist + SameSite=Lax already blocking the cookie from
cross-site subresource requests). A double-submit token
(`capacityos_csrf`, non-httpOnly, echoed back as `X-CSRF-Token`) is added
as defense-in-depth on every mutating route. It is a **separate** random
value from the session token (`UserSession.csrf_token_hash`), never
derived from it — reusing the session token's value for a JS-readable
cookie would hand any XSS payload the means to impersonate the session,
defeating the point of the session cookie being httpOnly.

**`session_cookie_secure` is a computed property (`environment ==
"production"`), not a settable field.** No insecure-by-omission default
exists for an operator to forget to flip.

### C. Authorization model

Five roles, matching CLAUDE.md's own suggested set. `app/domain/
authorization.py` (pure, DB-free, unit-tested like every other domain
module) defines `Permission` and a static `ROLE_PERMISSIONS` table —
routes declare `Depends(require_permission(Permission.X))`, never `if
user.role == "admin"`.

| Role | Grants |
|---|---|
| Viewer | Read every operational entity + AI (advisory, never mutates). |
| Member | Viewer + `export.use`. |
| Manager | Member + write/delete on every operational entity + `import.use`. |
| Admin | Manager + `user.read`/`user.write` + `audit.read`. |
| Owner | Same permission SET as Admin — the distinction is procedural (see below), not an extra permission. |

Every role gets every `*.read` permission on operational entities — reads
are gated on "authenticated," not role, today. `user.read`/`audit.read`
are the exception (Admin/Owner only). This is a deliberate seam: routes
already declare a permission dependency, so differentiating read access
later is a table edit, not a route rewrite.

**401 vs 403**: `get_current_user` (no/invalid/expired session) → 401.
`require_permission` (valid session, insufficient role) → 403, and records
a `permission.denied` audit event before raising.

### D. Resource-level authorization — scope decision

Phase 10 implements **type-level** authorization only (role → permission
on an entity TYPE). No instance-level scoping ("only your own team," "only
your own scenario") — there is no Organization/tenant or team-ownership
model yet to make that meaningful. `has_permission`/`require_permission`
accept an optional `resource` parameter, unused today — a forward-compat
seam, not a built feature. `Scenario.created_by` stays exactly as it was
(free text, untouched) — not repurposed into a real FK this phase.

### E. Audit architecture

Three distinct things, not conflated: **operational logs** (Phase 9's
structured JSON, unchanged), **security logs** (login success/failure/
lockout/logout to the existing structured logger, `capacityos.security`),
and **persistent audit events** (the new `audit_events` table).

`AuditEvent`: `timestamp`, `actor_user_id` (nullable — a login failure
against an unknown email has none), `actor_email` (a denormalized
snapshot, so a record stays readable after the actor is renamed/
deactivated), `action` (an open `AuditAction` StrEnum, ~35 members
following one `{entity}.{verb}` pattern — deliberately NOT DB-CHECK-
constrained, matching `AvailabilityType`'s precedent, since new audited
actions are a pure code change), `resource_type`/`resource_id`,
`outcome` (`success`/`failure`/`denied` — DB-CHECK-constrained, a small
fixed vocabulary), `request_id` (ties a row to Phase 9's structured log
lines), `event_metadata` (JSON, deliberately minimal per action type —
never a raw request body, uploaded file, AI prompt, password, or token).

**Append-only by construction**, not a DB trigger: no service method
updates or deletes a row; `GET /api/v1/audit` (Admin/Owner only) is the
only route touching the table. A DB-level immutability trigger was
considered and rejected — not portable cleanly across SQLite/PostgreSQL,
and not needed to meet this phase's actual requirement (documented as a
known limitation: a database superuser could still alter rows directly,
the same trust boundary every other table already has).

**Recorded at the route layer, one line per mutating route** — not a
generic response-inspecting interceptor. This is what keeps every
existing Phase 1–9 service method's signature completely unchanged.

#### The audit-commit design took three iterations, all caught by real testing

1. **First**: `AuditService.record()` committed the request-scoped `db`
   session directly. Broke immediately: SQLAlchemy's default
   `expire_on_commit=True` expired every ORM object already mutated
   earlier in the same request, so a subsequent re-read of e.g. a
   `Decimal` field silently reflected the database's stored
   representation ("4.00" instead of the "4" the route just set). Caught
   by the full backend regression suite (`test_working_schedules.py`,
   `test_allocations.py`, `test_availability_exceptions.py`).
2. **Second**: gave `AuditService` its own independent database session/
   connection, specifically to avoid touching `db`'s identity map. This
   fixed the expiry problem but broke logins and every permission denial
   against a real, file-backed SQLite database (never against the test
   suite's in-memory one): SQLite allows only one writer at a time, and by
   the point almost every audit call happens, `db` already holds an open,
   uncommitted write of its own (the mutation being audited, or
   `AuthService.login`'s `failed_login_count` increment). A second
   connection's write blocks against that open transaction until SQLite's
   `busy_timeout` gives up with `database is locked` — a structural
   deadlock (that transaction can't release until the request finishes,
   which is waiting on the audit write), not transient contention. This
   was caught only by manually running a real server against a real
   database file — the test suite's `StaticPool` in-memory SQLite shares
   one physical connection across every session, so it cannot reproduce
   cross-connection lock contention at all.
3. **Final**: `AuditService` uses the SAME `db` session (one writer, no
   deadlock possible), and `record()` temporarily sets
   `session.expire_on_commit = False` around just its own `commit()` call,
   restoring it in a `finally`. This gets both properties at once: no
   second writer, and no stale re-read of anything the route already
   mutated.

A secondary, unrelated SQLite fix landed alongside this: `app/core/
database.py` now sets `PRAGMA journal_mode=WAL` and `PRAGMA
busy_timeout=5000` on every SQLite connection (a no-op on `:memory:`,
where the test suite runs) — standard practice for any concurrent SQLite
access, and independently useful given ADR 0009 already documents SQLite's
single-writer limitation.

**Import/export**: `imports.py::apply_import` records one `import.apply`
event with `entity_type`, `mode`, and result counts — never file content,
closing the "no audit trail" limitation ADR 0006 flagged.

### F. Data model

Three new tables (`users`, `sessions`, `audit_events`), all UUID-PK, one
migration (`332ca8583f5f`, chained after `e79054e949ad`).

- **`users`**: `email` (the LOGIN identity, independent of `Person.email`),
  `password_hash`, `display_name`, `status` (`active`/`invited`/
  `disabled`), `role`, `person_id` (nullable, unique-when-not-null FK →
  `people.id`, `ON DELETE SET NULL`), `failed_login_count`,
  `locked_until`, `last_login_at`.
- **`sessions`**: `user_id`, `token_hash` (SHA-256 of the raw cookie
  value), `csrf_token_hash` (a SEPARATE random value — see the CSRF
  decision above), `expires_at` (fixed absolute TTL from login,
  `SESSION_TTL_HOURS`, default 24 — deliberately no silent sliding
  renewal), `last_seen_at` (written at most once per 5 minutes per
  session, to avoid a write on every authenticated request).
- **`audit_events`**: as described in E.

`Person` is untouched — no auth fields added. `User → Person` is a
nullable one-to-one, not the reverse: a User can exist before being linked
to a Person, a Person can exist with no login (a contractor tracked for
capacity only), and a future service/integration identity can be a User
with no Person — none of which fit if these were merged.

`UserRead.permissions` (computed by `app/schemas/user.py::user_to_read`
from `ROLE_PERMISSIONS[user.role]`, never stored) is the one field
explicitly designed for frontend consumption — the backend remains the
authorization boundary regardless (every route independently re-checks
`require_permission`), but the frontend gates UI affordances from this one
authoritative list instead of hand-maintaining a second copy of the role/
permission table in TypeScript, which would drift.

### G. Threat model (condensed)

| Threat | Mitigation |
|---|---|
| Session/token theft (XSS) | httpOnly cookie — never reachable from page JS. |
| CSRF | SameSite=Lax + JSON-only routes + CORS allowlist + double-submit token. |
| Credential stuffing / brute force | Per-account lockout: 5 failed attempts → 15 min lock, DB-backed so it holds across multiple API instances. No distributed IP-based rate limiting — a real, documented limitation (would need shared infra this deployment doesn't have), not claimed as enterprise-grade. |
| Enumeration | Login returns the identical generic message for unknown-email, wrong-password, and locked-account; a dummy Argon2 verify runs even when the email doesn't match anything, so response timing doesn't leak existence either — verified in `tests/api/test_auth.py`. |
| Privilege escalation | `UserService.change_role` requires `user.write` (route-level) AND `acting_user.role == OWNER` to touch an Owner/Admin role; every change is audited with old/new role; the system refuses to demote or disable the last active Owner. |
| IDOR | No per-instance ownership exists yet to bypass (see D) — the residual risk is a *missing* permission check on a route, mitigated by adding one to literally every existing mutating/sensitive route and verifying with an explicit role-matrix test suite (`tests/api/test_rbac.py`), not spot checks. |
| Audit tampering | No update/delete path exists for `AuditEvent` at the service/API layer. |
| Secret/token leakage in logs | Password, raw session token, and CSRF token join the existing Phase 9 "never logged" list. |
| Session fixation | A fresh token is issued on every successful login — never reused. |

## Consequences

- 3 new tables, 1 migration, 0 changes to any Phase 1–9 table.
- New backend modules: `app/models/{user,session,audit_event}.py`,
  `app/domain/authorization.py`, `app/core/security.py`, `app/api/deps.py`,
  `app/api/v1/{auth,users,audit}.py`, `app/repositories/{user,session,
  audit_event}.py`, `app/services/{auth,user,audit}.py`,
  `app/schemas/{user,auth,audit}.py`. Extended: `app/core/exceptions.py`
  (+`UnauthenticatedError`/`ForbiddenError` and their handlers),
  `app/core/config.py` (+`session_ttl_hours`, +`session_cookie_name`,
  +`session_cookie_secure`), `app/core/database.py` (+SQLite WAL pragma),
  `app/models/base.py` (+`as_utc` — SQLite doesn't preserve tzinfo across a
  write/read round-trip, unlike PostgreSQL; a real bug caught by
  `tests/api/test_auth.py`'s session-expiry test), every existing route
  file (+auth/permission dependencies, +one audit call per mutation).
- New frontend module: `apps/web/src/features/auth/` (types, API client,
  `AuthContext`/`AuthProvider`/`useAuth`, `LoginPage`, `UserMenu`,
  `ViewOnlyNotice`); `api/client.ts` (+`credentials: 'include'`, +CSRF
  header injection, +centralized 401 handling); `app/routes.tsx` (+`/login`
  route, +`RequireAuth` wrapper); `AppShell.tsx` (+user menu/logout,
  +role-gated nav); write-affordance gating in `ScenarioListPage`,
  `SkillsOverviewPage`, `ImportExportPage`.
- 1 new backend dependency: `argon2-cffi`. 0 new frontend dependencies.
- Bootstrap: `scripts/create_first_owner.py` — operator-run, refuses to
  run if an Owner already exists, never a hardcoded credential.
- Backend: +56 tests across `tests/domain/test_authorization.py`,
  `tests/core/test_security.py`, `tests/api/{test_auth,test_rbac,
  test_users,test_audit}.py`, 541 total, all passing — the full pre-Phase-
  10 suite (485 tests) passes unmodified via a new `authed_client`-style
  fixture pattern in `tests/conftest.py` (a role-parameterized `client_as`
  factory; the plain `client` fixture now resolves to `client_as(OWNER)`,
  so no pre-existing test needed to change). Frontend: +19 tests across
  `features/auth/`, `components/layout/RequireAuth.test.tsx`,
  `api/client.test.ts`, plus updates to `App.test.tsx`,
  `ScenarioListPage.test.tsx`, and `ImportExportPage.test.tsx` (both
  needed a permissive `useAuth` mock once those pages started calling
  `can()`).
- **Known, deliberate UI-gating limitation**: only the most prominent
  write entry point on each write-capable page is gated by `can()`
  (scenario creation, skill creation, the whole import/export card) —
  nested detail edits (e.g. `PersonSkillsPanel`, per-row skill-requirement
  editing) are not individually gated at the UI layer yet. The backend
  independently enforces every one of these regardless; this is a UX
  completeness gap, not a security gap.
- **Deferred, matching the phase boundary**: multi-tenancy, instance-level
  resource authorization, OIDC/external IdP integration, service-account
  identities, distributed rate limiting, DB-level audit-immutability
  triggers, sliding session renewal, converting `Scenario.created_by` into
  a real actor FK.
