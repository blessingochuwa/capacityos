# PRD: Phase 17 — Prioritization Engine & Decision Framework

- **Status:** Draft — needs sign-off before implementation starts
- **Author:** Claude (drafted per user request), for review
- **Scope:** CLAUDE.md §18 ("Prioritization and Product Management")

This is a PRD, not an ADR. Every prior phase (0–16) extended or hardened
infrastructure that already existed one layer down (a new entity on the
existing Person/Project/Organization spine, a new grant type on the
existing authorization spine). Phase 17 is the first phase that is a new
*product module* — a whole decision-making surface with its own vocabulary,
its own math, and its own frontend section. That warrants agreeing on the
shape of the thing before writing a single model. See CLAUDE.md §31: "For
complex or ambiguous work, use a planning-first approach and confirm major
architectural changes before implementation."

**This document ends with a list of specific open questions. Nothing below
is a final decision — implementation should not start until those are
answered.**

---

## 1. Problem statement

CapacityOS today can tell an operator *what is true*: who has capacity, who
is over-allocated, which skills are scarce, which risks are live, which
projects are demanding the most. It cannot yet tell them *what to do about
it* when demand exceeds capacity — CLAUDE.md §18 names this gap directly:

> When demand exceeds capacity, the system should support explicit
> prioritization... Prioritization should connect strategy to execution
> rather than simply producing a ranked list.

Phase 17 builds that layer, on top of — never duplicating — the
deterministic facts Phases 2/5/7/13 already compute.

## 2. Product vision

> **"Given limited people, time, and capacity — what should this
> organization work on first?"**

This is explicitly **not** task management (no tickets, no kanban-per-task,
no sprint boards). It is **portfolio-level operational prioritization**:
ranking *Projects* — the existing planning unit — against organization-
chosen criteria, informed by the facts the rest of the system already
produces.

## 3. Explicit non-goals

- **No universal framework.** CLAUDE.md §18: "Do not prescribe one
  prioritization framework as universally correct." Every organization
  picks its own framework(s); none is a hardcoded default winner.
- **AI never generates a score.** Matches CLAUDE.md §4's existing rule for
  capacity math, extended here: AI explains an already-computed ranking
  (why A beat B, which criterion drove it, which inputs are missing); it
  never produces the number itself. This is the same
  facts → deterministic engine → signals → AI interpretation pipeline
  Phase 8 already established for Insights — prioritization scores are
  just a new kind of fact at the bottom of that pipeline, not a new AI
  capability.
- **No invented risk/priority multipliers.** Mirrors Risk's own precedent
  (`app/domain/risk.py::calculate_risk_exposure` — an explicit 3×3 lookup
  table, never a multiplication) and CLAUDE.md §17's "do not create risk
  scores that imply false precision," generalized: nothing in this phase
  invents a formula a named framework didn't already define.
- **Not a redesign of Project.** Project remains exactly what it is today;
  prioritization data hangs off it, the same way Risk and Stakeholder do.
- **Not a second capacity engine.** Every capacity/utilization/skill-
  coverage/risk-exposure number a framework's criteria consume is read
  from the existing `CapacityService`/`InsightService`/`SkillCapacityService`/
  `app/domain/risk.py` — never recomputed here.

## 4. Core architectural principle: Facts vs. Frameworks

Two things that must never be conflated:

- **Facts** — capacity, utilization, skill coverage, risk exposure,
  dependencies, effort, deadlines. Already deterministic, already
  computed by Phases 2/5/7/13. Read-only inputs to this phase.
- **Decision frameworks** — an organization-chosen *method* for turning
  facts (plus human judgment criteria a fact can't supply, like "Reach" or
  "Business Value") into a ranking. Phase 17 builds the framework layer and
  the glue that lets a framework pull in facts; it never becomes a second
  source of truth for the facts themselves.

## 5. Framework model

The five requested frameworks are not five unrelated things — four of them
are the *same* underlying shape (a set of named, weighted/scaled criteria
combined into a numeric score), and one (MoSCoW) is categorically
different. Recognizing this now avoids building five parallel systems.

### 5.1 The numeric-scoring family: RICE, ICE, WSJF, Weighted Scoring

All four are: a fixed or custom list of **criteria**, each with a defined
input scale, combined by a **named formula** into a single number.

| Framework | Criteria | Formula |
|---|---|---|
| RICE | Reach, Impact, Confidence, Effort | `(Reach × Impact × Confidence) / Effort` |
| ICE | Impact, Confidence, Ease | `(Impact + Confidence + Ease) / 3` (or product — see Open Questions) |
| WSJF | Business value, Time criticality, Risk reduction/Opportunity enablement, Job size | `(Business value + Time criticality + RR/OE) / Job size` |
| Weighted Scoring | Organization-defined criteria, each with a user-set weight | `Σ (criterion_value × criterion_weight)` |

**Proposed design**: one generic engine, not four. A `PrioritizationFramework`
row has a `framework_type` (RICE/ICE/WSJF/WEIGHTED) that selects which
**pure function** in `app/domain/prioritization.py` combines its criteria —
RICE/ICE/WSJF's criteria and formula are **fixed** by the framework
definition itself (an organization can't redefine what "Reach" means in
RICE, only enable/use it), while Weighted Scoring's criteria are fully
organization-defined (name, weight, scale). All four share the same
`PrioritizationCriterion`/`ProjectPriorityScore` storage shape; only the
combining function differs, selected by `framework_type` — exactly the
"explicit lookup, never invented" discipline `calculate_risk_exposure`
already established, generalized to "look up the right named formula for
this framework type," not "invent a formula."

### 5.2 MoSCoW: categorical, not numeric — deliberately no invented score

MoSCoW (Must/Should/Could/Won't) does not produce a number, and forcing one
onto it (e.g., "Must = 4, Should = 3...") would be exactly the false-
precision CLAUDE.md §17 warns against generalized to a new domain. **Proposed
design**: MoSCoW is its own `framework_type`; a MoSCoW-scored project has a
single `category` value, not a numeric score. The Portfolio Priority Board
(§10) renders it as four columns (a Kanban-style board), not a single
sorted list — ranking *within* a column needs a secondary, explicit
tiebreaker (see Open Questions).

## 6. Proposed domain entities

All organization-scoped (Phase 12 pattern: direct `organization_id`,
repository-enforced). Draft shape, not final:

- **`PrioritizationFramework`** — `organization_id`, `name`,
  `framework_type` (RICE/ICE/WSJF/MOSCOW/WEIGHTED), `is_active`,
  timestamps. One organization may have several active frameworks
  (e.g., RICE for feature work, WSJF for platform work) — "compare
  frameworks" (§10) means comparing rankings *of the same portfolio* under
  two different framework instances.
- **`PrioritizationCriterion`** — belongs to a `PrioritizationFramework`.
  For RICE/ICE/WSJF: pre-seeded, fixed rows (not user-editable — see Open
  Questions) matching the table in §5.1. For Weighted Scoring: fully
  organization-defined (`name`, `weight`, `scale_min`/`scale_max`). For
  MoSCoW: none (category is stored directly on the score).
- **`ProjectPriorityScore`** — `organization_id`, `project_id`,
  `framework_id`, one row per (project, framework) pair (a project can be
  scored under multiple frameworks at once). Stores the **input values**
  per criterion (a JSON map or a child `ProjectPriorityCriterionValue`
  table — see Open Questions) — never the computed total. `confidence`
  (mirrors RICE's own named criterion where applicable, or a general
  "how complete are these inputs" indicator elsewhere), `missing_inputs`
  (which criteria have no value yet — the total score cannot be computed,
  and must say so, not silently treat a missing input as zero).
  **The computed score/rank is never a stored column** — same "compute at
  read time, never cache" discipline `Risk.exposure` and every Scenario
  result already follow (ADR 0004: "no caching... results are never stale
  relative to production data"). Only the human-entered *inputs* are
  facts worth persisting; the *score* is a pure function of
  (inputs, framework, current facts) and must always be freshly derived
  so it can never drift from the criteria it depends on.
- **`ProjectDependency`** — `organization_id`, `from_project_id`,
  `to_project_id`, `dependency_type` (`blocks` / `related` / `enables`).
  `blocked_by` is **not** a stored type — it is the reverse query of
  `blocks` (storing both directions would let them disagree with each
  other, an integrity problem no constraint can fully prevent). `related`
  is symmetric (order shouldn't matter for display, though the row itself
  is still directional in storage — see Open Questions on de-duplication).
  Both projects must resolve within the acting organization (mirrors
  Allocation's person/project pattern).
- **`PortfolioSnapshot`** — an explicit, user-triggered "save today's
  computed ranking" record: `organization_id`, `framework_id`, `taken_at`,
  and the ranked project list with each project's computed score *as of
  that moment*, stored as a genuine historical record (like `AuditEvent`),
  **never read back as an input to a live computation**. This is
  deliberately different from caching — live views (§10's "rank portfolio")
  always compute fresh; a snapshot is only created by an explicit action
  ("save this ranking"), for trend/history purposes, and is immutable once
  taken.
- **Review history**: proposed as reuse of the existing `AuditEvent`
  infrastructure (framework changes, score changes) rather than a new
  table — see §12. A dedicated "review history" table is only justified if
  audit events turn out to be insufficient for the frontend's needs (see
  Open Questions).

No changes to `Project` itself — this repeats CLAUDE.md's own instruction
in the phase brief.

## 7. Dependency graph

- Directed edges (`blocks`, `enables`) plus one symmetric type (`related`).
- **Cycle detection**: a pure function in `app/domain/prioritization.py`
  (DFS-based, no I/O — same module discipline as every other
  `app/domain/*.py` file), run against the full set of `blocks` edges for
  an organization before a new edge is persisted. `enables`/`related` are
  proposed as **not** cycle-checked (they don't imply a strict ordering
  the way `blocks` does) — see Open Questions.
- A rejected cycle is a `DomainValidationError` → 422 (existing
  convention), not a new error type.
- The full graph is exposed read-only (`GET .../dependency-graph`) for the
  frontend's Dependency Graph view; it is never auto-derived into
  priority scores (a project doesn't get a higher/lower score merely for
  having dependents — that's a `related` fact a human weighs via a
  criterion like "Opportunity enablement" in WSJF, not something this
  phase invents an automatic rule for).

## 8. Integration points — all read-only consumption, nothing recomputed

- **Capacity** (Phase 2): remaining capacity, over-allocation, project
  demand — read via the existing `CapacityService` the same way Insights
  and AI already do.
- **Skills** (Phase 7): coverage/gap facts via `SkillCapacityService`.
- **Risks** (Phase 13): `exposure` (already derived, never recomputed
  here) as an optional criterion input for frameworks that use it (e.g., a
  Weighted Scoring criterion literally named "Risk," populated from
  `calculate_risk_exposure`) — proposed as **not** an automatic score
  modifier; a criterion must be explicitly configured to consume it (the
  phase brief: "No invented risk multipliers. Use explicit framework
  configuration").
- **Stakeholders** (Phase 14): read-only context surfaced *alongside* a
  score (who cares about this project, what their decision authority is)
  — the phase brief is explicit that stakeholders "do not automatically
  change priority," so no stakeholder field feeds any formula.
- **Scenarios** (Phase 4): "if we accept this project, how does portfolio
  priority change?" — proposed as a **derived comparison, not a new
  calculation**: compute the portfolio ranking twice (once against
  baseline project/allocation facts, once against the scenario's
  hypothetical facts via the existing `ScenarioCalculationService`) and
  diff the two orderings (movement per project). No scenario-specific
  scoring logic; the same ranking function runs against two different
  fact sets it's already given.

## 9. AI integration

Extends the existing `AIContextBuilder`/`AIService` pattern (Phase 8) —
not a new AI subsystem:

- New `AIPriorityContext` (mirrors `AIInsightContext`): the computed
  ranking, each project's criterion breakdown, missing inputs, and the
  scenario comparison delta if applicable — all already-computed facts,
  never raw model rows.
- New grounding allow-list entries (`("priority_score", project_id)`,
  `("dependency", edge_id)`) added to the existing `known_references()`
  mechanism (Phase 8's citation-checking gate) — no change to how
  grounding itself works, only what it's allowed to cite.
- `AI_USE` permission, unchanged — no new permission needed for read-only
  explanation.
- Explicitly required test (per the phase brief's own Live Verification
  step 10): a fixture proving a manipulated/malicious criterion note (e.g.
  a prompt-injection string in a "notes" field) cannot cause the AI
  explanation to cite a project *not* in the computed ranking — same
  grounding-enforcement test shape Phase 8 already has for Insights.

## 10. Proposed API surface

Mirrors existing nesting conventions exactly (frameworks are org-level,
scores/dependencies are project-nested, matching Risk/Stakeholder):

```text
POST   /api/v1/organizations/{org_id}/prioritization/frameworks
GET    /api/v1/organizations/{org_id}/prioritization/frameworks
GET    /api/v1/organizations/{org_id}/prioritization/frameworks/{id}
PATCH  /api/v1/organizations/{org_id}/prioritization/frameworks/{id}
DELETE /api/v1/organizations/{org_id}/prioritization/frameworks/{id}   (soft-delete via is_active, matching Skill's precedent)

POST   /api/v1/projects/{project_id}/priority-scores
GET    /api/v1/projects/{project_id}/priority-scores
PATCH  /api/v1/projects/{project_id}/priority-scores/{id}
DELETE /api/v1/projects/{project_id}/priority-scores/{id}

GET    /api/v1/organizations/{org_id}/prioritization/portfolio?framework_id=...          (ranked list; grouped-by-category for MoSCoW)
GET    /api/v1/organizations/{org_id}/prioritization/portfolio/compare?framework_ids=...  (same portfolio under 2+ frameworks)
GET    /api/v1/organizations/{org_id}/prioritization/portfolio/compare-scenario?scenario_id=&framework_id=

POST   /api/v1/projects/{project_id}/dependencies
GET    /api/v1/projects/{project_id}/dependencies
DELETE /api/v1/projects/{project_id}/dependencies/{id}
GET    /api/v1/organizations/{org_id}/prioritization/dependency-graph

POST   /api/v1/organizations/{org_id}/prioritization/snapshots
GET    /api/v1/organizations/{org_id}/prioritization/snapshots

POST   /api/v1/ai/explain-priority   (extends the existing /api/v1/ai/* router, mirrors explain-signal)
```

## 11. Proposed authorization

Reuses the existing `ROLE_PERMISSIONS`/`require_permission`/
`require_project_access` machinery — no parallel system:

- **`Permission.PRIORITIZATION_MANAGE`** (new, Owner/Admin only) —
  framework create/update/delete. Mirrors `ORGANIZATION_MANAGE`/
  `MEMBERSHIP_MANAGE`'s precedent: an org-wide configuration surface,
  restricted tighter than ordinary write access. The phase brief is
  explicit ("Owners/Admins manage organization frameworks") that this is
  *not* Manager-level, unlike Skill's org-wide-but-Manager-writable
  precedent — a deliberate difference, not an oversight, because a
  framework change silently reshuffles every project's rank org-wide.
- **`Permission.PRIORITIZATION_READ`** — every role (rankings, dependency
  graph, snapshots) — matches every other `*_READ` permission's
  all-roles-including-Viewer precedent.
- **`Permission.PRIORITIZATION_SCORE`** (new) — Manager+, gated by
  `require_project_access` on the specific project being scored (the
  brief: "Managers can score projects they manage") — exactly
  `Risk`/`Stakeholder`'s existing shape, not a new mechanism.
- Dependency edges: proposed to require `PRIORITIZATION_SCORE`-equivalent
  project access on the **`from_project`** side (see Open Questions on
  whether the `to_project` side also needs a grant).

## 12. Audit

No new audit mechanism — reuses `AuditService`/`AuditEvent` exactly:

- `prioritization_framework.create/update/delete` — metadata: changed
  criteria **names and weights only** (the brief: "Do not log sensitive
  notes" — matches Risk/Stakeholder's existing "changed field names, never
  free-text values" convention exactly, see
  `test_updating_a_risk_audit_event_never_carries_free_text_values`).
- `project_priority_score.create/update/delete`.
- `project_dependency.create/delete`.
- `portfolio_snapshot.create`.
- Rejections (cycle detected, invariant violations) follow the existing
  precedent (ADR 0015): **not** separately audited — the structured
  application log already captures a `DomainValidationError` at INFO,
  matching every other business-rule rejection in the codebase.

## 13. Import / Export

**Proposed: defer, matching Phase 13/14's own precedent exactly** (ADR
0013/0014: "not specified; deferred... for a new entity that wasn't
explicitly asked for"). Prioritization data is even less naturally
tabular than Risk/Stakeholder (framework criteria are structured
sub-objects, not flat columns), and CLAUDE.md doesn't ask for it. Document
this as a deliberate deferral in ADR 0017, matching the brief's own
fallback instruction ("Otherwise document the deferral").

## 14. Frontend (`features/prioritization/`)

Reuses the existing design system (`components/ui/*`) and TanStack Query
data pattern — no new state-management approach. Proposed views, roughly
in build order (see §16 slice recommendation):

1. **Portfolio Priority Board** — ranked list (numeric frameworks) or
   Kanban columns (MoSCoW).
2. **Priority Explanation Panel** — per-project criterion breakdown +
   optional AI explanation, opened from the board.
3. **Project Scoring Drawer** — the score-entry form for a single project
   under a single framework.
4. **Framework Builder** — Owner/Admin-only, create/edit a framework's
   criteria and weights.
5. **Scenario Comparison** — baseline vs. scenario ranking, movement per
   project.
6. **Dependency Graph** — visualize/edit `blocks`/`related`/`enables`
   edges.

## 15. Visualizations (Recharts, matching the existing dataviz skill's
palette/discipline)

- Priority vs. Effort scatter plot.
- Capacity vs. Priority matrix.
- Risk vs. Value quadrant.
- WSJF breakdown (stacked bar of the four inputs).
- Portfolio ranking table (not really a "visualization," but listed
  in-scope by the brief — a sortable table component).
- Dependency timeline.

## 16. Recommended delivery slice (this is the part most likely to need
your input)

The brief's full scope — 5 frameworks, full dependency graph with cycle
detection, scenario comparison, risk/stakeholder integration, AI
explanation, 6 API resource groups, 6 frontend views, 6 chart types,
tests across every layer — is large enough that CLAUDE.md §31's own
instruction ("implement the smallest complete slice") argues against
building all of it in one pass with no checkpoint. **Proposed v1 slice**
(everything else explicitly deferred to a "Phase 17b," not dropped):

- Domain engine: Weighted Scoring + RICE only (the two simplest — Weighted
  Scoring proves the generic engine, RICE proves the fixed-formula path).
  ICE/WSJF/MoSCoW follow once the shape is proven, since §5.1 shows they
  fit the same engine.
- Entities: `PrioritizationFramework`, `PrioritizationCriterion`,
  `ProjectPriorityScore` (no `ProjectDependency`/`PortfolioSnapshot` yet).
- API: framework CRUD, score CRUD, `GET .../portfolio` ranking only (no
  compare, no scenario-compare, no dependency graph, no snapshots yet).
- Frontend: Portfolio Priority Board + Project Scoring Drawer + Framework
  Builder only.
- No AI integration yet (added once the ranking itself is stable and
  real).
- Full authorization, audit, and IDOR test coverage from day one —
  security discipline is never part of a "later" slice.

If you'd rather I build the full brief in one pass instead, say so and
I'll drop this section.

## 17. Testing plan (applies regardless of slice size)

- `tests/domain/test_prioritization.py` — every framework formula, cycle
  detection, MoSCoW category logic — pure function tests, no DB.
- `tests/services/test_prioritization.py` — service-level orchestration,
  missing-input handling.
- `tests/api/test_prioritization_frameworks.py`,
  `test_prioritization_scores.py` — CRUD, cross-org IDOR
  (`tests/api/test_cross_organization_boundaries.py`'s established
  pattern), Manager-without-grant/with-grant (`test_risks.py`'s pattern).
- Dependency graph cycle tests, including the multi-hop case (A→B→C→A).
- Scenario-comparison tests reusing `ScenarioCalculationService` test
  fixtures.
- AI grounding test proving an ungrounded reference is rejected (Phase 8's
  existing pattern).
- Frontend: loading/empty/error/authorized/unauthorized states per view,
  matching every existing `features/*` test convention.

## 18. Documentation

`docs/adr/0017-prioritization-engine.md` once decisions are final (this
PRD is not that ADR — the ADR records what was actually built and why,
written after implementation, matching every prior phase's pattern).
Update CLAUDE.md §39, README, `docs/architecture.md`,
`docs/domain-concepts.md`, `docs/roadmap.md` at that point.

---

## Open questions requiring your confirmation before implementation starts

1. **Delivery slice** (§16): build the reduced v1 slice first, or the full
   brief in one pass?
2. **ICE formula**: sum-then-average or product? Community usage is
   inconsistent; picking one is a real, stated decision either way.
3. **Are RICE/ICE/WSJF's criteria ever organization-editable** (e.g., can
   an org rename "Reach" or change its scale), or are they permanently
   fixed definitions and only Weighted Scoring is customizable?
4. **`ProjectPriorityScore` storage shape**: one JSON column of
   `{criterion_id: value}`, or a normalized `ProjectPriorityCriterionValue`
   child table? JSON is simpler; a child table is more queryable
   (e.g., "show me every project scored below 5 on Confidence") and more
   consistent with this codebase's general preference for normalized
   columns over JSON blobs (`ScenarioOperation.payload` is the one
   existing JSON-column precedent, and it's typed via a Pydantic
   discriminated union at the schema layer, not queried directly).
5. **MoSCoW tiebreak**: how is order *within* a category (e.g., which
   "Must" comes first) determined — manual drag-to-reorder (a stored
   `sequence` field), most-recently-updated, or combination with a second
   numeric framework?
6. **Dependency cycle scope**: cycle-check `blocks` only, or `enables` too?
7. **Dependency authorization**: does creating a `blocks`/`related`/
   `enables` edge require project-write access on both projects, or just
   the `from_project`?
8. **`PortfolioSnapshot` — needed in v1 at all**, or is "compare two live
   framework rankings" (§10) sufficient without a stored historical
   record? (Affects whether item 16 of the brief's "review history" /
   "portfolio snapshots" entities are in v1 scope.)
9. **Cost-of-delay** — CLAUDE.md §18 names it as a "may be supported"
   framework; your Phase 17 brief doesn't request it. Confirm it stays
   out of scope entirely (not even v2), or should it join the deferred
   list explicitly?

I'd suggest answering these (or telling me to just use my recommended
defaults throughout) before I start on models/migrations.
