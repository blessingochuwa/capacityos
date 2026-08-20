# ADR 0012: Phase 12 organizations & multi-tenancy

- **Status:** Accepted
- **Date:** 2026-08-20

## Context

Every phase through Phase 11 assumed a single implicit tenant. Phase 11's
own "Future multi-tenancy seam" section named this gap explicitly: instance-
level grants compose cleanly under a future `Organization` layer, but that
layer didn't exist — any authenticated user with the right role/grant could
act on *any* Team/Project in the entire database, because there was only
one organization, unstated. Phase 12's mandate: **a user must never be able
to read, modify, export, infer, or otherwise interact with data belonging
to an organization they are not authorized to access** — across URL
manipulation, object ids, API parameters, imports, exports, scenarios,
skills, insights, AI, audit queries, and access-grant manipulation.

## Audit findings (before any code changed)

Confirmed by full-file audit of every model, repository, and service: zero
organization concept anywhere, no query filtered on anything tenant-like.
Global-unique fields needing to become organization-scoped-unique:
`Person.email`, `Team.name`, `Skill.name`, `Project.external_id`,
`Allocation.external_id`, `WorkingSchedule.external_id`,
`AvailabilityException.external_id`. The "≥1 active Owner" invariant lived
in exactly two places in `UserService`, both guarded by a fully unscoped
`SELECT COUNT(*) WHERE role='owner'`. Highest cross-tenant leak risk,
ranked: `ExportService._collect_rows` (4 of 10 entity types called
`.list()` unconditionally; every optional-filter-omitted branch on the
other 6 silently fell back to the same unscoped call — designed to dump
full tables); `ScenarioService`'s existence-only checks (`.get(id)`, zero
ownership validation — a scenario operation could reference any
organization's person/project/allocation with no error); `ImportService`'s
identity-resolution lookups (a crafted row could silently match and mutate
another organization's row); `insight_service.py`/`skill_capacity.py`'s
`list_for_skills(skill_ids)`, explicitly documented at the time as
intentionally "ORG-WIDE" meaning globally unscoped.

## Decisions

### `Organization` is the tenant root

`id`, `name`, `slug` (unique, stable, immutable-once-set identifier),
`is_active` (soft-delete only — never hard-deleted, matching `Skill.
is_active`'s precedent), timestamps.

### Role moves off `User` onto a new `OrganizationMembership`

The single biggest structural decision. `User.email` stays the globally
unique LOGIN identity (one account, no duplicate logins to join a second
organization); `role` cannot stay a scalar on `User` once one person can be
Owner in Org A and Viewer in Org B. `OrganizationMembership`: `user_id`/
`organization_id` (both `ON DELETE CASCADE`), `role` (reuses `UserRole`
verbatim — no new vocabulary), `status` (new `MembershipStatus`: `active`/
`revoked`, independent of `User.status` — a membership can be revoked
without disabling the account, which may still belong to other
organizations), `UniqueConstraint(user_id, organization_id)`.

Ripple: `UserCreate.role` removed — creating an account implies no role
anywhere until an explicit membership grants one. `UserRead` loses `role`/
`permissions`/`accessible_*_ids` (not meaningful for an account outside
organization context); a new `MeRead` (for `/auth/login`, `/auth/me`,
`/auth/switch-organization`) carries those, computed from the *resolved
active membership*. `PATCH /users/{id}/role` relocates to
`PATCH /organizations/{org_id}/memberships/{user_id}/role`.
`UserRepository.count_by_role` is replaced by
`OrganizationMembershipRepository.count_active_owners(organization_id)` —
the last-Owner invariant is now per-organization, enforced in
`OrganizationMembershipService`, not `UserService`. `GET /users` stays
deliberately organization-*unscoped* — the access-grant admin UI's "invite
an existing user" flow needs to find any account by email, not just the
acting organization's; `UserService.create`/`update` still take
`organization_id` solely to validate an optional `person_id` link, since
`Person` itself became organization-scoped.

One known gap, called out rather than silently accepted: Phase 10's
"can't disable the last remaining Owner's account" check had no
straightforward per-organization equivalent once role moved off `User` —
a user can now be Owner of multiple organizations, so a single
account-level check no longer has one invariant to enforce. This was not
re-implemented (it would require `UserService` to depend on
`OrganizationMembershipRepository` across a boundary this phase otherwise
keeps clean, for a case outside the phase's explicit multi-tenancy
mandate); the now-obsolete test was removed rather than adapted. A future
phase should decide whether "disabling an account that holds the last
active Owner membership anywhere" needs its own guard.

### Active organization lives on `UserSession`, re-verified every request

`UserSession.active_organization_id` (nullable FK, `ON DELETE SET NULL`) —
never a cookie/query-param/body value trusted as proof of membership on its
own. `AuthService.login`: after password verification, exactly one active
membership auto-selects it; zero or many leave it `NULL` (the frontend
gates on that state rather than the backend guessing). New
`POST /api/v1/auth/switch-organization` re-verifies an active membership
row for `(user, target_org)` **and** `Organization.is_active` before
updating the session, raising `NotFoundError` (not `ForbiddenError`) on
failure — indistinguishable from "that organization doesn't exist," so the
endpoint can't be used to enumerate organizations the caller doesn't belong
to. New `app/api/deps.py::get_current_membership` re-resolves and
re-verifies membership status + organization active on **every request**,
not cached from login/switch time — this is what makes "select Org A →
revoke membership → next request → denied" work without a logout. New
`NoActiveOrganizationError` (409) — distinct from 401 (`get_current_user`
already ruled that out) and 403 (the caller has an organization but the
wrong role).

### Direct `organization_id` denormalization, not indirect joins

13 tables get a direct `organization_id` (`NOT NULL`, indexed, `FK ondelete
=RESTRICT`): `Person`, `Team`, `TeamMembership`, `Project`, `Allocation`,
`WorkingSchedule`, `AvailabilityException`, `Skill`, `PersonSkill`,
`ProjectSkillRequirement`, `Scenario`, `TeamAccessGrant`,
`ProjectAccessGrant`. `RESTRICT` not `CASCADE`: organizations are
soft-deleted, never hard-deleted, but `RESTRICT` protects against ever
silently cascading away an entire tenant's data if hard-delete is added
later. **Not** denormalized onto `WorkingScheduleEntry`/`ScenarioOperation`
— leaf-of-leaf rows always accessed only through their already-scoped
parent, never queried independently. `AuditEvent.organization_id` is the
one exception to `NOT NULL`: nullable, `ON DELETE SET NULL` — a
pre-organization-context event (an unknown-email login failure)
legitimately has none, and the audit trail must outlive the organization it
references.

### Repository-layer enforcement by direct signature override

Each of the 13 repositories overrides `get`/`list` (and every narrow method
— `get_by_email`, `list_for_people`, etc.) with a required `organization_id`
parameter, deliberately shadowing `BaseRepository`'s unscoped signatures —
every pre-Phase-12 call site becomes a Pyright strict type error, not a
silent runtime leak. The plan originally specified a generic
`OrganizationScopedRepository[ModelT]` base with a Protocol-bound
`organization_id` accessor; this was deliberately **not** built — verifying
Pyright strict's interaction between a generic Protocol base and
SQLAlchemy's `Mapped` columns was assessed as too risky to get right
without extensive empirical iteration, for a benefit (less per-file
boilerplate) that direct overriding already achieves the actual goal of.
Each override carries a `# pyright: ignore[reportIncompatibleMethodOverride]`
— a deliberate, documented simplification, not an oversight.

One concrete gap this uncovered and fixed: `TeamMembershipRepository`,
`PersonSkillRepository`, `ProjectSkillRequirementRepository`,
`WorkingScheduleRepository`, and `AvailabilityExceptionRepository` had org-
scoped `get()`/narrow methods but had never gained an org-scoped `list()`
override — their inherited `BaseRepository.list()` stayed fully unscoped.
`ExportService`'s "no filter given" fallback branches called exactly this
unscoped `list()` for several entity types. Closed by adding the missing
`list()` overrides (delegating to `list_filtered` where one already
existed, matching `SkillRepository`'s existing pattern) before hardening
`ExportService` itself — fixing the root cause, not just the one call site
that happened to expose it.

### 404, not 403, for cross-organization access

Different from Phase 11's within-organization semantics (which used 403,
since reads stayed globally visible within one organization). A resource
in another organization must look like it doesn't exist at all — a 403
would confirm it exists *somewhere*, itself a leak. Mechanism: once
`repository.get(id, organization_id)` returns `None` for a cross-
organization id, the *existing* `NotFoundError` → 404 path already handles
it; no new branching was needed at the route layer. The same pattern
extends to `app/api/v1/organizations.py`'s own routes: every one resolves
the caller's *active* organization via `get_current_membership` and 404s if
the path `organization_id` doesn't match it — a path id is a claim that
must be verified against the trusted session-derived value, never trusted
on its own.

### Access grants never cross organizations

`AccessGrantService.grant_team_access`/`grant_project_access` (Phase 11)
now verify **both** that the target Team/Project resolves within the
acting organization (via the now-org-scoped `.get()`) **and** that the
target user holds an *active* membership in that same organization —
raising `NotFoundError`, not `ForbiddenError`, either way, so a same-org
team id paired with a different-org user id fails exactly like a
nonexistent user would (never confirming the user exists elsewhere).

### Organization lifecycle and membership administration

Create (any authenticated user, no permission check — there's no existing
organization context to check a permission *within* yet; the creator
becomes Owner in the same transaction, so a new organization never exists
with zero Owners even momentarily) / get / update(name) / deactivate,
gated by new `Permission.ORGANIZATION_MANAGE` (Owner only). Membership
add/list/change-role/revoke/reactivate gated by new
`Permission.MEMBERSHIP_MANAGE` (Owner + Admin, mirroring `ACCESS_MANAGE`'s
precedent). "Add a member" resolves an **existing** `User` by email
(Phase 10's `get_by_email` precedent) — no invitation/email delivery, no
side-effect account creation (CLAUDE.md §26). Owner and Admin are no longer
identical permission sets: Owner alone holds `ORGANIZATION_MANAGE`;
`MEMBERSHIP_MANAGE` (and everything else) stays shared, mirroring how
Phase 11 kept `ACCESS_MANAGE` Admin+Owner rather than Owner-only.

## Milestone C hardening (risk-ranked)

1. **`ExportService`** — every `_collect_rows` branch's `organization_id`
   is now required by the underlying repository signatures; the "filter
   omitted" fallback is "whole organization," never "whole table."
2. **`ScenarioService`/`ScenarioCalculationService`** — `_check_person`/
   `_check_project`/`_check_allocation` now resolve through org-scoped
   repositories, so a payload referencing another organization's person/
   project/allocation fails `NotFoundError` exactly like a nonexistent id.
   `_load_baseline_state` was refactored to call the shared
   `load_people_facts` helper instead of duplicating its query shape,
   folding the org-scoping fix into the one place both capacity and
   scenario calculation already share.
3. **`planning_facts.py::load_people_facts`** — gained `organization_id`,
   threaded into all three fact-type queries; every caller (capacity,
   scenario, insights) inherited the fix through this one shared function.
4. **`ImportService`** — every identity-resolution lookup (email/name/
   external_id) gained `organization_id`.
5. **`insight_service.py`/`skill_capacity.py`** — the "ORG-WIDE" candidate
   pool documentation now means org-scoped, not globally unscoped;
   `list_for_skills` requires `organization_id`.
6. **`AIContextBuilder`/`AIService`** — made safe by construction: it makes
   zero independent repository queries, only calling back into
   Capacity/Insight/Scenario/Skill services, so fixing those four made AI
   safe without AI-specific logic; `organization_id` still threads through
   its public methods for the 3 trivial label lookups it does own.

## Migration

One Alembic revision (`6fca5b5c9b4f`, chained after Phase 11's
`69270a626bfc`), hand-written rather than raw autogenerate output — every
one of the 13 organization-owned tables has real data that must be
backfilled to a bootstrap organization *between* adding the nullable
`organization_id` column and making it `NOT NULL`, a sequence autogenerate
cannot express on its own. Sequence: create `organizations`/
`organization_memberships` → insert one deterministic bootstrap
organization (fixed UUID, `slug='default'`) → backfill
`organization_memberships` from every existing `User.role` (Python-side
`uuid.uuid4()` per row, not raw cross-dialect SQL UUID generation, so it
stays portable to Postgres production) *before* dropping the column →
`batch_alter_table` drop `users.role` → add nullable `sessions.
active_organization_id` (no backfill — `NULL` is the correct "must select
an organization" state) → for each of the 13 tables: add nullable column →
`UPDATE` backfill to the bootstrap org → `batch_alter_table` to `NOT NULL`
+ FK + index + (where applicable) drop the old single-column unique
constraint and add the new composite one → add nullable `audit_events.
organization_id` (no backfill). `downgrade()`'s `organization_memberships →
users.role` direction is lossy for any user later given a second
membership (writes back only the first membership found per user) —
accepted as a development safety net, not a supported production rollback
path, the same caveat already accepted for structurally-irreversible
changes in prior migrations.

Verified: full chain (`alembic upgrade head`) against a completely fresh
database; `upgrade` → `downgrade` → `upgrade` round-trip against the
existing dev database with real prior data, confirming the schema and
`users.role` fully restore on downgrade and the bootstrap organization/
composite constraints are correctly in place after re-upgrade. The
recurring SQLite CHECK-constraint autogenerate text-diff false positive
(documented in every prior phase's migration — ADR 0002/0004/0005/0006/
0007/0010/0011) fires again for every enum column touched by table
recreation; not reproduced in this migration's `alembic check` output
verbatim, since hand-writing explicit `batch_alter_table` blocks (rather
than relying on autogenerate's own diff) never emits those spurious
`CheckConstraint` drop/recreate pairs in the first place.

## Test fixture strategy

The constraint that made ~600 pre-existing tests need zero behavioral
changes: `tests/conftest.py::client_as` transparently creates one default
`Organization` per test (lazily, on first call, cached for the test's
duration) plus a fresh `User` + `OrganizationMembership(role)` per call,
overriding **both** `get_current_user` and the new `get_current_membership`
together so they always agree — a test written as
`client_as(UserRole.MANAGER)` before this phase means exactly what it
always meant ("a Manager acting in the test's organization"), with the
organization itself invisible unless a test explicitly reads
`test_client.organization`. `tests/factories.py`'s org-owned `make_*`
functions each gained a required `organization` keyword parameter; a new
`organization` pytest fixture (backed by `make_organization`) is available
for tests building rows directly through factories rather than through
`client_as`. Genuinely new cross-tenant tests construct a **second**
organization explicitly.

## Consequences

- New tables: `organizations`, `organization_memberships`. New/extended
  columns across 15 existing tables (13 `NOT NULL` + `sessions`/
  `audit_events` nullable). 1 migration.
- New backend modules: `app/models/{organization,organization_membership}.
  py`, `app/repositories/{organization,organization_membership}.py`,
  `app/services/{organization,organization_membership}.py`,
  `app/schemas/{organization,organization_membership}.py`,
  `app/api/v1/organizations.py`. Extended: every repository/service/route
  for the 13 organization-owned entities (Person, Team, TeamMembership,
  Project, Allocation, WorkingSchedule, AvailabilityException, Skill,
  PersonSkill, ProjectSkillRequirement, Scenario, TeamAccessGrant,
  ProjectAccessGrant), `ExportService`, `ImportService`, `InsightService`,
  `SkillCapacityService`, `AIContextBuilder`, `AIService`,
  `CapacityService`, `planning_facts.py`, `AccessGrantService`,
  `AuthService`, `AuditService`, `app/api/deps.py` (+`get_current_
  membership`, +`get_organization_repository`, +`get_organization_
  membership_repository`), `app/schemas/{user,auth}.py` (`MeRead`),
  `app/domain/authorization.py` (+`ORGANIZATION_MANAGE`,
  +`MEMBERSHIP_MANAGE`), `app/models/enums.py` (+`MembershipStatus`, +9
  `AuditAction` members, -1 obsolete member), `app/main.py`.
- 0 new external dependencies.
- Backend: 616 tests total, all passing. `ruff check` and `pyright`
  (strict) both fully clean across `app/` and `tests/` — zero errors.
- **Not yet done as of this ADR's initial acceptance**: frontend
  (`CurrentUser`/`AuthContext`/`RequireAuth`/`OrganizationSwitcher`/
  `/select-organization`), live verification against a running server,
  README/architecture/domain-concepts doc updates beyond this ADR.
- **Deferred, matching the phase boundary**: billing/subscription
  concepts, SSO/OAuth, cross-organization data sharing, organization
  hierarchies/sub-organizations, per-organization feature flags, hard
  delete of an organization, a UI for the "last remaining Owner account
  disable" gap noted above.
