# ADR 0035: Phase 35 — USER_WRITE organization-scoping decision

- **Status:** Accepted
- **Date:** 2026-08-29

## Context

ADR 0029 (Phase 29) surfaced, but deliberately did not resolve, a
property of the existing `USER_WRITE` contract: an Admin/Owner of
Organization A can rename or disable/enable a `User` account that has no
membership in Organization A at all — only a membership in some other
organization, or no membership anywhere. ADR 0029 recorded this as *"a
candidate for a future explicit product decision, not something Phase 29
alters."* Every phase since (30–34) repeated "still open" rather than
resolving it — including Phase 34, whose brief explicitly forbade
touching it. Phase 35's brief named this the recommended next candidate
and required either an explicit, sufficiently precise decision already
present in the repository, or a stop-and-ask gate — never a guess.

## Audit findings — the executable contract

Per the phase brief's audit-first, decision-gate-first instruction, the
following were confirmed directly against current code before any
question was asked or any code touched:

| # | Question | Finding |
|---|---|---|
| 1 | What does `USER_READ` permit? | `GET /api/v1/users` (list, Phase 34 added `q`/`status` filters), `GET /api/v1/users/{id}` — both global, no organization filter (ADR 0012 Decision 8, explicit: "`GET /users` stays deliberately organization-*unscoped*"). |
| 2 | What does `USER_WRITE` permit? | `POST /api/v1/users` (create a new global account — not "belonging" to any org yet) and `PATCH /api/v1/users/{id}` (`display_name`, `status` active/disabled, `person_id`). Same grant set as `USER_READ` (Admin/Owner). |
| 3 | Is role/membership management the same surface? | **No — already a separate, already-organization-scoped surface.** `PATCH/DELETE /organizations/{organization_id}/memberships/{user_id}/...` is gated by `Permission.MEMBERSHIP_MANAGE` **and** `_require_active_organization` (a path `organization_id` that isn't the caller's active org **404s** — verified in `app/api/v1/organizations.py:47-56`, confirmed IDOR-safe live in this phase's own verification below). This was resolved by Phase 12/28 and was never part of the `USER_WRITE` ambiguity — this phase did not touch it. |
| 4 | What can `PATCH /api/v1/users/{id}` cross an org boundary today? | Only the account-level fields: `display_name` (rename) and account `status` (disable/enable — itself already guarded by the Phase 15 last-owner invariant across every organization the account is an active Owner of, unrelated to the caller's org). `person_id` linking is the one already-scoped exception (validated against the acting org's People, unchanged, untouched by this phase). |
| 5 | Does ADR 0029 recommend a direction? | No — it explicitly frames this as an open question, not a lean. |
| 6 | Does CLAUDE.md §27 resolve it? | Considered and found **not dispositive**: §27 forbids modifying "data belonging to an organization [the caller] is not an active member of," but `User` is explicitly modeled by ADR 0012 as belonging to **no** organization (no `organization_id` column) — the global login identity by design. §27's precondition doesn't unambiguously bind to a resource the schema itself defines as organization-less. Treating §27 as decisive here would have been exactly the "infer intent from naming/principle" the brief warned against. |
| 7 | Any other materially different option the repository already exposes? | None found. The membership-scoped pattern (`_require_active_organization`) is the only existing "organization boundary" mechanism, and it already fully governs the separate role/status-of-membership surface (finding #3) — there was nothing left unexplored beyond the Option A/B/C space the brief itself named. |

No explicit, sufficiently precise decision existed anywhere in the
repository. Per the brief, implementation was **not** guessed —
the phase stopped and asked the user directly.

## Decision

**Option A was chosen: `USER_WRITE` remains global. No code change.**

The user was presented with three options (keep global / scope both
rename and status to the caller's organization / scope only status,
leaving rename global) plus the tradeoffs for each — including that
Option B/C would require inventing a membership-existence check with no
existing precedent, and would need an explicit carve-out for accounts
with zero memberships anywhere (which belong to no organization under
any scoping rule, and would otherwise become unmodifiable by anyone).
The user chose to keep `USER_WRITE` global, matching the already-explicit
global design of `USER_READ`/`GET /users` (ADR 0012 Decision 8) and
requiring no new authorization concept, no migration, and no change to
any existing tested Admin/Owner workflow.

### Exact scope of the decision

- `POST /api/v1/users` and `PATCH /api/v1/users/{id}` remain global —
  an Admin/Owner may create, rename, or disable/enable **any** `User`
  account, regardless of that account's organization membership(s),
  exactly as before this phase.
- This is now a **documented, deliberate, accepted** property of the
  system, not merely an unaddressed edge case — closing the "candidate
  for a future explicit product decision" ADR 0029 opened.
- The already-organization-scoped membership/role surface
  (`/organizations/{id}/memberships/...`, gated by `MEMBERSHIP_MANAGE`
  and `_require_active_organization`) is **unaffected** and remains the
  correct place any future organization-boundary tightening around
  *roles* would go, should that ever be requested — this decision is
  specific to the account-level `USER_WRITE` fields only.
- No new permission, role, endpoint, or schema field. `Permission.
  USER_READ`/`USER_WRITE` grant sets (Admin/Owner) are unchanged.

### Expected authorization/IDOR behavior (unchanged, now explicit)

- Admin/Owner with `USER_WRITE` → `PATCH /users/{id}` for any existing
  account id → 200, regardless of the caller's active organization or
  the target account's memberships.
- Manager/Member/Viewer → 403, unchanged (no `USER_WRITE`).
- Unknown account id → 404, unchanged.
- The Phase 15 last-owner invariant on disable → 422 if disabling would
  strand any organization the account is an active Owner of, unchanged
  and evaluated across every organization regardless of the caller's own.
- The genuinely organization-scoped surface (membership role/revoke/
  reactivate) still 404s a path `organization_id` that isn't the
  caller's active org — verified live in this phase (see below) as an
  explicit control check, confirming this decision did not weaken that
  boundary.

### Backwards compatibility

Total — this is a no-op on the API contract, schemas, and every existing
test. No Admin/Owner workflow changes behavior in any way.

## Backend changes

None to production code. One new regression test,
`tests/api/test_users.py::test_user_write_is_deliberately_global_across_organizations`,
locks the decision in as an intentional, tested contract: an Owner
acting in "Org A" renames and disables an account whose only membership
is in a separately-created "Org B," asserting both mutations succeed
(200). Without this test, a future phase auditing this area could easily
mistake global `USER_WRITE` for an untested accident rather than a
closed decision.

## Frontend changes

None. No behavior changed; nothing to update.

## Database / migration impact

None. No schema change.

## Tests

- Backend: **+1** (`test_user_write_is_deliberately_global_across_organizations`).
  Full suite: **1007 passed** (was 1006 after Phase 34). `ruff check .`
  clean. `uv run pyright` (strict) **0 errors**.
- Frontend: unchanged — no files touched, no new run needed beyond
  confirming no regression (none possible; nothing was edited).

## Verification

- **Fresh DB:** a brand-new SQLite file migrated cleanly via
  `alembic upgrade head` to the existing head (`9f73a340f443`) — no new
  migration exists or was expected.
- **Live/API:** a real `uvicorn` server was started against that
  database. `scripts/create_first_owner.py` bootstrapped Owner A in
  "Default Organization." A target account was created with no
  membership anywhere; a second organization ("Org B") was created and
  the target added as a Member of Org B only (Owner A briefly switched
  active organization to B to do this, then switched back to Org A).
  Acting with active organization = A, `PATCH /users/{target_id}` was
  exercised twice over real HTTP — rename (200) and disable (200) —
  confirming the decision holds end-to-end, not just under the
  in-memory test client. A **control check** confirmed the already-
  scoped membership route (`GET /organizations/{org_b_id}/memberships`)
  still correctly 404s while acting in Org A, proving this phase did not
  weaken the boundary that *is* supposed to hold. Server log scanned for
  `password|token|hash|secret` — no matches. Server stopped and the
  scratch database removed afterward.
- **Browser verification:** not applicable — no frontend change was
  made, and browser automation remains unavailable in this environment
  regardless (the same disclosed limitation as every prior phase).

## Deviations

None from the approved decision.

## Assumptions

None beyond the user's explicit answer — no option was guessed or
defaulted to.

## Known limitations

Unchanged from ADR 0029: an Admin/Owner of any organization can still
touch an account with no relationship to that organization. This is now
explicitly accepted rather than merely unaddressed.

## Residual security risk

Unchanged from before this phase — no new risk introduced, since no
behavior changed. The existing risk (a global admin surface reachable by
any Admin/Owner of any organization) was already present since Phase 10/
12 and is now a documented, deliberate design choice rather than an
undocumented one.

## Technical debt

None added.

## Explicitly deferred work

Re-opening this decision (e.g., scoping `USER_WRITE` later) requires a
new, explicit product request — not implied by this ADR, which records
the decision as made, not as provisional. Nothing else was deferred by
this phase specifically.

## Confirmation

Phase 36 was **not** started. Nothing in this phase was committed or
pushed.
