# ADR 0043: Phase 43 — Audit Log UI

- **Status:** Accepted
- **Date:** 2026-09-08

## Context

The Phase 41 full roadmap re-audit (audit-only, no code, no ADR, no
commit) found a gap no prior phase had named as a deliberate deferral:
`GET /api/v1/audit` (`app/api/v1/audit.py`) has existed, fully built,
organization-scoped, and permission-gated, since Phase 10 — with **zero
frontend consumer anywhere** in `apps/web/src`. Phase 42 built the
Capacity vs. Priority matrix instead (a different, user-supplied product
decision); Phase 41's Audit Log UI recommendation remained the standing
candidate. Phase 43 builds it.

### What was audited before implementing

- Git state: `HEAD` at `16d1b71` ("Implement Phase 42 capacity vs.
  priority matrix visualization"), matching `origin/main` exactly (0
  ahead / 0 behind), working tree clean. This **contradicts** the Phase
  43 brief's own stated context ("Phase 42 changes intentionally
  uncommitted") — the user had separately instructed a commit and push
  between Phase 42's report and this phase starting, which the brief's
  author was not aware of. Per this phase's own instruction not to trust
  a prior report's commit-status claim, the actual state (verified via
  `git status`/`git log`/`git fetch`) is what this phase proceeded from.
- CLAUDE.md §§4, 21, 26–40; `docs/roadmap.md`; `docs/architecture.md`;
  `docs/domain-concepts.md`; `README.md`; ADR 0006 (import/export —
  confirmed Scenario/Insight/AuditEvent are all deliberately excluded
  from that pipeline as derived/historical, not source data — the same
  reasoning this phase's own read-only design follows), ADR 0011/0012
  (organization scoping precedent), ADR 0015 (last-owner invariant —
  confirms `AuditService`/`AuditEvent` predate and are unrelated to that
  guard), ADR 0028-0035 (the membership/user/organization admin-UI
  family this page joins), ADR 0042 (the immediately preceding phase's
  precedent for reusing an existing bulk-list endpoint client-side).
- Backend: `app/models/audit_event.py` (append-only, `organization_id`
  nullable + `ondelete=SET NULL`, `event_metadata` deliberately minimal —
  "never a raw request body... or any secret"), `app/models/enums.py`
  (`AuditOutcome` — closed, DB-constrained, 3 values; `AuditAction` — open,
  backend-owned vocabulary, dozens of members, explicitly documented as
  "expected to be added... a pure code change, never a migration"),
  `app/schemas/audit.py::AuditEventRead` (the exact response shape),
  `app/repositories/audit_event.py::list_filtered` (the only server-side
  filters: `actor_user_id`, `action`, `resource_type`, `start`, `end` —
  all exact-match/range, no substring search on any field; classic
  offset/limit pagination with a real `total` via a `COUNT` query),
  `app/api/v1/audit.py::list_audit_events` (`GET /api/v1/audit`,
  `Permission.AUDIT_READ`, `get_current_membership`-scoped to the
  caller's active organization, `limit` `Query(default=100, ge=1,
  le=500)`), `app/domain/authorization.py` (`AUDIT_READ` granted only to
  `ADMIN`/`OWNER`, alongside `USER_READ`/`USER_WRITE`), and
  `tests/api/test_audit.py` (confirms audit events never carry a
  password/token, `event_metadata` shape per action type, and the
  route's existing organization-scoping contract).
- Frontend: `features/users/{api/usersApi.ts,hooks/useUserAccounts.ts,
  components/UsersFilterBar.tsx,views/UsersPage.tsx}` (the closest
  existing precedent — a permission-gated, filtered, organization-
  implicit list page) and `features/members/{api/membersApi.ts,
  hooks/useMemberships.ts,types/members.ts}` (the existing, complete,
  already-authorized organization roster — `user_id` + `email` +
  `display_name` — reused here rather than fetched again); `api/client.ts`
  (`QueryParams`, `apiGet`, `ApiError`); `features/auth/context/
  AuthContext.tsx` (`switchOrganization`'s full-cache-purge on organization
  switch — the mechanism this phase relies on for Requirement §16, not a
  new one); `components/ui/{Card,Table,Badge,Select,Button,EmptyState,
  ErrorState,QueryBoundary}.tsx`; `components/layout/{AppShell,
  PageHeader}.tsx`; `app/routes.tsx`; `test/{fixtures.ts,
  mockQueryResult.ts}`.

## Decision

Build a single, read-only **Audit Log** page at `/admin/audit`
(`apps/web/src/features/audit/`) consuming `GET /api/v1/audit` exactly as
it already exists. **Zero backend changes.**

### Existing API contract (verified, not assumed)

| Aspect | Value |
|---|---|
| Endpoint | `GET /api/v1/audit` |
| Authorization | `Permission.AUDIT_READ` (Admin/Owner only) |
| Scope | The caller's active organization (`get_current_membership`), server-side, unconditionally |
| Response | `Page[AuditEventRead]` — `{items, total}` |
| Fields | `id`, `timestamp`, `organization_id`, `actor_user_id`, `actor_email`, `action`, `resource_type`, `resource_id`, `outcome` (`success`/`failure`/`denied`), `request_id`, `event_metadata` |
| Filters | `actor_user_id` (exact), `action` (exact), `resource_type` (exact), `start`/`end` (inclusive timestamp range) |
| Pagination | `limit` (1-500, default 100) + `offset` (default 0); `total` is a real `COUNT` over the filtered set |

No field was invented; nothing was added to this contract.

### Filters exposed: actor and date range only

Of the four server-supported filters, this UI exposes **actor** and
**since/until** as controls; `action` and `resource_type` are shown as
plain table columns, not filter controls. Reasoning: `action` and
`resource_type` are each an open, backend-owned vocabulary with no
frontend-exposed enum (`AuditAction`'s own docstring: new values are
"a pure code change, never a migration"). A dropdown would have to either
duplicate that list client-side (a drift risk every time a new action is
added) or be built from only the currently-loaded page's distinct values
— which would misrepresent completeness, exactly the "fake filtering
experience" this phase's brief explicitly warns against (§9). The actor
filter avoids this problem entirely: it is populated from the active
organization's **complete** membership roster
(`useMemberships`/`membersApi.list`, already fetching every member,
active and revoked, with no page-size risk since this app's `LIST_ALL_LIMIT`
convention already covers it) — a real, complete, already-authorized list,
not a fabricated one. `actor_user_id` is the one server filter that isn't
directly human-typable (a raw UUID), so resolving it through an existing,
already-fetched roster is the one case here where a Select is honest and
useful rather than risky.

### Pagination — the first real pagination UI in this frontend

Every other "list all X" pattern in this app (`peopleApi.list`,
`projectsApi.list`, `allocationsApi.list`, `usersApi.list`) fetches up to
500 rows in one request and never paginates — deliberate, per ADR 0034's
own documented convention, because those entities are small in practice.
An audit trail is different: it grows without bound and existed already
before this phase, so treating "the first 500 rows" as if it were the
whole history would misrepresent it. This phase therefore builds real
Previous/Next controls over the endpoint's existing `limit`/`offset`/
`total` contract — `AUDIT_PAGE_SIZE = 50`, `offset` held in local
component state, reset to `0` on every filter change, "Showing X–Y of Z
events" computed from the response's own `total`. This is the first
pagination UI this codebase has needed, and it is built on the contract
that already exists — no new pagination architecture, cursor scheme, or
backend change.

### Actor / target / details display — no fabricated semantics

`actor_email` (already denormalized server-side) is shown verbatim; a
null actor (e.g. a login failure against an unknown email) renders
"Unknown actor" rather than a blank cell. `action` is rendered as the raw
machine code (`<code>`), never mapped through an invented human-readable
label table — the same reasoning that ruled out an `action` filter
dropdown applies here: any such mapping would immediately go stale for a
newly added `AuditAction` member and would be reading intent into a
string the backend didn't provide. `resource_type`/`resource_id` render
together as the "Target" column, `resource_id` truncated with a `title`
tooltip since it is frequently a full UUID. `event_metadata` renders as
a compact `key: value` list — never raw JSON, and never expanded beyond
what the backend already decided is audit-safe to expose (verified live
against `tests/api/test_audit.py`'s own "never contains a password or
token" guarantee — this UI adds no new field to that payload).

### Authorization & multi-tenancy

- **No authorization or tenancy code was written or changed.** The route
  is already `Permission.AUDIT_READ`-gated and already scoped to the
  caller's active organization on the server, unconditionally, on every
  request.
- The frontend passes **no** organization id anywhere — `auditApi.list`
  accepts only `actor_user_id`/`start`/`end`/`offset`/`limit`. There is no
  way for this UI to request another organization's events, because the
  backend never accepts one to select.
- The page is gated by `can('audit.read')` for UX only
  (`AuditLogPage`/`AppShell` nav), mirroring `UsersPage`'s exact pattern —
  the backend re-checks the real permission on every request.
- **Organization switching**: no organization id is threaded into
  `useAuditEvents`'s query key (`['audit-events', filters]`), matching
  every other organization-scoped query in this app. Switching
  organizations already purges the **entire** React Query cache except
  `['session']` (`AuthContext.tsx::switchOrganizationMutation`,
  established since Phase 12) — this is the single existing mechanism
  every organization-scoped page in this codebase already relies on for
  "no stale data survives a switch," and this phase adds nothing on top
  of it. That mechanism already has its own test coverage
  (`AuthContext.test.tsx`'s `switchOrganization` suite); this phase does
  not duplicate it per-feature, matching the precedent that no other
  organization-scoped feature (Users, Members, Projects) re-tests it
  either.

### Sensitive data

No new field is exposed beyond `AuditEventRead`'s existing shape.
`event_metadata` was already audited by the backend's own test suite to
never carry a password, token, or file content
(`tests/api/test_audit.py`); this phase renders that same, already-vetted
payload and adds nothing to what the API returns.

## Consequences

- **Backend:** 0 files changed. 0 new tables, 0 migrations, 0 new routes,
  0 new query parameters, 0 new permissions, 0 new roles, 0 API-contract
  changes. `docs/openapi.json` untouched.
- **Frontend:** 10 new files
  (`features/audit/{types/audit.ts, constants.ts, api/auditApi.ts,
  hooks/useAuditEvents.ts, components/AuditFilterBar.tsx+test,
  components/AuditEventsTable.tsx+test, views/AuditLogPage.tsx+test}`),
  3 files edited (`app/routes.tsx` — 1 import, 1 route;
  `components/layout/AppShell.tsx` — 1 nav entry; `test/fixtures.ts` —
  1 new `makeAuditEvent` fixture).
- **Tests:** +20 (7 in `AuditEventsTable.test.tsx`, 4 in
  `AuditFilterBar.test.tsx`, 9 in `AuditLogPage.test.tsx`). Frontend
  suite: **368 → 388 passing**, 73 → 76 files, verified with a final
  clean full-suite run (all green, no flakes).
- **Typecheck:** `tsc -b --noEmit` clean. **Lint:** `oxlint` clean (two
  pre-existing, unrelated warnings remain in `AuthContext.tsx`, unchanged
  by this phase). **Build:** `tsc -b && vite build` succeeds (the
  pre-existing >500 kB chunk-size advisory is unrelated — Recharts has
  been in the bundle since Phase 24). One test (`TeamCapacityTable.test.tsx`,
  unrelated to this phase — `features/capacity/`, untouched) timed out
  once during a run where a test pass and a production build were
  executing concurrently in the background; it passed cleanly in
  isolation and in a subsequent full clean run, confirming environment
  resource contention, not a regression.
- **Backend verification:** not run — 0 backend files changed
  (`git status`/`git diff --name-only` confirm no `apps/api` path
  touched), the same convention every zero-backend-change phase since
  Phase 24 has followed.
- **Live/API verification:** no backend behaviour changed, so no endpoint
  was verified live this phase; the route this feature consumes was
  already live-verified in Phase 10 and is byte-for-byte unchanged here.
- **Browser verification:** not performed — no browser-automation tool is
  available in this environment (the same disclosed limitation as every
  prior frontend phase).

### Known limitations

- `action`/`resource_type` filtering is not exposed in the UI, though
  both are real, supported backend query parameters — deliberately
  deferred rather than built as a misleading dropdown (see Decision). A
  future phase could expose them as plain text inputs sending the exact
  machine code verbatim (an honest, non-dropdown design), if requested.
- The actor picker's roster comes from `useMemberships` (active + revoked
  members of the **current** roster only) — an audit event whose actor
  was fully removed from every organization (not merely revoked from
  this one) would not appear as a selectable option, even though the
  event itself, carrying its own denormalized `actor_email`, would still
  correctly display in the table. This is a pre-existing property of
  `membersApi.list`, not something this phase changes.
- No "jump to page N" — Previous/Next only, matching the smallest useful
  contract over `offset`/`limit`/`total` per the brief's own bounded-scope
  instruction.

### Deferred, not dropped

- Risk vs. Value quadrant (still blocked on a user-supplied "Value"
  definition and risk-aggregation rule), scenario snapshots, org-wide
  Risk/Stakeholder registers, external integrations, SSO/OAuth, billing,
  org hierarchies, Chrome extension, PostgreSQL concurrency verification —
  unchanged, none started this phase, per the brief's explicit exclusion
  list.

## Confirmation

Phase 44 was **not** started. Nothing in this phase was committed or
pushed — see the Phase 43 Final Report for the exact git state.
