# ADR 0013: Phase 13 risk management

- **Status:** Accepted
- **Date:** 2026-08-20

## Context

CLAUDE.md's phase roadmap (§39) named phases explicitly only through Phase
8, then bundled everything after that into one stale line — "Phase 9+:
External integrations, authentication, RBAC, multi-tenancy, and Chrome
extension" — that Phases 9–12 (production readiness, auth/RBAC/audit,
instance-level authorization, multi-tenancy respectively) already
outgrew without ever being recorded back into §39. Starting Phase 13, a
full audit (CLAUDE.md, README, docs/architecture.md, every ADR through
0012, a repo-wide search) confirmed no document anywhere named what "Phase
13" was supposed to be — a genuine ambiguity, reported to the user rather
than guessed at, per this session's instructions.

The user chose **Risk Management (CLAUDE.md §17)** from three audited
candidates (the others: extending Phase 11's instance-authorization gaps
to Person-keyed resources, or building only the last-remaining-Owner
account invariant ADR 0012 flagged as a deferred gap). That gap remains
explicitly out of this phase's scope — see Consequences.

Phase 13's job: a `Risk` entity — description, cause, potential effect,
probability, impact, response, owner, status, review date (§17's exact
field list) — reusing every existing system (organization scoping, RBAC,
instance-level authorization, audit, Insights) rather than building a
parallel one.

## Decisions

**`Risk` follows `ProjectSkillRequirement`'s exact shape** — the closest
existing entity: organization-scoped, project-scoped, `CASCADE`-deleted
with its project, CRUD routes nested inside `app/api/v1/projects.py`
(`/{project_id}/risks`, no separate route file), `require_project_access`
for writes (Phase 11's instance-level scoping — a Manager needs an
explicit grant on the specific project), `require_permission` for reads
(global per-role visibility, matching every other project-scoped
sub-resource). No separate `RiskService` design was needed beyond mirroring
`ProjectSkillRequirementService`'s CRUD/ownership-check pattern.

**`owner_person_id` points at `Person`, not `User`, and is `SET NULL` on
delete.** CLAUDE.md §9's existing Person/User distinction: an accountable
risk owner is a planning-relevant individual, not necessarily someone with
a login. `ON DELETE SET NULL` (matching `User.person_id`'s own precedent)
— the risk record must outlive whichever person currently owns it rather
than being deleted or blocked when that person leaves the roster.
Verified organization-scoped on create/update (mirrors
`PersonSkillService`'s "both sides resolved through org-scoped `.get()`
before write" pattern) — a cross-organization `owner_person_id` fails
`NotFoundError`, never silently links across the tenant boundary.

**`probability`/`impact` are coarse 3-tier stored enums; `exposure` is
never stored.** CLAUDE.md §17: "Do not create risk scores that imply false
precision." A fine-grained numeric scale would invite exactly that.
`exposure` (`low`/`medium`/`high`) is always derived at read time from an
explicit 3×3 lookup table in the new pure module `app/domain/risk.py`
(`calculate_risk_exposure`) — never a multiplication/formula, matching
`PROFICIENCY_RANK`'s explicit-table precedent in `app/domain/skills.py`,
and never persisted, matching how `Severity` is computed rather than
stored throughout Phase 5/7. `RiskRead` needed a builder function
(`risk_to_read`, matching `user_to_read`/`membership_to_read`'s precedent
for "the read model has a field `from_attributes` can't populate").

**`status` is a real 4-state lifecycle, DB-CHECK-constrained like
`ProjectStatus`:** `open` → `mitigating` (a response is underway) →
`monitoring` (mitigated but still watched, or a low-priority risk tracked
passively) → `closed` (terminal). CLAUDE.md §12/§17: "risk management
should be continuous" — a risk is not a one-time open/closed toggle. A
`closed` risk never produces a signal regardless of exposure or a lapsed
review date, enforced as the first branch of `classify_risk_signal` — see
below.

**Two new signal types plug into the EXISTING Phase 5/7 Insights
pipeline — no new route, same mechanism Phase 7 used for skill
signals.** `risk_high_exposure` and `risk_review_overdue` were added to
the same flat `SignalRead` model, the same `_TYPE_RANK`/`_prioritize`
ordering, and the same `get_project_signals` endpoint every other project
signal already flows through, via a new `_project_risk_signals`/
`_risk_signal` builder pair called from `InsightService._project_signals`
exactly where `_project_skill_signals` already is. `classify_risk_signal`
(pure, in `app/domain/risk.py`) is a mutually-exclusive if/elif chain
matching `classify_capacity_signal`'s style:

| Signal | Severity | Fires when |
|---|---|---|
| `risk_high_exposure` | `critical` while `open`, `warning` once `mitigating`/`monitoring` | exposure is `high` and status is not `closed` |
| `risk_review_overdue` | `warning` | `review_date` is in the past, status is not `closed`, and exposure is not already `high` |

A risk reports at most one signal (`risk_high_exposure` takes priority
when both conditions hold) — the same "existence gate, not a magnitude
judgment, one signal per underlying fact" discipline every Phase 5/7
signal already follows. `review_date == today` is not yet overdue (strict
`<`, matching `UserSession.expires_at`'s own expiry-boundary convention
elsewhere in this codebase). Severity is computed in the service layer
(`InsightService._risk_signal_severity`), not embedded in the domain
module — matching `_skill_gap_signal`'s inline-ternary precedent, since
domain modules classify and services assign severity throughout this
codebase.

**Import/Export registration: deliberately deferred, not built.** Every
phase since Phase 7 that introduced a new source-data entity registered
it into the Phase 6 import/export pipeline, but CLAUDE.md §17 doesn't ask
for this, and this task's scope-discipline instructions were explicit
("critical") about not expanding beyond the requested phase. Recorded as
recommended future work, not implemented — see Consequences.

**No global `/api/v1/risks` list route.** Matches `ProjectSkillRequirement`'s
exact route set (list/create/update/delete, all nested under a project, no
bare GET-by-id either). An org-wide cross-project risk register is a
reasonable future idea, not built now.

**Frontend: `features/risks/` mirrors `features/skills/`'s single-page,
`ProjectFilterPicker`-driven structure** — there is no per-project detail
route in this app to nest risks under (confirmed by audit: `Skill` was the
most recently added CRUD-with-relationships feature and uses this exact
pattern, not a `ProjectDetailPage`). `PersonPicker` is reused
cross-feature from `features/skills/components/`, the same way
`SkillsOverviewPage` already reuses `ProjectFilterPicker` from
`features/insights/components/`. Status changes are a single inline
`<select>` per table row (calling the existing `PATCH` route with only
`{status}`) rather than a full edit form — matching this codebase's
established convention that no entity's frontend exposes a full multi-field
edit form, only create + a small set of targeted inline actions
(`ProjectSkillRequirement`'s PATCH route, for example, has no frontend
edit UI at all, only remove).

## Consequences

- 1 new table (`risks`), one migration (`4ad14ba4eb50`), no changes to any
  existing table.
- New backend modules: `app/domain/risk.py` (pure, no I/O),
  `app/models/risk.py`, `app/repositories/risk.py`, `app/services/risk.py`,
  `app/schemas/risk.py`. Extended: `app/models/enums.py` (+`RiskProbability`,
  +`RiskImpact`, +`RiskStatus`, +3 `AuditAction` members),
  `app/domain/authorization.py` (+3 `Permission` members), `app/models/
  project.py` (+`risks` relationship), `app/api/v1/projects.py` (+5 routes),
  `app/schemas/insights.py` (+2 `SignalType` members, +9 nullable `risk_*`
  fields), `app/services/insight_service.py` (+`risk_repository` dependency,
  +2 builder methods, +2 `_TYPE_RANK` entries), `app/api/v1/insights.py`
  (`get_insight_service` gains a `RiskRepository`).
- New frontend feature: `apps/web/src/features/risks/` (types, API client,
  hooks, `RiskForm`, `RisksTable`, `RisksOverviewPage`). Extended:
  `features/insights/types/insights.ts`/`utils/presentation.ts`/
  `components/SignalDetailPanel.tsx` (the 2 new signal types), `app/
  routes.tsx` (+`/risks`), `components/layout/AppShell.tsx` (+nav link).
- 0 new external dependencies.
- Backend: +53 tests (18 domain, 4 model, 21 API CRUD/auth/audit/
  cross-tenant, 10 signal-integration), 669 total, all passing. `ruff
  check` and `pyright` (strict) both fully clean. Frontend: +10 component
  tests, 160 total, all passing. `tsc -b`, `oxlint`, and `npm run build`
  all clean (2 pre-existing warnings in `AuthContext.tsx` predate this
  phase).
- **A real gap was found by live verification, not the unit suite, in the
  Phase 12 audit trail this phase exercised for the first time in
  anger**: `AuditEventRead` never exposed `organization_id` at all — the
  underlying column was correctly populated and correctly org-scoped by
  `AuditEventRepository.list_filtered`, but the API response silently
  dropped the field. Not a Phase 13 regression (the column and its
  filtering predate this phase), but Phase 13's live-verification pass —
  inspecting a project's risk audit trail end-to-end — was the first time
  anyone actually looked at a raw `GET /api/v1/audit` response body since
  Phase 12 shipped. Fixed in `app/schemas/audit.py`; no dedicated
  regression test was added since the fix is a one-line schema field and
  every existing `test_audit.py` assertion already exercises the response
  shape.
- **Explicit multi-tenancy test**: `tests/api/test_risks.py` proves a
  client bound to Organization A cannot list, read, update, or delete a
  Project/Risk built directly in Organization B (404, not 403), and cannot
  create a Risk whose `owner_person_id` belongs to a different
  organization (also 404) — the pattern instruction #6 required for every
  new Phase 13 resource. This is also the first API-level (not just
  model-level) cross-tenant test in the repository; prior phases proved
  isolation at the model/DB-constraint level only.
- **Deferred, matching the phase boundary:** Risk Import/Export
  registration, an org-wide cross-project risk register, Stakeholder
  (§16) and Prioritization (§18) domain concepts, AI-generated risk
  assessments, any numeric risk score or probability/impact weighting.
- **Explicitly out of scope, not silently implemented:** the
  per-organization "last active Owner account" disable invariant ADR 0012
  flagged as a known gap — the user chose Risk Management over this
  candidate when the two were presented as alternatives; it remains
  exactly as documented in ADR 0012's Consequences, unaddressed.
