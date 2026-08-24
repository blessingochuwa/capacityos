# ADR 0015: Phase 15 last-owner invariant

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

ADR 0012 (Phase 12) moved `role` off `User` onto `OrganizationMembership`,
which made Phase 10's old global "can't disable the last remaining Owner's
account" check obsolete — a single account-level check no longer has one
invariant to enforce once a User can be Owner of multiple organizations.
That gap was called out rather than silently dropped (ADR 0012's
Consequences, repeated in `docs/domain-concepts.md` and CLAUDE.md §39's
Phase 13/14 amendments) and left for a future phase to close deliberately.

Phase 15 is that phase, scoped narrowly: close the account-deactivation gap,
and — per the audit below — the concurrency gap in the two mutation paths
that already had a same-shape check.

## Audit findings (before any code changed)

Read in full: CLAUDE.md, `docs/architecture.md`, `docs/domain-concepts.md`,
ADRs 0010–0014. Audited: `Organization`/`OrganizationMembership`/`User`/
`UserSession` models, `AuthService`, `app/domain/authorization.py`,
`app/api/deps.py`, `OrganizationMembershipService`/`OrganizationService`/
`UserService` and their routes, `AuditService`, the frontend `AuthContext`,
`OrganizationSwitcher`, and every `features/` directory for an existing
membership- or user-management UI.

**`change_role`/`revoke` already enforced the per-organization invariant** —
contrary to a literal reading of ADR 0012's Consequences line ("the
now-obsolete test was removed rather than adapted"), `OrganizationMembershipService.
change_role`/`revoke` (built as part of Phase 12 itself) already contained a
`count_active_owners(organization_id) <= 1` guard, with existing test
coverage (`tests/api/test_users.py::test_cannot_demote_the_last_remaining_owner_of_an_organization`).
The genuinely open gap was narrower than ADR 0012's wording suggested:

1. **No guard existed anywhere for account deactivation** — `UserService.update`
   applied `UserUpdate.status` unconditionally via `setattr`, with zero
   awareness of `OrganizationMembership` at all. This is the literal Phase
   12 gap and Phase 15's primary target.
2. **The two existing guards were read-then-write, not atomic** — `count_active_owners`
   was read as a plain `SELECT`, decided on in Python, then a separate
   `UPDATE` (via ORM attribute assignment + `flush()`) followed. Two
   concurrent requests can each observe the same pre-decrement count and
   both proceed — see Concurrency below.
3. **No other mutation path removes an Owner.** Grepped the whole backend
   for `Owner`/`OrganizationMembership`/role-change/deletion/deactivation
   call sites: `add_member` and `reactivate` only ever increase or restore
   active-Owner count, never decrease it, so neither needs a guard.
   `OrganizationService.create` creates the Organization and its first
   Owner membership in one call (never zero-Owner even momentarily,
   documented in its own docstring already). `OrganizationService.deactivate`
   soft-deletes the whole Organization, not a membership — an inactive
   organization's Owner count is moot (`get_current_membership` already
   denies access to it regardless of who holds what role inside it). No
   hard-delete path exists for `User`, `OrganizationMembership`, or
   `Organization` anywhere in the codebase.
4. **No membership- or user-management UI exists in the frontend at all**
   — only `features/auth/` (login, `OrganizationSwitcher`,
   `SelectOrganizationPage`) and `features/access/` (Team/Project grant
   management) exist. There is no page that lists an organization's
   members, changes a role, revokes a membership, or disables a user
   account; those routes have existed, API-only, since Phase 12. Section
   12 of this phase's brief said explicitly not to add a new page solely
   for this phase — so the frontend section of this phase is a documented
   no-op, not an oversight.

## Decisions

### The core invariant, and what "active Owner" means

> For every active Organization: at least one `OrganizationMembership` with
> `role=Owner`, `status=Active`, whose linked `User.status` is also `Active`.

The brief's literal text (`count(active OrganizationMembership WHERE
role=Owner) >= 1`) doesn't mention `User.status`, and `MembershipStatus`'s
own docstring frames independence from `User.status` in one direction only
(revoking a membership must not force-disable the account). Taken alone,
that reading would make the account-deactivation path pointless to guard:
`OrganizationMembership.status` never changes when `User.status` does, so a
membership-only count could never be affected by disabling an account —
directly contradicting the brief's own worked example (§4C) and required
test ("disable final Owner → rejected"). Existing lifecycle behavior settles
it: `AuthService.login`/`resolve_session` already refuse to authenticate a
disabled `User` outright (`app/services/auth.py` lines checking
`user.status != UserStatus.ACTIVE`), so an Owner membership pointing at a
disabled account cannot actually exercise Owner authority today, regardless
of what this phase does. Counting it as satisfying the invariant would make
the invariant lie about whether the organization has a *working* Owner.

`OrganizationMembershipRepository.count_active_owners` (used by both
`change_role_if_safe` and `revoke_if_safe`'s guard subquery) was extended
with a `JOIN users ON ... AND users.status = 'active'` to reflect this. This
is a real behavior change to the two paths that already had a check, not
just a new path — documented here rather than left implicit: an Owner
membership whose account happens to already be disabled (only reachable
today as pre-existing data, since this phase closes the only path that
could newly create one) no longer counts toward satisfying the invariant
for `change_role`/`revoke` either. This is the smallest change that makes
all three mutation paths (role change, revocation, deactivation) use one
consistent, honest definition of "active Owner" rather than three
different ones.

### All protected mutation paths

| Path | Where | Mechanism |
|---|---|---|
| A. Owner → non-Owner role change | `OrganizationMembershipService.change_role` | `OrganizationMembershipRepository.change_role_if_safe` |
| B. Owner membership removal | `OrganizationMembershipService.revoke` | `OrganizationMembershipRepository.revoke_if_safe` |
| C. Owner account deactivation | `UserService.update` (status → disabled) | `UserRepository.disable_if_safe` |

Every other membership/user/organization mutation was audited (see above)
and confirmed incapable of reducing an organization's active-Owner count.

### Concurrency: atomic guarded `UPDATE`, not read-then-write

The unsafe shape, present in the pre-Phase-15 code:

```
count = SELECT COUNT(*) WHERE role=Owner AND status=Active   -- read
if count <= 1: reject                                          -- decide
membership.role = new_role; session.flush()                    -- write
```

Two concurrent requests can each run the `SELECT` before either runs the
`UPDATE`, both observe `count=2`, and both proceed — leaving zero Owners.
This is exactly the same class of bug ADR 0011 tested for (concurrent
grant/revoke) and ADR 0010 found for real (the `AuditService` cross-
connection deadlock) — real, not hypothetical, and only reproducible
against a real file-backed database with genuinely independent connections,
not the in-memory `StaticPool` fixture the rest of this suite uses.

The fix folds the count into the `UPDATE`'s own `WHERE` clause as a
correlated scalar subquery, so the guard is evaluated **as part of the same
write statement**, not a separate prior read:

```sql
UPDATE organization_memberships
SET role = :new_role
WHERE user_id = :user_id AND organization_id = :organization_id
  AND (role != 'owner' OR (<fresh count of active Owners in this org>) > 1)
```

SQLite (like PostgreSQL) serializes writers — only one write transaction is
ever "in flight" against a given database at a time (`app/core/database.py`'s
existing WAL + `busy_timeout=5000` PRAGMAs, set since Phase 10, already
make a second writer block-and-retry rather than fail immediately). Because
the guard subquery is evaluated as part of the `UPDATE` statement itself,
whichever request's `UPDATE` actually executes first commits against a
still-accurate count; the second request's `UPDATE` — blocked until the
first commits — then re-evaluates the *same* subquery fresh, correctly
seeing the first request's already-committed change and failing its own
guard. `rowcount == 0` after the `UPDATE` is unambiguous: the caller already
resolved the target row to exist (404 otherwise) before calling the guarded
method, so zero rows updated can only mean the invariant blocked the write,
never "no such row." `session.refresh()` reloads the ORM object from the
now-current database state afterward, since a Core `UPDATE` executed via
`session.execute()` doesn't update the identity-mapped Python object`s
attributes on its own.

`UserRepository.disable_if_safe` (path C) applies the identical technique
but as a `NOT EXISTS` correlated subquery across `organization_memberships`/
`users`, since the row being written (`users`) is a different table from
the rows the guard depends on. This is why the guard couldn't be
implemented by first calling into `OrganizationMembershipRepository` and
then writing to `User` as two steps — splitting it that way would
reintroduce the exact read-then-write race being closed. It is a
deliberate, narrow, documented exception to `UserRepository` otherwise
never referencing `OrganizationMembership`.

**What this does and doesn't prove.** SQLite's writer serialization is a
single-machine, single-database-file guarantee — every writer targets the
same file through the same PRAGMA-configured connection pool. This is not
a claim about PostgreSQL's MVCC/row-locking behavior under true multi-node
concurrency (CLAUDE.md §7: production must remain PostgreSQL-compatible).
The atomic-guarded-`UPDATE` technique itself (fold the invariant into the
`WHERE` clause of the write, don't decide in application code first) is
standard, portable SQL that produces an equivalent compare-and-swap
guarantee under PostgreSQL's isolation levels too — but that specific claim
is not re-verified against a real PostgreSQL instance in this phase; only
SQLite was actually tested, honestly stated as the residual risk below
rather than assumed.

**Verified**, against a real file-backed SQLite database with genuinely
independent connections per thread (`tests/api/test_last_owner_concurrency.py`,
following `tests/api/test_access_grant_concurrency.py`'s established Phase
11 pattern exactly):

- Two Owners, both demoted at the same instant → exactly one succeeds.
- Demote-vs-revoke race on the last two Owners → exactly one succeeds.
- Demote-vs-account-deactivation race on the last two Owners (different
  mutation *types*, different tables) → exactly one succeeds.
- Two different organizations' unrelated demotes, both proceeding
  concurrently → both succeed (busy_timeout serialization must not
  spuriously block or fail an operation that was never actually racing).
- After every contention scenario: `count_active_owners` is re-verified
  from a fresh connection to be exactly 1 — never 0.

All four tests pass consistently across repeated runs (checked manually);
none are flaky by construction, since SQLite's write serialization makes
the outcome deterministic rather than timing-dependent.

### Authorization: no new permission

The invariant is enforced regardless of actor — an Owner attempting to
demote/revoke/disable the last Owner (including themselves) is blocked
exactly like an Admin would be. No new `Permission` was added; the existing
`MEMBERSHIP_MANAGE`/`USER_WRITE` gates (Admin/Owner only, unchanged since
Phase 10/12) still decide *who may attempt* the operation, and the
invariant decides whether the *specific* attempt is allowed to succeed —
the same separation Phase 11 established between type-level permission and
instance-level scope.

### Error semantics: unchanged convention

`DomainValidationError` → HTTP 422, `{"detail": "..."}` — the exact status
and shape the pre-existing `change_role`/`revoke` guards already used, kept
identical for path C rather than introducing a new status code for the same
class of business-rule violation. Messages stay generic ("last remaining
active Owner"), matching the existing precedent of not naming other
organizations by name in an error a caller might not be authorized to know
about.

### Audit trail

Successful mutations continue to use the exact same `AuditAction`s Phase 12
already defined (`MEMBERSHIP_ROLE_CHANGE`, `MEMBERSHIP_REVOKE`,
`USER_STATUS_CHANGE`) — nothing new needed since the guard is inside the
existing write path, not a new one. **Rejected attempts are not separately
audited**, matching the existing, codebase-wide precedent: every one of the
~15 other `DomainValidationError` call sites in this codebase (date-range
validation, inactive-skill assignment, etc.) is likewise not written to
`AuditEvent`, relying only on the structured application log
(`core/exceptions.py::handle_validation`, which already logs "business rule
violation" at INFO with the request path) — the same pattern Phase 10/11
established for `ForbiddenError` NOT being the model to imitate here
(permission denials ARE separately audited, because they're a distinct,
security-relevant class of event; a business-rule rejection from an
authorized actor is not).

### Session behavior

No change. `get_current_membership` already re-resolves membership/
organization state on every request (Phase 12); a successful demote/revoke
is reflected on the acting session's very next request exactly as before.
A rejected disable leaves `User.status` untouched, so no session behavior
is affected at all.

### Database

**No migration.** No new column, table, or index — the invariant is
derived entirely from existing `OrganizationMembership`/`User` columns via
query logic, matching CLAUDE.md §9's "do not add `organization.owner_id`
unless clearly necessary" guidance in spirit (a per-organization Owner
count is exactly the kind of thing that must stay derived, never a
redundant stored value that could drift from the membership rows
themselves).

### Frontend

**No changes.** No membership- or user-management UI exists yet to add a
guard to (see Audit findings above) — building one was explicitly out of
scope ("do not add a new page solely for this phase"). The backend
enforces the invariant unconditionally regardless of what UI eventually
calls these routes.

## Consequences

- 0 new tables, 0 migrations. Extended: `app/repositories/organization_membership.py`
  (+`change_role_if_safe`, +`revoke_if_safe`, +`_active_owner_count_subquery`,
  `count_active_owners` now joins `User.status`), `app/repositories/user.py`
  (+`disable_if_safe`), `app/services/organization_membership.py`
  (`change_role`/`revoke` now call the atomic guards), `app/services/user.py`
  (`update` now guards a status→disabled transition).
- 0 new external dependencies.
- Backend: +43 tests (`tests/services/test_organization_membership.py`,
  `tests/services/test_user.py`, `tests/api/test_organizations.py`,
  `tests/api/test_last_owner_concurrency.py`, plus additions to
  `tests/api/test_users.py`) — 751 total, all passing. `ruff check` and
  `uv run pyright` (strict) both fully clean.
- Frontend: unchanged — 0 files touched, existing suite unaffected.
- **Behavior change to two already-shipped guards**: `change_role`/`revoke`'s
  existing last-Owner check now also requires the Owner's `User.status` to
  be `active` to count — see "what 'active Owner' means" above. Only
  reachable as a behavior difference for pre-existing data with an
  Owner-membership-pointing-at-a-disabled-account state, which this phase's
  own new guard (path C) prevents from being newly created going forward.
- **Residual risk, stated honestly**: the atomic-guarded-`UPDATE`
  concurrency guarantee is verified against SQLite's single-file writer
  serialization only, not against a real PostgreSQL instance under true
  multi-connection MVCC. The technique (fold the invariant into the write's
  own `WHERE` clause) is standard, portable SQL expected to hold under
  PostgreSQL's isolation levels too, but that expectation is not
  independently re-verified here — a future production-hardening pass
  against a real PostgreSQL deployment should confirm it rather than
  assume it.
- **Deferred, unchanged from prior phases**: everything CLAUDE.md §39 and
  ADRs 0011–0014 already listed as deferred (Team→Project inheritance,
  instance-level scoping for Person-keyed resources, SSO/OAuth, billing,
  organization hierarchies, Risk/Stakeholder Import/Export, the
  Prioritization entity). Phase 15 adds nothing to this list and removes
  exactly one item from it: the "per-organization last active Owner
  account-disable invariant" gap ADR 0012 named.
