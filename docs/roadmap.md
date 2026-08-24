# Roadmap

This is the single place to see what CapacityOS has built and what's genuinely still open. **Completed phases** (0–16) are drawn directly from CLAUDE.md §39 and their ADRs — that section is the authoritative build order and this table should never drift from it. **Proposed future phases** are compiled from every deferral CLAUDE.md and the ADRs already named explicitly (§22 external integrations, §23 Chrome extension, §18 Prioritization, and the "Deferred items" paragraph at the end of CLAUDE.md §39) — nothing below was invented for this document. Their numbering and grouping are a proposal, not a commitment: this project's own history (see Phase 13's ADR) is that "what phase comes next" gets decided deliberately, by asking, not by assuming a pre-written list — treat "Phase 17" onward as provisional until CLAUDE.md §39 itself is amended to confirm it, the same way Phases 9–16 were each confirmed as they happened.

## Status legend

| Status | Meaning |
|---|---|
| ✅ Complete | Shipped, tested, documented, has an ADR (except where noted) |
| 🔜 Proposed next | Named by name in this doc's most recent revision as the next thing to build |
| 📋 Proposed, unscheduled | A real, named gap — not yet ordered or confirmed |

## Completed phases (0–16)

| Phase | Name | Key deliverable | ADR |
|---|---|---|---|
| 0 | Repository & architecture bootstrap | Monorepo structure, tooling, CI | [0001](adr/0001-phase-0-bootstrap.md) |
| 1 | Domain foundation | People, Teams, Projects, Availability, Allocations | [0002](adr/0002-phase-1-domain-foundation.md) |
| 2 | Deterministic capacity engine | `calculate_period_capacity`, working-hours/availability/allocation math, zero AI in the calculation path | [0003](adr/0003-phase-2-capacity-engine.md) |
| 3 | Core dashboard & planning views | Read-only team/person/project capacity views, consuming Phase 2 endpoints verbatim | — |
| 4 | Scenario planning | Hypothetical what-if operations over a baseline, no mutation of live data | [0004](adr/0004-phase-4-scenario-planning.md) |
| 5 | Operational insights | Deterministic, explainable decision-support signals (over-allocation, capacity risk, concentration, imbalance, pressure, scenario deltas) | [0005](adr/0005-phase-5-operational-insights.md) |
| 6 | Import / export | CSV/JSON portability, two-stage validate-then-apply | [0006](adr/0006-phase-6-import-export.md) |
| 7 | Skills & bottleneck analysis | Skill vs. total capacity, qualified-capacity/coverage, skill-gap signals plugged into Phase 5's pipeline | [0007](adr/0007-phase-7-skills-bottleneck-analysis.md) |
| 8 | AI insight layer | Provider-abstracted interpretation strictly downstream of the deterministic engine; app works fully with no AI configured | [0008](adr/0008-phase-8-ai-insight-layer.md) |
| 9 | Production readiness & observability | Structured logging, request correlation, health/readiness, config safety gate | [0009](adr/0009-phase-9-production-readiness.md) |
| 10 | Authentication, RBAC & audit | Session-cookie login, five-role permission model, persistent append-only audit trail | [0010](adr/0010-authentication-rbac-audit.md) |
| 11 | Instance-level resource authorization | `TeamAccessGrant`/`ProjectAccessGrant` — a Manager's write access is grant-scoped, not automatic org-wide | [0011](adr/0011-instance-level-resource-authorization.md) |
| 12 | Organizations & multi-tenancy | Every entity belongs to exactly one Organization; role moves to `OrganizationMembership`; cross-org access 404s, never 403s | [0012](adr/0012-organizations-multi-tenancy.md) |
| 13 | Risk management | Project-scoped risk register, derived (never stored) exposure, two new Insights signal types | [0013](adr/0013-phase-13-risk-management.md) |
| 14 | Stakeholder management | Project-scoped stakeholder register, influence/interest/decision-authority stored but never scored | [0014](adr/0014-phase-14-stakeholder-management.md) |
| 15 | Last-owner invariant | Every active Organization retains ≥1 Owner who can actually authenticate; closes a Phase 12 gap; atomic-guarded-UPDATE concurrency fix | [0015](adr/0015-last-owner-invariant.md) |
| 16 | Instance-authorization completion | Audited every remaining Phase 11 deferral (Team→Project inheritance, Person-keyed scoping, Scenario scoping) and deliberately retained each; closed a real cross-org test-coverage gap instead | [0016](adr/0016-instance-authorization-completion.md) |

**Tag:** [`v0.1-foundation`](https://github.com/blessingochuwa/capacityos/releases/tag/v0.1-foundation) marks Phases 0–16 complete.

## Proposed future phases

None of these have a confirmed number, order, or ADR yet — each should be confirmed (with the user, per this project's established practice) before work starts, exactly as Phases 13–16 each were.

### 🔜 Proposed next: Prioritization (CLAUDE.md §18)

When demand exceeds capacity, support explicit prioritization using value, strategic fit, urgency, cost, risk, dependency, and effort criteria. CLAUDE.md is explicit that no single framework (RICE, WSJF, MoSCoW, weighted scoring, cost-of-delay) is prescribed as universally correct — whichever is chosen, it must connect strategy to execution, preserve the rationale behind a decision, and (per this project's own recurring discipline) not become a second, competing calculation engine alongside Phase 2's deterministic capacity math.

### 📋 Proposed, unscheduled

- **Risk & Stakeholder Import/Export registration** — both Phase 13 and Phase 14 explicitly deferred registering their entity into the Phase 6 Import/Export system (ADR 0013/0014 Consequences).
- **Org-wide cross-project Risk and Stakeholder registers** — both entities are currently nested under one Project only; a register spanning every project in an organization was named but not built (ADR 0013/0014 Consequences).
- **Membership- / user-management UI** — every backend route for adding/removing members, changing roles, and disabling accounts (Phases 10/12/15) has existed API-only since Phase 12; no frontend page lists or manages them yet (ADR 0015/0016 Consequences).
- **External integrations foundation** (CLAUDE.md §22) — Slack, Jira, Linear, Asana, ClickUp, Google Calendar, via an isolated adapter layer (`External System → Integration Adapter → CapacityOS Internal Model → Domain Engine`) so vendor-specific logic never spreads into the domain layer. Deliberately not started in any phase through 16.
- **SSO / OAuth / external identity provider** — deferred since Phase 10 (session-cookie auth was chosen specifically because a self-hosted option was sufficient for that phase's scope).
- **Billing / subscription** — no concept exists anywhere in the schema or domain model (ADR 0012 Consequences).
- **Organization hierarchies / sub-organizations** — every organization is currently a flat, independent tenant (ADR 0012 Consequences).
- **Chrome extension** (CLAUDE.md §23) — explicitly deferred; when built, it must call the CapacityOS API rather than duplicate any business logic client-side.
- **PostgreSQL verification of the Phase 15 last-owner concurrency guard** — the atomic-guarded-`UPDATE` technique is expected to hold under PostgreSQL's isolation levels (it's portable SQL), but this was verified against SQLite's single-file writer serialization only; a real PostgreSQL deployment should confirm it before being relied on as a production guarantee (ADR 0015 Consequences).
- **Team→Project access-grant inheritance, Person-keyed instance scoping (WorkingSchedule/AvailabilityException/PersonSkill), Scenario instance scoping** — audited and *deliberately retained* as role-only by Phase 16 (ADR 0016), not merely unbuilt. Re-opening any of these requires a new, explicit product requirement naming the missing ownership concept CLAUDE.md would need to define first — not a default next step.

## Keeping this document current

Update this file whenever CLAUDE.md §39 gains a new confirmed phase (move it from "Proposed" to the completed table, link its ADR) or a proposed item's scope changes. If a phase is dropped or superseded, say so explicitly here rather than silently deleting the row — matching CLAUDE.md's own "do not silently remove deferred items" convention (§39's amendment history is the model to follow).
