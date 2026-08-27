# Roadmap

This is the single place to see what CapacityOS has built and what's genuinely still open. **Completed phases** (0–24) are drawn directly from CLAUDE.md §39 and their ADRs — that section is the authoritative build order and this table should never drift from it. **Proposed future phases** are compiled from every deferral CLAUDE.md and the ADRs already named explicitly (§22 external integrations, §23 Chrome extension, and the "Deferred items" paragraph at the end of CLAUDE.md §39) — nothing below was invented for this document. Their numbering and grouping are a proposal, not a commitment: this project's own history (see Phase 13's ADR) is that "what phase comes next" gets decided deliberately, by asking, not by assuming a pre-written list — treat anything below "Completed phases" as provisional until CLAUDE.md §39 itself is amended to confirm it, the same way Phases 9–20 were each confirmed as they happened.

## Status legend

| Status | Meaning |
|---|---|
| ✅ Complete | Shipped, tested, documented, has an ADR (except where noted) |
| 🚧 v1 shipped | A deliberately reduced first slice is complete; a named, scoped remainder is proposed below, not dropped |
| 🔜 Proposed next | Named by name in this doc's most recent revision as the next thing to build |
| 📋 Proposed, unscheduled | A real, named gap — not yet ordered or confirmed |

## Completed phases (0–24)

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
| 17 🚧 | Prioritization engine (v1 slice) | RICE + Weighted Scoring rank a portfolio against an organization-chosen framework; a score is always derived at read time, never stored. First phase preceded by a [PRD](PRD-phase-17-prioritization.md), confirmed with the user before implementation. | [0017](adr/0017-prioritization-engine.md) |
| 18 🚧 | Prioritization frameworks & dependencies (Phase 17b slice) | ICE/WSJF/MoSCoW formulas complete the framework set; a Weighted Scoring framework's criteria can be edited after creation; `ProjectDependency` (blocks/related/enables) with cycle detection, plus a Dependency Graph view. | [0018](adr/0018-prioritization-frameworks-and-dependencies.md) |
| 19 🚧 | AI priority explanation | A fifth Phase 8 AI capability (`explain-priority`), reusing `AIContextBuilder`/`AIService`/grounding unchanged — explains an existing `ProjectPriorityScore` without ever recalculating it. | [0019](adr/0019-ai-priority-explanation.md) |
| 20 🚧 | Scenario-vs-baseline prioritization comparison | Resolves the Phase 19-flagged product decision: a Scenario can declare explicit, hypothetical criterion overrides (never auto-derived from capacity data); baseline and scenario rankings are both computed through the unchanged Phase 17/18 scoring engine and diffed. | [0020](adr/0020-scenario-priority-comparison.md) |
| 21 | Portfolio snapshots | An explicit, user-triggered, immutable point-in-time saved ranking (the PRD's own original §8 proposal). `PortfolioSnapshotService.create` freezes `ProjectPriorityScoreService.rank_portfolio`'s result verbatim — framework name/type and every entry's project name/score/rank/breakdown — so a later rename, re-score, or deletion never retroactively changes an already-taken snapshot. No PATCH/DELETE — immutable and append-only, matching `AuditEvent`. | [0021](adr/0021-portfolio-snapshots.md) |
| 22 | Portfolio snapshot diff/trend | Compares two immutable Phase 21 snapshots — entered/left/changed/unchanged per project, same-framework-only (rejected with 422 otherwise). Pure computation over already-frozen data (`app/domain/portfolio_snapshot.py::compare_snapshot_entries`) — no scoring engine involved, nothing persisted, 0 new tables. | [0022](adr/0022-portfolio-snapshot-comparison.md) |
| 23 | AI snapshot comparison explanation | A sixth Phase 8 AI capability (`explain-snapshot-comparison`), reusing `AIContextBuilder`/`AIService`/grounding unchanged — explains an existing Phase 22 snapshot comparison without ever recalculating its status/rank/score/category. | [0023](adr/0023-ai-snapshot-comparison-explanation.md) |
| 24 | Multi-snapshot portfolio trend visualization | A score-over-time line chart across 2+ Phase 21 snapshots, built entirely from the existing `GET /api/v1/prioritization/snapshots` response — 0 backend changes. `buildSnapshotTrend` (frontend, pure, unit-tested) never recomputes a score and never fabricates a value for a project absent from a snapshot. A rank-over-time variant was audited and explicitly not selected (a MoSCoW score/rank is always null; rank conflates a project's own change with the portfolio around it). See "Proposed next" below for the still-named remainder. | [0024](adr/0024-portfolio-snapshot-trend.md) |

**Tag:** [`v0.1-foundation`](https://github.com/blessingochuwa/capacityos/releases/tag/v0.1-foundation) marks Phases 0–16 complete (Phases 17–24 landed after the tag).

## Proposed future phases

None of these have a confirmed number, order, or ADR yet — each should be confirmed (with the user, per this project's established practice) before work starts, exactly as Phases 13–24 each were.

### 🔜 Proposed next: the rest of Prioritization

Phases 17-24 together shipped a deliberately reduced slice of the original Phase 17 PRD (each confirmed with the user before implementation, per CLAUDE.md §31's "smallest complete slice"). Still named, scoped, not dropped:

- The five Recharts visualizations the PRD's own §15 actually names (Priority vs. Effort scatter, Capacity vs. Priority matrix, Risk vs. Value quadrant, WSJF breakdown, dependency timeline) — the Phase 24 audit confirmed the multi-snapshot trend chart is *not* one of these five; it was only ever named in later ADRs' own deferred-items lists.
- An AI interpretation of the Phase 20 scenario-vs-baseline comparison — Phase 20's own brief was explicit that AI may only interpret an established deterministic comparison, never be its source, and left this for a future phase to consider deliberately rather than bundling it in speculatively.
- **Scenario snapshots** — a snapshot of a scenario's hypothetical (rather than baseline) ranking, within a `PortfolioSnapshot`'s conceptual reach but genuinely ambiguous: `Scenario` (unlike `PrioritizationFramework`) supports a real, non-soft delete, so what happens to a scenario snapshot when its scenario is deleted needs a product decision before this is buildable (audited and explicitly not selected for Phase 22, re-confirmed still open by the Phase 23 and Phase 24 audits — see ADR 0022's Context).
- A rank-over-time or toggleable score/rank variant of the Phase 24 trend chart — audited and explicitly not selected for Phase 24 (a rank trend risks conflating a project's own change with a sibling project entering/leaving the ranking, and a MoSCoW framework has no rank at all — see ADR 0024's Decision).

An AI explanation of a Phase 22 snapshot comparison is resolved as of Phase 23 — see [ADR 0023](adr/0023-ai-snapshot-comparison-explanation.md). A multi-snapshot score-over-time trend chart is resolved as of Phase 24 — see [ADR 0024](adr/0024-portfolio-snapshot-trend.md). See [ADR 0020](adr/0020-scenario-priority-comparison.md)'s, [ADR 0021](adr/0021-portfolio-snapshots.md)'s, [ADR 0022](adr/0022-portfolio-snapshot-comparison.md)'s, [ADR 0023](adr/0023-ai-snapshot-comparison-explanation.md)'s, and [ADR 0024](adr/0024-portfolio-snapshot-trend.md)'s Consequences for the authoritative list.

### 📋 Proposed, unscheduled

- **Risk, Stakeholder, Prioritization & Project Dependency Import/Export registration** — Phase 13 and Phase 14 explicitly deferred registering their entity into the Phase 6 Import/Export system (ADR 0013/0014 Consequences); Prioritization joined this same deferred list in Phase 17, `ProjectDependency` in Phase 18 (ADR 0017/0018 Consequences), and `PortfolioSnapshot` in Phase 21 (ADR 0021 Consequences). A Phase 22 audit of the actual import/export code confirmed the gap directly (`ImportEntityType` has 10 members, none Risk or Stakeholder) and found a further open question: neither entity has a Person/Project-style natural identity key for CSV upsert-matching, which would need its own decision before implementation (see ADR 0022's Context).
- **Org-wide cross-project Risk and Stakeholder registers** — both entities are currently nested under one Project only; a register spanning every project in an organization was named but not built (ADR 0013/0014 Consequences).
- **Membership- / user-management UI** — every backend route for adding/removing members, changing roles, and disabling accounts (Phases 10/12/15) has existed API-only since Phase 12; no frontend page lists or manages them yet (ADR 0015/0016 Consequences). Re-confirmed ready-to-build (fully backend-complete, zero frontend surface) by the Phase 22 audit, but not selected for that phase (ADR 0022's Context).
- **External integrations foundation** (CLAUDE.md §22) — Slack, Jira, Linear, Asana, ClickUp, Google Calendar, via an isolated adapter layer (`External System → Integration Adapter → CapacityOS Internal Model → Domain Engine`) so vendor-specific logic never spreads into the domain layer. Deliberately not started in any phase through 17.
- **SSO / OAuth / external identity provider** — deferred since Phase 10 (session-cookie auth was chosen specifically because a self-hosted option was sufficient for that phase's scope).
- **Billing / subscription** — no concept exists anywhere in the schema or domain model (ADR 0012 Consequences).
- **Organization hierarchies / sub-organizations** — every organization is currently a flat, independent tenant (ADR 0012 Consequences).
- **Chrome extension** (CLAUDE.md §23) — explicitly deferred; when built, it must call the CapacityOS API rather than duplicate any business logic client-side.
- **PostgreSQL verification of the Phase 15 last-owner concurrency guard** — the atomic-guarded-`UPDATE` technique is expected to hold under PostgreSQL's isolation levels (it's portable SQL), but this was verified against SQLite's single-file writer serialization only; a real PostgreSQL deployment should confirm it before being relied on as a production guarantee (ADR 0015 Consequences).
- **Team→Project access-grant inheritance, Person-keyed instance scoping (WorkingSchedule/AvailabilityException/PersonSkill), Scenario instance scoping** — audited and *deliberately retained* as role-only by Phase 16 (ADR 0016), not merely unbuilt. Re-opening any of these requires a new, explicit product requirement naming the missing ownership concept CLAUDE.md would need to define first — not a default next step.

## Keeping this document current

Update this file whenever CLAUDE.md §39 gains a new confirmed phase (move it from "Proposed" to the completed table, link its ADR) or a proposed item's scope changes. If a phase is dropped or superseded, say so explicitly here rather than silently deleting the row — matching CLAUDE.md's own "do not silently remove deferred items" convention (§39's amendment history is the model to follow).
