# ADR 0014: Phase 14 stakeholder management

- **Status:** Accepted
- **Date:** 2026-08-21

## Context

Phase 13 (risk management) closed the ambiguity in CLAUDE.md's phase
roadmap and left §39 explicitly listing every unclaimed deferred item
rather than guessing at what came next. This session's task explicitly
named Phase 14 as CLAUDE.md §16 — Stakeholder Management — removing the
ambiguity Phase 13 had to resolve by asking. A repo-wide search confirmed
zero pre-existing stakeholder-related model, route, UI, or documentation
anywhere before this phase.

Phase 14's job: a `Stakeholder` entity — role, influence, interest,
decision authority, communication needs (§16's exact field list) — reusing
every existing system (organization scoping through the existing Project
relationship, RBAC, Phase 11 instance-level authorization, audit) rather
than building a parallel one, following Phase 13's `Risk`/
`ProjectSkillRequirement` precedent as closely as the domain allows.

## Decisions

**`Stakeholder` follows `Risk`'s exact shape** — the closest and most
recent precedent: organization-scoped, project-scoped, `CASCADE`-deleted
with its project, CRUD routes nested inside `app/api/v1/projects.py`
(`/{project_id}/stakeholders`, no separate route file),
`require_project_access` for writes (Phase 11's instance-level scoping —
a Manager needs an explicit grant on the specific project), `require_
permission` for reads (global per-role visibility). No new authorization
mechanism, no new tenancy mechanism, no new generic CRUD framework — the
existing `StakeholderRepository`/`StakeholderService` pair mirrors
`RiskRepository`/`RiskService` field-for-field.

**Stakeholders are NOT forced into the internal `Person` model.** A real
stakeholder is very often external to the organization's own staffed
roster — a client contact, a regulator, an executive at a partner
organization — and CLAUDE.md §9's Person/User distinction already
establishes that not every real-world identity belongs in `Person`
(which specifically answers "who is being planned for capacity").
`Stakeholder.name` is therefore always required and always stored
explicitly, independent of any internal link. `person_id` is an OPTIONAL
nullable FK to `Person`, `ON DELETE SET NULL` (matching `Risk.
owner_person_id`'s exact precedent) — for stakeholders who are also
staffed people. When set, `name` is still the stakeholder's own recorded
identity, never silently derived from or overwritten by the linked
Person's `display_name`, so renaming one never surprises the other.
Verified organization-scoped on create/update (mirrors
`PersonSkillService`/`RiskService`'s "both sides resolved through
org-scoped `.get()` before write" pattern) — a cross-organization
`person_id` fails `NotFoundError`, never silently links across the tenant
boundary.

**`influence`/`interest` are stored 3-tier enums; no combined
score is ever computed.** CLAUDE.md §16 lists "influence" and "interest"
without prescribing a scale. The well-established power/interest
stakeholder grid (CLAUDE.md §37: prefer established frameworks over
inventing one) uses exactly this pair of axes at exactly this
granularity — `low`/`medium`/`high`, DB-CHECK-constrained like `Risk.
probability`/`Risk.impact`. Deliberately **not** combined into an
"engagement quadrant" label ("manage closely" / "keep satisfied" / "keep
informed" / "monitor") even though that IS part of the same established
framework: §16 doesn't ask for it, and the task's own domain-design
instructions were explicit about not inventing a derived classification
merely because a framework would support one. The two raw values are
stored and displayed as-is; any grouping is a frontend presentation
choice a future phase can add without a schema change, not a backend
concept this phase invents.

**`decision_authority` is a 3-level stored enum, not a full RACI
matrix.** CLAUDE.md §5: "every important... decision... should have an
accountable owner" — this field is what lets a decision's owner be
identified among a project's stakeholders. `decision_maker` (can make or
veto the decision) / `advisor` (consulted, doesn't decide) / `informed`
(told after the fact) — three ordered levels answering exactly the one
field §16 asks for ("decision authority"), not a four-role
responsibility-assignment system (a different, unrequested concept).

**`communication_needs` is free text, not a fixed vocabulary.**
Communication preferences ("weekly email," "monthly steering committee,"
"ad hoc as needed") vary too much across projects and organizations to
fit a small closed set — matches `AvailabilityType`'s existing "open
vocabulary, no DB constraint" precedent, not `RiskStatus`'s "fixed
business meaning, DB-constrained" one.

**"Relevant project/work context" (§16's seventh field) needs no
separate stored field** — it is satisfied by `Stakeholder` being scoped to
exactly one `Project` in the first place, the same reasoning `Risk`
applied to the same phrase in §17's field list.

**`(project_id, person_id)` is a composite unique constraint, nullable
side included.** A person can be recorded as a stakeholder on a project
at most once; multiple external stakeholders with no `person_id` on the
same project don't collide, since `NULL` doesn't collide with itself
under a composite unique constraint in either SQLite or PostgreSQL —
matches `Project.external_id`'s exact precedent (ADR 0012).

**No Insights integration — deliberately, not by oversight.** CLAUDE.md
§16 defines no threshold, no derived fact, no existence condition to
classify into a signal — nothing structurally comparable to `Risk`'s
probability×impact→exposure or `ProjectSkillRequirement`'s
required-vs-qualified-hours gap. Every existing Phase 5/7/13 signal
exists because a real, specified, deterministic fact crosses a
CLAUDE.md-sanctioned threshold or existence gate; inventing a
"stakeholder health score" or an "under-engaged stakeholder" signal here
would be exactly the false-precision, unrequested-recommendation-engine
CLAUDE.md §17 (and this task's own instructions) explicitly warn against,
just applied to a different entity. Stakeholder Management stays a
project-context register, not a signal source.

**No Import/Export integration — deliberately deferred, matching Phase
13's own precedent.** CLAUDE.md §16 doesn't ask for it, and Phase 13
already established the pattern of deferring a new entity from the Phase
6 pipeline when not explicitly requested rather than silently expanding
scope on every new entity phase. Recorded as future work — see
Consequences.

**Editing is a first-class capability, unlike Risk's inline-status-only
UI.** This phase's brief explicitly separated "stakeholder editing" from
"stakeholder creation" as distinct required capabilities (Risk's brief
did not). `StakeholderForm` supports both create and edit via an optional
`stakeholder` prop — one component, not two — and an edit submission only
includes fields that actually changed from the original values (diffed
client-side before the `PATCH` body is built), so the audit trail's
`{"fields": [...]}` metadata reflects real edits, not a "did we submit
this key" artifact of always sending the full form.

**Frontend: `features/stakeholders/` mirrors `features/risks/`'s
single-page, `ProjectFilterPicker`-driven structure** — the same
established pattern (there is no per-project detail route in this app to
nest stakeholders under). `PersonPicker` is reused cross-feature from
`features/skills/components/`, the same way `RiskForm`/`SkillsOverviewPage`
already reuse it/`ProjectFilterPicker`. No dialog/modal component exists
anywhere in this codebase's UI kit (checked before designing the edit
flow), so editing swaps the create form into edit mode inline within the
same Card rather than introducing a new modal pattern.

## Consequences

- 1 new table (`stakeholders`), one migration (`c756ff8bebe5`), no
  changes to any existing table.
- New backend modules: `app/models/stakeholder.py`,
  `app/repositories/stakeholder.py`, `app/services/stakeholder.py`,
  `app/schemas/stakeholder.py`. Extended: `app/models/enums.py`
  (+`StakeholderInfluence`, +`StakeholderInterest`,
  +`StakeholderDecisionAuthority`, +3 `AuditAction` members),
  `app/domain/authorization.py` (+3 `Permission` members),
  `app/models/project.py` (+`stakeholders` relationship),
  `app/api/v1/projects.py` (+4 routes: list/create/update/delete).
  No pure domain module was needed (unlike `app/domain/risk.py`) — there
  is no derived value to compute; every stored field is a direct
  passthrough, so `StakeholderRead` needed no builder function either
  (unlike `Risk`'s `risk_to_read`).
- New frontend feature: `apps/web/src/features/stakeholders/` (types, API
  client, hooks, `StakeholderForm` (create+edit), `StakeholdersTable`,
  `StakeholdersOverviewPage`). Extended: `app/routes.tsx` (+`/stakeholders`),
  `components/layout/AppShell.tsx` (+nav link). `features/insights/` was
  **not** touched — no signal types, no schema fields, no presentation
  changes — matching the explicit no-Insights-integration decision above.
- 0 new external dependencies.
- Backend: +39 tests (7 model, 32 API covering CRUD, 401/403/404, the
  full Phase 11 grant matrix — Manager without grant denied, granted
  allowed, revoked denied again immediately with no re-login — audit
  events, and 2 explicit cross-tenant IDOR tests), 708 total, all
  passing. `ruff check` and `pyright` (strict) both fully clean. Frontend:
  +12 component tests, 172 total, all passing. `tsc -b`, `oxlint`, and
  `npm run build` all clean (2 pre-existing warnings in `AuthContext.tsx`
  predate this phase).
- **Live verification found no real application bugs** (unlike Phases 12
  and 13, each of which surfaced one). The full 16-step golden path —
  login/select-org, create project, create/read/update a stakeholder,
  audit trail, Viewer read-allowed/write-denied, Manager denied without a
  `ProjectAccessGrant`, granted via the real grant API, mutation succeeds,
  revoked via the real revoke API, the very next mutation attempt denied
  with no re-login, cross-organization access 404s, delete, deletion
  confirmed — passed end-to-end on the first attempt against the real
  file-backed dev database and a running server. Two operator mistakes in
  the verification script itself (a forgotten `X-CSRF-Token` header on one
  revoke call; a `GET` attempted against a path that only supports
  `PATCH`/`DELETE`, correctly answered `405`) were identified as scripting
  errors, not application defects, and did not require a code change or a
  regression test.
- **Deferred, matching the phase boundary:** Stakeholder Import/Export
  registration, an org-wide cross-project stakeholder register (every
  route stays nested under one project, matching `Risk`'s own deferred
  org-wide-register item), a frontend "engagement quadrant" grouping of
  influence×interest (the two raw values are available; combining them
  into a labeled grid is a presentation-only future addition, not a
  backend concept).
- **Explicitly out of scope, not silently implemented:** Prioritization
  (§18), SSO, billing, organization hierarchies, Team→Project
  authorization inheritance, Person-level authorization gaps, Scenario
  authorization, the per-organization last-Owner invariant, Risk
  Import/Export, and any AI-layer change — all remain exactly as
  documented in ADR 0012/0013's Consequences and CLAUDE.md §39's deferred
  list, untouched by this phase.
