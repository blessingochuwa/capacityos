# ADR 0044: Phase 44 — Audit Log action & resource-type filtering

- **Status:** Accepted
- **Date:** 2026-09-08

## Context

Phase 43 built the Audit Log UI (`/admin/audit`) consuming the existing
`GET /api/v1/audit` contract, and deliberately exposed only **actor** and
a **since/until** date range as filter controls — `action` and
`resource_type`, though both real, already-supported server-side query
parameters, were left as plain table columns. ADR 0043's own "Known
limitations" named this explicitly as a small, well-scoped follow-up:
build them as plain text inputs (never a dropdown), since
`AuditAction`/`resource_type` are open, backend-owned vocabularies with
no frontend-exposed enum. Phase 44 builds that follow-up.

### What was audited before implementing

- Git state: `HEAD` at `48a9674` ("Implement Phase 43 audit log UI"),
  matching `origin/main` exactly (0 ahead / 0 behind), working tree
  clean. This **contradicts** the Phase 44 brief's own stated context
  ("Phase 43 was not committed/pushed according to its report") — the
  user had separately instructed a commit and push after Phase 43's
  report, which the brief's author was not aware of. Per this phase's
  own instruction not to trust a prior report's commit-status claim, the
  actual verified state is what this phase proceeded from.
- CLAUDE.md §§4, 21, 26–40; `docs/roadmap.md`; `docs/architecture.md`;
  `docs/domain-concepts.md`; `README.md`; `docs/adr/0043-audit-log-ui.md`
  in full (its "Filters exposed" and "Known limitations" sections in
  particular).
- Backend, re-verified directly against current source (not assumed
  unchanged from Phase 43's own audit):
  `app/api/v1/audit.py::list_audit_events` — `action`/`resource_type`
  remain plain optional query parameters, no new validation added since
  Phase 43;
  `app/repositories/audit_event.py::list_filtered` — confirms
  `AuditEvent.action == action` and
  `AuditEvent.resource_type == resource_type`, both plain SQL equality
  comparisons, **not** `ilike`/substring/case-insensitive matching. This
  is the authoritative semantic this phase's UI is built on — verified
  fresh, not carried forward from memory.
- Frontend: the complete Phase 43 `features/audit/` tree exactly as
  committed (`api/auditApi.ts`, `hooks/useAuditEvents.ts`,
  `components/AuditFilterBar.tsx` + test,
  `components/AuditEventsTable.tsx` + test, `views/AuditLogPage.tsx` +
  test) — this phase extends every one of those files in place rather
  than introducing a parallel structure.

## Decision

Extend the existing Phase 43 Audit Log UI with two new **plain text**
filter inputs — Action and Resource type — wired through the exact same
architecture Phase 43 already established. **Zero backend changes.**

### Filter semantics — exact match, verified, not assumed

`action` and `resource_type` are **exact-match** filters
(`AuditEvent.action == action`), confirmed directly against
`app/repositories/audit_event.py::list_filtered` this phase, not merely
repeated from Phase 43's ADR. The frontend performs no matching logic of
its own and does not claim substring or case-insensitive behavior
anywhere in its UI copy — the placeholder text ("e.g. person.create" /
"e.g. project") demonstrates the expected format without claiming the
UI knows the complete set of valid values, and without claiming a
matching behavior (substring, fuzzy, case-insensitive) the backend does
not implement.

### Plain text, never a dropdown — the standing reason, reconfirmed

Identical reasoning to Phase 43's original deferral, reconfirmed rather
than re-litigated: `app/models/enums.py::AuditAction`'s own docstring
still calls it "an open... vocabulary," so a dropdown would either
duplicate that backend-owned list (a drift risk every time a new
`AuditAction` member is added, since the docstring is explicit that this
is "a pure code change, never a migration") or be built from only the
currently-loaded page's distinct values, misrepresenting completeness.
Both risks are avoided entirely by a plain text field the user fills in
with the exact or partial value they already know.

### Implementation shape

- **`features/audit/api/auditApi.ts`** — `AuditEventFilters` gains
  `action?: string` / `resource_type?: string`; `auditApi.list` passes
  both through to the existing, unchanged query parameters. No new
  endpoint, no new parameter on the backend side (both already existed).
- **`features/audit/components/AuditFilterBar.tsx`** — two new
  `type="search"` text inputs ("Action", "Resource type"), positioned
  between the existing Actor select and the Since/Until date inputs,
  using the same `INPUT_CLASS` and label/input layout every existing
  field in this component already uses. `type="search"` (matching
  `UsersFilterBar`'s own search-box precedent) gives a native browser
  clear affordance for free, directly serving the "must be able to
  clear Action/Resource type" requirement without new code.
- **`features/audit/views/AuditLogPage.tsx`** (`AuditLogManager`) — two
  new pieces of local state (`actionFilter`, `resourceTypeFilter`),
  trimmed before being sent (`actionFilter.trim() || undefined` —
  normalizing accidental whitespace is not a matching-semantics change,
  since the backend would reject a padded string as a non-match anyway),
  included in the `filters` object passed to `useAuditEvents` (and
  therefore in its `['audit-events', filters]` React Query key,
  unchanged mechanism), and in the existing `isFiltered` boolean gating
  the table's empty-state message. Both new `onChange` handlers call the
  same `resetToFirstPage()` every existing filter handler already calls
  — no new pagination logic, the same one Phase 43 built.

### Empty state — no change needed

Phase 43's `AuditEventsTable` already branches on a generic `isFiltered`
boolean ("No audit events match these filters." vs. "No audit events
yet."), computed in `AuditLogPage` from *any* active filter. Extending
that boolean's inputs to include the two new filters was sufficient —
no change to `AuditEventsTable` itself was needed or made, matching the
brief's own "table should remain unchanged unless testing reveals a
necessary clarification" instruction; testing confirmed none was
necessary.

## Authorization & multi-tenancy

Unchanged from Phase 43, not touched by this phase: `Permission.AUDIT_READ`
gating, organization-scoping via `get_current_membership`, the frontend's
`can('audit.read')` UX-only gate, and the no-organization-id-in-query-key
architecture (relying on `AuthContext`'s full cache purge on organization
switch). This phase adds two request parameters to an already-authorized,
already-scoped call — it introduces no new authorization or tenancy
surface to reason about.

## Consequences

- **Backend:** 0 files changed. 0 new query parameters (both already
  existed), 0 schema changes, 0 migrations, 0 new permissions.
  `docs/openapi.json` untouched — the API contract did not change.
- **Frontend:** 0 new files, 3 files edited
  (`features/audit/api/auditApi.ts`,
  `features/audit/components/AuditFilterBar.tsx`,
  `features/audit/views/AuditLogPage.tsx`) + 2 test files extended
  (`AuditFilterBar.test.tsx`, `AuditLogPage.test.tsx` — no new test
  files, matching the brief's "extend rather than duplicate" instruction).
- **Tests:** see the Phase 44 Final Report for the exact before/after
  count and file-by-file breakdown.
- **Browser verification:** not performed — no browser-automation tool
  is available in this environment (the same disclosed limitation as
  every prior frontend phase).

### Known limitations

- `action`/`resource_type` remain exact-match only — a user who doesn't
  know the precise machine code (e.g. typing "create" instead of
  "person.create") gets zero results, not a partial match. This is not a
  frontend limitation to work around; it is the backend's actual,
  unchanged semantic, and this phase does not alter backend filtering
  behavior to accommodate a friendlier UI (explicitly out of scope).
- No debounce on the two new text inputs — every keystroke updates
  component state and (since state feeds directly into the React Query
  key) issues a new request. This mirrors every *other* field already in
  `AuditFilterBar` (the Actor select and the two date inputs apply
  immediately, with no debounce), so the two new fields behave
  identically to their siblings rather than introducing a second
  interaction pattern within the same filter bar. A future phase could
  add a debounce across the whole bar if request volume becomes a
  concern; not attempted here as it was not requested and would add a
  second, unrequested behavior only to the two new fields.

### Deferred, not dropped

Risk vs. Value quadrant (still blocked on a user-supplied Value
definition and risk-aggregation rule — not started this phase), and
every other item this phase's own brief listed out of scope
(PortfolioSnapshot export, scenario snapshots, import/export
architecture, organization hierarchy, billing, SSO/OAuth, external
integrations, Chrome extension, PostgreSQL concurrency, USER_WRITE
scope, membership/account-directory redesign, capacity/allocation
redesign, any other visualization) — none started, none touched.

## Confirmation

Phase 45 was **not** started. Nothing in this phase was committed or
pushed — see the Phase 44 Final Report for the exact git state.
