# ADR 0046: Phase 46 — Roadmap re-audit & next-build decision

- **Status:** Accepted (audit only — no code)
- **Date:** 2026-09-08

## Context

Phase 45 completed the Risk vs. Value quadrant — the last of the PRD's
five §15 visualizations. With the prioritization visualization backlog
fully closed, this phase re-audits the whole roadmap from evidence
rather than defaulting to whatever was most recently named, to determine
the single most defensible next build.

### Actual git state at the start of this audit

`git status --short` clean; `HEAD` = `1839674` ("Implement Phase 45 risk
vs. value quadrant"), matching `origin/main` exactly (0 ahead / 0
behind), branch `main`, `git diff --stat` empty. Phase 45 was already
committed and pushed (not "uncommitted" as a stale report might assume —
verified directly, not trusted).

### What was audited

CLAUDE.md §§4, 21, 26–40; `docs/roadmap.md`; `docs/architecture.md`;
`docs/domain-concepts.md`; `README.md`; every ADR through 0045;
`docs/PRD-phase-17-prioritization.md`. Directly against current source
(not merely re-reading prior ADR claims):

- `app/services/scenario.py::ScenarioService.delete` — confirmed a real,
  unconditional hard delete (`scenario_repository.delete(...)`, no
  soft-delete flag anywhere on `Scenario`).
- `app/models/scenario.py` / `scenario_priority_override.py` /
  `portfolio_snapshot.py` — FK `ondelete` behavior compared directly:
  `ScenarioOperation.scenario_id` and `ScenarioPriorityOverride.scenario_id`
  are both `CASCADE` (die with their scenario, by design — "deleting a
  scenario should delete only the scenario," but also *only ever* the
  scenario's own rows); `PortfolioSnapshot.framework_id` is `RESTRICT`,
  which only works in practice because `PrioritizationFramework` is
  never hard-deleted (soft-deleted via `is_active`) — the opposite of
  `Scenario`'s real, hard delete.
- `app/domain/authorization.py` — confirmed `Permission.RISK_READ` and
  `Permission.STAKEHOLDER_READ` are both inside `_READ_PERMISSIONS`
  (granted to every role, including Viewer — reads were never
  grant-scoped by Phase 11, only writes were).
- `apps/web/src/features/risks/views/RisksOverviewPage.tsx` and
  `features/stakeholders/views/StakeholdersOverviewPage.tsx` — both
  confirmed to require selecting exactly one project via
  `ProjectFilterPicker` before showing anything; neither has ever had an
  org-wide "every project's risks/stakeholders at once" view.
- `docs/roadmap.md`'s "Proposed, unscheduled" section, read in full —
  every named item there was individually re-verified rather than
  assumed still accurate.
- Known-limitations sections of ADRs 0031–0045, read in full — none
  names a limitation that rises to "the next feature," only bounded,
  deliberate trade-offs already accepted at the time.

## Completed functionality (summary)

Domain foundation, deterministic capacity engine, scenario what-if
planning, operational insights, import/export (7 core entities + Risk/
Stakeholder/Prioritization/ProjectDependency), skills & bottleneck
analysis, an optional AI interpretation layer (9 capabilities), auth/
RBAC/audit, instance-level authorization, organizations & multi-tenancy
(including a full deactivation/reactivation lifecycle and global
inactive-org awareness), risk management, stakeholder management, the
last-owner invariant, a five-framework prioritization engine with
dependency graph, portfolio snapshots + diff/trend, and **all five** of
the PRD's own §15 visualizations (dependency timeline, Capacity vs.
Priority, Risk vs. Value, plus WSJF breakdown and Priority vs. Effort
from earlier phases), a full membership/user/organization-settings admin
surface, an account-directory search/filter, and an Audit Log UI with
actor/date/action/resource-type filtering.

## Remaining work inventory

| Item | Category |
|---|---|
| Org-wide cross-project Risk register | **B — build-ready** |
| Org-wide cross-project Stakeholder register | **B — build-ready** |
| Scenario snapshots | **C — product-decision blocked** |
| Rank-over-time trend variant | **E — explicitly declined** (ADR 0024) |
| PostgreSQL concurrency verification | **D — architecture/infra blocked** |
| External integrations (Slack/Jira/Linear/Asana/ClickUp/Calendar) | **E — explicitly deferred** (CLAUDE.md §22) |
| SSO/OAuth | **E — explicitly deferred** |
| Billing/subscription | **E — explicitly deferred**, no schema exists |
| Organization hierarchies | **E — explicitly deferred** (ADR 0012 Consequences) |
| Chrome extension | **E — explicitly deferred** (CLAUDE.md §23) |
| Team→Project inheritance / Person-keyed / Scenario instance scoping | **E — deliberately retained** (ADR 0016; needs a new explicit ownership requirement to reopen) |
| Invitations, email verification, password reset | **E — no spec anywhere**, not requested |

## Prioritization status (explicit confirmation)

- **Capacity vs. Priority** — completed (Phase 42, ADR 0042).
- **Risk vs. Value** — completed (Phase 45, ADR 0045).
- **Audit Log UI** — completed (Phase 43, ADR 0043).
- **Audit Log filtering (action/resource type)** — completed (Phase 44, ADR 0044).
- **Scenario Snapshots** — still blocked; the specific, sharpened
  question (see below) is which lifecycle relationship a snapshot's
  reference to its source `Scenario` should have, since `Scenario`
  (unlike `PrioritizationFramework`) supports a genuine hard delete.
- **Rank-over-time** — still declined; no new evidence in this audit
  changes ADR 0024's reasoning (`rank_priority_results` still gives
  MoSCoW `rank=None`; a rank trend still conflates a project's own
  change with the portfolio around it). Not reopened.

## Candidate matrix

| Candidate | Current state | Product decision needed? | Architecture work? | Existing precedent? | Scope size | Recommendation |
|---|---|---|---|---|---|---|
| **Org-wide Risk register** | Named (ADR 0013 Consequences), unbuilt | No — a read-only cross-project list needs no new semantics | None — `RISK_READ` is already global; composes existing per-project reads client-side | Strong — Phase 45's `useRisksForProjects` is the exact bulk-composition shape needed; Phase 43's Audit Log UI is the exact "wrap existing data in a new read view" shape | Small–medium | **Recommended Phase 47** |
| Org-wide Stakeholder register | Named (ADR 0014 Consequences), unbuilt | No | None — same reasoning | Strong, identical shape | Small–medium | Natural follow-up phase after Risk register (mirrors the Members→Users, Phase 28→29, sequencing precedent), not bundled into the same phase |
| Scenario snapshots | Named, blocked | **Yes** — see decision below | Small once decided (one new table, matching `PortfolioSnapshot`'s own shape) | Strong (`PortfolioSnapshot`'s frozen-field technique) | Small once unblocked | Not recommended yet — blocked on a product decision only the user can make |
| PostgreSQL concurrency verification | Named, deferred | No | **Yes** — needs a real PostgreSQL deployment/CI target, not application code | N/A | N/A | Not next — infrastructure/ops work, not a user-facing product increment |
| Rank-over-time trend | Declined (ADR 0024) | N/A | N/A | N/A | N/A | Not recommended — stays closed, no new evidence |
| External integrations / SSO / billing / org hierarchy / Chrome extension | Explicitly deferred | Yes — each is a large, unscoped product area | Yes | None | Large | Not recommended — no explicit request, matches CLAUDE.md §32 |

## Recommended Phase 47

**Org-wide cross-project Risk register** — a new, read-only view
listing every `Risk` across every project in the active organization at
once (filterable by project, status, and exposure), answering the
question the current per-project-only Risks page cannot: "which
projects across this whole organization currently carry high-exposure
risk?" This is exactly the gap CLAUDE.md §5 ("Stakeholder visibility")
and §17 ("risk management should be continuous... not only during
project kickoff") already name, and the existing `risk_high_exposure`
Insights signal already computes the underlying fact per project without
anywhere to see it aggregated.

Not started this phase, per the brief's explicit instruction.

## Product decision required: Scenario Snapshots

The unresolved question is **not** whether historical scenario data is
valuable (that's already assumed by `PortfolioSnapshot`'s own existence)
— it is specifically: **what should a scenario snapshot's reference to
its source `Scenario` do when that `Scenario` is deleted**, given
`ScenarioService.delete` is a genuine, unconditional hard delete (unlike
`PrioritizationFramework`, which is only ever soft-deleted). Three
concrete, code-grounded options exist:

1. **`CASCADE`** — the snapshot is deleted along with its scenario. Simple, but defeats the entire purpose of a snapshot as a surviving historical record (the same purpose `PortfolioSnapshot` itself exists for).
2. **`RESTRICT`** — a scenario cannot be deleted while any snapshot references it. Preserves history perfectly, but silently changes existing `Scenario` deletion behavior (today, any scenario can always be deleted) in a way no one has asked for.
3. **Freeze the scenario's identifying fields into the snapshot at capture time (matching `PortfolioSnapshot.framework_name`'s own precedent) and let the FK be nullable / `SET NULL`** — the snapshot survives deletion intact and readable, `scenario_id` becomes `NULL` (or is never a live FK at all, just an informational value), and scenario deletion is completely unaffected either way.

This phase does not choose one — it is a real product decision about
whether scenario deletion should ever be blocked or altered by having
taken a snapshot, which only the user can make.

## Security / multi-tenancy considerations (for the recommended candidate)

An org-wide Risk register introduces **no** new authorization surface:
`Permission.RISK_READ` is already granted to every role and already
organization-scoped per request (verified directly this phase); the
per-project routes it would compose are the exact same, already-audited
routes the existing Risks page already calls. No new permission, no
grant-scoping change, no cross-organization exposure risk — a risk
belonging to another organization can never appear in any of the
composed per-project responses, the same guarantee every other
client-side-composed view in this codebase (Dependency Timeline,
Capacity vs. Priority, Risk vs. Value) already relies on.

## Documentation changes

- `docs/adr/0046-roadmap-reaudit.md` (this file, new).
- `CLAUDE.md` §39 — one new "Phase 46" entry recording this audit and
  its recommendation.
- `docs/roadmap.md` — the "Org-wide cross-project Risk and Stakeholder
  registers" bullet sharpened with this audit's findings; the Scenario
  Snapshots bullet sharpened with the exact FK-behavior question found
  this phase.
- `docs/architecture.md` — one new short paragraph recording the audit,
  matching Phase 41's own precedent for an audit-only phase.
- `README.md` — status line updated to Phase 46.
- `docs/domain-concepts.md` and `docs/openapi.json` — **not** touched;
  no genuine new domain concept was introduced and no API contract
  changed.

## Production-code impact

**None.** This phase changed documentation and this ADR only. No API
endpoint, migration, frontend component, permission, or domain concept
was added or modified.

## Confirmation

Phase 47 was **not** started. Nothing in this phase was committed or
pushed — see the Phase 46 Final Report for the exact git state.
