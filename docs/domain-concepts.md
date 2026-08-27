# Domain Concepts (Phase 1)

This document explains the entities introduced in Phase 1 and, most importantly, the distinction CLAUDE.md requires be made explicit:

> **WORKING SCHEDULE ≠ AVAILABILITY ≠ ALLOCATION ≠ CAPACITY**

None of these four are the same thing, and none of them is "capacity." Capacity is a *derived* concept that a future phase computes from the other three — it is not stored anywhere in Phase 1.

## The four concepts, in plain language

**Working schedule** — "When does this person *normally* work?"
A recurring weekly pattern (e.g. Mon–Fri, 8 hours/day, or a 4-day week). It does not know about holidays, leave, or what projects exist. It answers a question about the person's baseline rhythm, full stop.

**Availability exception** — "Is there a *deviation* from that normal pattern during a specific period?"
Leave, a public holiday, training, a temporarily reduced schedule. It modifies (overrides) the working schedule for a date range — it does not replace the working schedule permanently, and it says nothing about what work is planned.

**Allocation** — "What work has been *planned* for this person, on this project, during this period?"
This is demand, not time. An allocation can exist even if it would overload the person — Phase 1 deliberately does not check that (see "What Phase 1 does NOT compute" below).

**Capacity** — "Given the above three, how much room does this person actually have?"
This is arithmetic over the other three (something like: working-schedule hours, minus availability-exception reductions, minus allocated hours, over a given period) — and it belongs entirely to a future capacity-engine phase (CLAUDE.md §10, §39 Phase 2). Phase 1 stores no `remaining_hours`, `utilization`, or similar field anywhere, on purpose (CLAUDE.md §1: "Do not store a mutable `available_hours` field as the source of truth").

## Entities

Every entity below belongs to exactly one `Organization` (Phase 12 — see
"Organizations & Multi-Tenancy" at the end of this document) via a direct
`organization_id` foreign key. That boundary is orthogonal to the four
concepts this document is otherwise about: it answers "whose data is this,"
never "how much capacity does this represent."

| Entity | Answers | Lives in |
|---|---|---|
| `Organization` | Whose data is this? | `app/models/organization.py` |
| `Person` | Who is this? | `app/models/person.py` |
| `Team` / `TeamMembership` | Which team(s) is this person part of? | `app/models/team.py`, `team_membership.py` |
| `Project` | What workstream exists to consume capacity? | `app/models/project.py` |
| `Allocation` | What work is planned, for whom, on what project, when? | `app/models/allocation.py` |
| `WorkingSchedule` / `WorkingScheduleEntry` | When does this person normally work? | `app/models/working_schedule.py` |
| `AvailabilityException` | When does this person deviate from that normal pattern? | `app/models/availability_exception.py` |

### Person

`display_name` is stored, not purely computed — `PersonService.create` defaults it to `"{first_name} {last_name}"` when not explicitly supplied, but it can be overridden (a preferred/display name that differs from the legal name is a real, common need). There is exactly one place in the codebase that decides this default, so it doesn't drift out of sync in practice.

`employment_status` is a controlled vocabulary (`active`/`inactive` today) enforced by a database CHECK constraint, not an arbitrary string — extending it later means adding an enum member and a migration, not "any string goes."

A person can belong to **zero, one, or many** teams. `Person.team_id` does not exist — see `TeamMembership`.

### Team / TeamMembership

`TeamMembership` is a real table with its own identity (not an anonymous many-to-many association table), specifically so future metadata — role within team, "primary team" flag, membership effective dates — can be added without restructuring anything. `(person_id, team_id)` is unique; you cannot join the same team twice.

### Project

`start_date`/`end_date` are optional — a project can exist in `planned` status before its dates are fixed. When both are set, `end_date >= start_date` is enforced both by a database CHECK constraint and by the API schema.

### Allocation

**This is the field most likely to be misread — read this carefully.**

`allocation_hours` is the **total planned hours across the whole `[start_date, end_date]` period** — not a daily rate, not a weekly rate. An allocation of 40 hours over a 4-week period means 40 hours total across those 4 weeks. It does **not** mean "40 hours/day" or "40 hours/week."

`allocation_unit` exists as a field (currently with a single value, `total_hours`) specifically so a future time-phased allocation unit (e.g. `hours_per_week`) can be introduced without changing the shape of this table.

Allocation validates that both the referenced person and project exist, and that `end_date >= start_date` and `allocation_hours >= 0` — but it does **not** check whether the person has enough capacity to take it on. That check requires the capacity engine (Phase 2+).

### WorkingSchedule / WorkingScheduleEntry

A `WorkingSchedule` is a container for up to seven `WorkingScheduleEntry` rows (one per weekday), rather than seven columns bolted onto `Person` — this supports uneven weeks (e.g. 6/6/0/6/6) and, via the schedule's optional `effective_start_date`/`effective_end_date`, supports a person having *different* schedules over time (e.g. a part-time period) without a future schema rewrite. Phase 1 does not enforce that a person's schedules don't overlap in time — that's a later-phase validation once it's actually needed.

`weekday` uses Python's `date.weekday()` convention: **0 = Monday … 6 = Sunday** (not the ISO-8601 1–7 convention). This is called out explicitly because the two conventions are easy to confuse and get it wrong silently.

### AvailabilityException

`hours = None` means the person is **completely unavailable** for the whole `[start_date, end_date]` period — this is the common case: annual leave, sick leave, a public holiday.

`hours = <a number>` means the person is available for that many hours **per day** during the period — the "partial availability" case (e.g. someone who normally works 8 hours/day is available for only 4 hours/day during this period). `hours` is never "hours missed" — it's always "hours still available."

`availability_type` is a controlled vocabulary (`AvailabilityType` in `app/models/enums.py`) but, unlike `EmploymentStatus`/`ProjectStatus`/`AllocationUnit`, it has **no database CHECK constraint**. CLAUDE.md is explicit that availability reasons "must not be hard-coded into the database structure" — so this one is enforced at the application layer (Pydantic) only, meaning a new reason can be added with zero migration.

## What Phase 1 does NOT compute

No utilization percentage, remaining capacity, over-allocation flag, workload score, or bottleneck detection exists anywhere in this phase — deliberately. Phase 1's job is to make the four source concepts above trustworthy and clearly distinguished; a future capacity engine (CLAUDE.md §10, Phase 2) is what turns `WorkingSchedule + AvailabilityException + Allocation` into an actual capacity number.

## Capacity Engine (Phase 2)

The capacity engine (`app/domain/capacity.py`, `app/domain/dates.py`) is pure, deterministic Python — no database, no HTTP, no AI (CLAUDE.md §4/§10) — that turns the three source concepts above into the fifth: **capacity**, over an explicit `[start_date, end_date]`. See [ADR 0003](adr/0003-phase-2-capacity-engine.md) for the reasoning behind every decision below; this section is the formulas and definitions.

### Definitions

| Term | Meaning |
|---|---|
| **Gross capacity** | The hours implied by `WorkingSchedule` alone for the period — the normal pattern, with no exceptions or allocations applied. |
| **Unavailable hours** | `gross capacity − effective capacity` for the period — the hours removed by `AvailabilityException`s. |
| **Effective capacity** | Gross capacity after applying availability exceptions — the actual working time available. |
| **Allocated hours** | Planned project demand (`Allocation`) time-phased into the period. |
| **Remaining capacity** | `effective capacity − allocated hours`. Can be negative — a negative value is real information (over-allocation), never clamped to zero. |
| **Utilization** | `allocated hours ÷ effective capacity`, as a ratio (0.80 = 80%, not the string `"80%"`). **`null`, not `0`, when effective capacity is `0`** — see below. |
| **Over-allocation** | `max(allocated hours − effective capacity, 0)`. Zero when a person has slack; positive whenever demand exceeds effective capacity, including when effective capacity is itself `0`. |

### Daily ledger, then aggregation

The engine always computes one day at a time first (`calculate_daily_capacity`), then sums the daily ledger into a period total (`calculate_period_capacity`) — day, week, and any arbitrary range are the same function with different bounds, never a separately-derived "weekly formula." Team totals (`aggregate_team_capacity`) are sums of already-computed member totals, not a third independent calculation.

### Allocation semantics: time-phasing

`Allocation.allocation_hours` is a **total** over `[start_date, end_date]` (see the Allocation section above). The engine spreads it evenly across every **calendar** day in that range — including weekends and days the person isn't normally scheduled to work — specifically so that an allocation placed on a non-working day shows up as a real conflict (over-allocation) instead of being silently absorbed or moved. Multiple allocations overlapping the same person and date (different projects) sum — this is cross-project contention, a fact to surface, not an error.

### Availability semantics: overlapping exceptions

If more than one `AvailabilityException` covers the same date, the engine takes the **most restrictive** reading: effective capacity for that date is the minimum of the normal scheduled hours and every covering exception's "available that day" value (`0` for `hours = None`). It is never a sum — two exceptions each leaving 4h and 2h available do not combine into 6h.

### Working schedule selection

`WorkingScheduleService` now rejects (422) creating or updating a schedule whose effective date range overlaps another schedule already on file for the same person — a Phase 1 amendment (ADR 0003) needed so the engine can assume at most one schedule ever matches a given date. Zero matching schedules for a date means `0` scheduled hours (the person has no normal pattern on file for that date), not an error.

### Zero-capacity utilization

`utilization` is `null` whenever effective capacity is `0` for the period — both when nothing is allocated (a person fully on leave, correctly not shown as "0% utilized") and when something *is* allocated despite zero capacity (a genuine conflict, visible instead through a positive `over_allocation` and negative `remaining_capacity`).

### Team aggregation

Team `effective_capacity`/`allocated_hours`/`remaining_capacity` are sums of member values. Team `utilization` is **weighted** — `sum(allocated) / sum(effective)` — never an average of member utilization percentages, which would treat a person with 2 effective hours as equally significant to the team number as one with 40. The team API response always includes every member's own full result alongside the team totals, so an individual's over-allocation is never hidden by a healthy team aggregate.

### Canonical week

Monday–Sunday, defined once (`app/domain/dates.py::WEEK_START_WEEKDAY`), matching `WorkingScheduleEntry.weekday`'s existing `date.weekday()` convention (0=Monday). The API takes explicit `start_date`/`end_date` — there's no separate "week" concept to get wrong.

### Worked example

```text
Person: Mon-Fri, 8h/day (40h/week gross)
Period: one week, no availability exceptions
Allocations: Project A 20h, Project B 15h, Project C 10h (all covering the full week)

Gross capacity      = 40h
Effective capacity  = 40h   (no exceptions)
Allocated hours     = 45h   (20 + 15 + 10)
Remaining capacity  = -5h   (40 - 45)
Utilization         = 1.125 (45 / 40)
Over-allocation     = 5h    (45 - 40)
```

### What Phase 2 does NOT do

No skills, no bottleneck detection, no scenario planning, no dashboard, no AI-generated explanation of these numbers — those are later phases (CLAUDE.md §39). Phase 2's job is the arithmetic itself, exposed through three thin read-only endpoints (`GET /api/v1/capacity/people/{id}`, `/teams/{id}`, `/projects/{id}`).

## Scenario Planning (Phase 4)

A **Scenario** (`app/models/scenario.py`) is a hypothetical planning exercise: "what happens if we accept this work?", "what if this project starts two weeks earlier?", "would hiring someone solve this?" — answered without ever writing to Person, Team, Project, Allocation, WorkingSchedule, or AvailabilityException. See [ADR 0004](adr/0004-phase-4-scenario-planning.md) for the full reasoning; this section is the concepts and lifecycle.

### Baseline vs scenario

Every scenario has a **baseline period** (`baseline_start_date`/`baseline_end_date`) and a list of **ScenarioOperations** — the delta from real data. A scenario is never a copy of People/Projects/Allocations; it is its operations plus that date range. Calculating it always re-reads current baseline data and applies the operations in memory — nothing is ever written back.

### Scenario operations

Eight typed operations (`app/domain/scenario.py`), each a small, unambiguous change:

| Operation | Models |
|---|---|
| `add_allocation` | A new hypothetical allocation |
| `adjust_allocation` | A change to a real, existing allocation's hours and/or dates |
| `remove_allocation` | Excluding a real, existing allocation |
| `move_allocation` | Moving all or part of a real allocation's hours to another person |
| `shift_project` | Shifting every allocation on a project by N days |
| `availability_override` | A hypothetical reduction/removal of availability for a window |
| `availability_clear` | Restoring normal availability for a window (early return from leave) |
| `add_hypothetical_resource` | A virtual person (no Person row) with a synthetic weekly schedule, for "would hiring solve this" questions |

`adjust_allocation`/`remove_allocation`/`move_allocation` only ever target a **real, baseline** allocation — not one created earlier in the same scenario by another operation. This is a deliberate scope limit (see the ADR), not an oversight.

Operations apply in stored **sequence order** — a later operation sees the effect of every earlier one. This is the entire conflict-resolution rule: there is no separate merge/precedence logic beyond "apply in order."

### Calculation lifecycle

1. Load real baseline facts (schedules, exceptions, allocations) for every person a scenario's operations reference, directly or via a project's full membership.
2. Apply the scenario's operations, in sequence, to produce a hypothetical version of those same facts (`apply_scenario_operations`) — a pure, in-memory transformation. The baseline is never mutated; a fresh state is returned.
3. Run **the same, unmodified** Phase 2 engine (`calculate_period_capacity`, `aggregate_team_capacity`, `calculate_project_demand`) over both the baseline facts and the scenario facts.
4. Derive comparison, risk, and impact entirely from those two already-computed results — no second set of formulas.

`POST /calculate`, `GET /results`, and `GET /comparison` all perform this same computation on demand — there is no cached "scenario result" row. See the ADR for why.

### Comparison semantics

Baseline and scenario numbers are always kept as distinct, explicit fields — never merged into one blob. A `MetricDelta` (`baseline`, `scenario`, `delta`) is used for every compared metric. Risks are limited to two objective facts the engine already computes — over-allocation and exactly-zero remaining capacity — each marked `is_new` (true in the scenario, false in the baseline) so "prioritize new risks" (CLAUDE.md §16) is a fact, not a guess.

### Prioritization comparison (Phase 20) — a separate mechanism, not a ninth operation

A Scenario can *also* carry hypothetical prioritization inputs (`ScenarioPriorityOverride`) and be compared against the baseline portfolio ranking under a chosen framework — but this is deliberately **not** a ninth entry in the operations table above, and does not flow through `apply_scenario_operations`/`PlanningState` at all. See "Prioritization" below ("Scenario-vs-baseline prioritization comparison") for why: a prioritization override has no ordering/replay semantics and never touches capacity, so it's a parallel, independent mechanism reached through its own `GET /priority-comparison` endpoint, not an extension of this section's calculation lifecycle.

## Operational Insights (Phase 5)

Phase 5 answers "where should I look?" — not "what should I do?" — by classifying facts the Phase 2 capacity engine and Phase 4 scenario engine already compute into explainable, prioritized **signals**. See [ADR 0005](adr/0005-phase-5-operational-insights.md) for the full reasoning; this section is the vocabulary and rules.

### Vocabulary

| Term | Meaning |
|---|---|
| Fact | A number the capacity or scenario engine already computed (e.g. `over_allocation`, `remaining_capacity`) — never recomputed differently here. |
| Derived metric | A deterministic function of one or more facts, gated only by an *existence* condition, never an invented magnitude threshold (e.g. concentration ratio, utilization spread). |
| Threshold | A single backend-owned judgment boundary — LOW_CAPACITY only (see ADR 0005). Every other signal fires on a fact or an existence condition. |
| Signal | A classified, explained instance of a fact/derived-metric/threshold crossing, surfaced by the Insights API. |
| Severity | One of `critical` / `warning` / `info`, assigned deterministically per signal type. |

### Signal categories

| Category | Signal type(s) | Classification | Scope |
|---|---|---|---|
| A. Over-allocation | `over_allocation` | fact (`over_allocation > 0`) | person, team |
| B. Zero remaining capacity | `zero_remaining_capacity` | fact (`remaining_capacity == 0`, gated on `effective_capacity > 0`) | person, team |
| C. Low capacity | `low_capacity` | threshold (`remaining_capacity / period_days <= LOW_CAPACITY`) | person, team |
| D. Concentration risk | `concentration_risk` | derived metric (top-2 contributors' share of a project's hours) | project |
| E. Capacity imbalance | `capacity_imbalance` | derived metric (min/max utilization spread across a team) | team |
| F. Project capacity pressure | `project_capacity_pressure` | fact/threshold, reusing `aggregate_team_capacity` over the project's assigned people | project |
| G. Scenario delta | `scenario_new_risk`, `scenario_existing_risk` | fact, reusing `ScenarioCalculationService`'s own risk detection | person |

A/B/C/F are mutually exclusive per entity (an `if`/`elif` chain, same style as `ScenarioCalculationService._risks`): over-allocation always wins over zero-remaining, which always wins over low-capacity.

### Severity rules

| Severity | Meaning | Fires for |
|---|---|---|
| `critical` | A confirmed, already-happened fact: promised work exceeds available capacity | `over_allocation`, `project_capacity_pressure` (over-allocated), scenario risks whose underlying type is `over_allocation` |
| `warning` | The one backend-invented threshold (LOW_CAPACITY) has been crossed — worth a look, not yet broken | `low_capacity`, `project_capacity_pressure` (low capacity) |
| `info` | A shape-of-the-plan observation, not a problem | `zero_remaining_capacity`, `concentration_risk`, `capacity_imbalance`, scenario risks whose underlying type is `zero_remaining_capacity` |

### Priority order

Signals are sorted `(severity, is_new-first, type-family, entity_label, entity_id)` — severity dominates because it is the one objective "how bad" fact every category shares; `is_new` and signal-type family are tiebreakers *within* a severity tier only. This deliberately refines the brief's flat example ordering ("critical over-allocation, new scenario risks, existing warnings, concentration, imbalance, informational"), which would let a merely-informational new scenario signal outrank an existing critical over-allocation.

### What Phase 5 does NOT do

No AI, no external integrations, no new capacity formula, no second invented threshold beyond LOW_CAPACITY, no org-wide unscoped scan (every endpoint is person/team/project/scenario-scoped, matching Phase 2/4). Concentration risk and capacity imbalance never escalate beyond `info` severity — they are structural observations, not confirmed problems.

## Import / Export (Phase 6)

Phase 6 makes CapacityOS's core operational data **portable**: exportable to CSV/JSON for backup or reuse, and importable back in with the same validate-before-write discipline every other write path in this system follows. See [ADR 0006](adr/0006-phase-6-import-export.md) for the full reasoning; this section is the vocabulary and rules.

### Supported entities

Person, Team, TeamMembership, Project, WorkingSchedule, AvailabilityException, Allocation — the same source-fact entities Phase 1 defined. **Deliberately excluded:** Scenario/ScenarioOperation (hypothetical, not source data — see [Scenario Planning](#scenario-planning-phase-4)) and Insight signals (derived, recalculated from source facts every time, never stored as authoritative — see [Operational Insights](#operational-insights-phase-5)). Importing a derived value as if it were a fact would let stale or fabricated numbers silently override what the capacity engine would otherwise compute.

### Vocabulary

| Term | Meaning |
|---|---|
| `ENTITY_COLUMNS` | The single source of truth for one entity's column/header set and order — shared verbatim by import parsing, export writing, and template generation. |
| Identity | The field(s) used to match an uploaded row against an existing record: `email` (Person), `name` (Team), resolved `(person_id, team_id)` (TeamMembership), or `external_id` (Project, Allocation, WorkingSchedule, AvailabilityException). A row with no identity always creates. |
| `external_id` | A nullable, unique, user-supplied string identifier added in Phase 6 for the four entities with no pre-existing natural key — the Phase 6 import identity key, distinct from the database's own internal `id`. |
| Validation report | The Stage A response (`ImportValidationReport`): per-row status plus totals, before anything is written. |
| Apply result | The Stage B response (`ImportApplyResult`): the same shape, after writing — `applied=False` whenever any row was invalid, since nothing is written unless every row is clean. |

### The two-stage flow

```text
Uploaded file
      ↓
Level 1 — file validation (format, encoding, headers, size/row limits)
      ↓
Level 2 — record validation (required fields, types, enums — via the real Create/Update Pydantic schemas)
      ↓
Level 3 — domain validation (reference resolution, date ranges, working-schedule overlap — reusing existing domain/service rules)
      ↓
Level 4 — cross-row validation (duplicate identities within the same file)
      ↓
Validation report (Stage A) — nothing written yet
      ↓
Explicit user confirmation
      ↓
Apply (Stage B) — re-validates the same file, then writes every row through the existing services, atomically
```

A row's classified action is one of `valid_create` / `valid_update` / `valid_unchanged` / `invalid`. "Unchanged" is a real field-level comparison against the current stored value (only the fields the row actually supplied), not just "a match was found" — this is what makes reimporting the same file repeatedly deterministic instead of reporting spurious updates every time.

### Import modes

| Mode | Behavior |
|---|---|
| `upsert` (default) | Create if no match, update if matched and changed, no-op if matched and unchanged. |
| `create_only` | A row that matches an existing record becomes a blocking conflict instead of updating it. |
| `update_only` | A row that matches nothing becomes a blocking error instead of creating it. |

There is no destructive "sync" or "replace" mode — an import never deletes a record that's simply absent from the uploaded file.

### What Phase 6 does NOT do

No AI, no external integrations, no new capacity formula, no persisted import-job/history entity (a validation report exists only within its own request/response), no destructive sync mode, no asynchronous/background job infrastructure. Imported facts flow through the unmodified Phase 2 capacity engine and Phase 5 insight classifiers exactly like manually-entered data — Phase 6 introduces no second way for a number to become "true."

## Skills & Bottleneck Analysis (Phase 7)

Phase 7 answers "do we have the *right* capacity, not just *enough* capacity?" by adding a skill dimension on top of the existing capacity engine and insights framework. See [ADR 0007](adr/0007-phase-7-skills-bottleneck-analysis.md) for the full reasoning; this section is the vocabulary and rules.

### The central distinction

**SKILL CAPACITY ≠ TOTAL CAPACITY.** A person with 40h of remaining capacity and no recorded proficiency in a required skill contributes 0h of *qualified* capacity toward that requirement. A team can be well under its aggregate capacity while a specific skill is fully consumed. Every Phase 7 view keeps these two numbers visibly separate — never one blended figure.

### Entities

| Entity | Answers | Lives in |
|---|---|---|
| `Skill` | A named capability people can hold and projects can require. | `app/models/skill.py` |
| `PersonSkill` | This person's explicitly recorded proficiency in one skill. | `app/models/person_skill.py` |
| `ProjectSkillRequirement` | How much of one skill, at what minimum proficiency, this project needs. | `app/models/project_skill_requirement.py` |

Proficiency (`beginner` / `working` / `proficient` / `advanced` / `expert`) is never inferred — not from job title, not from allocation history, not by AI. It exists only because someone explicitly recorded it. `Skill.is_active` is a soft-delete flag (`DELETE /api/v1/skills/{id}` deactivates, never removes the row) — deactivating preserves history instead of orphaning `PersonSkill`/`ProjectSkillRequirement` rows or silently changing past coverage numbers; every qualification/coverage/signal calculation filters out inactive skills regardless of what still references one.

### Qualification

A person qualifies for a requirement when all three hold:

1. They have an active `PersonSkill` for the required skill.
2. Their proficiency rank meets the requirement's `minimum_proficiency` (no minimum set = any recorded proficiency qualifies).
3. They have capacity — but "qualified available hours" is a Phase 7 derived quantity, `max(remaining_capacity, 0)`, not a redefinition of Phase 2's `remaining_capacity` (which stays unclamped, negative when over-allocated). A fully-booked qualified person still counts as a *holder* of the skill (relevant to single-point-of-failure detection) but contributes 0 qualified hours toward closing a gap.

### Coverage

For each `ProjectSkillRequirement`: `required_hours`, `qualified_available_hours` (summed across every qualified holder, org-wide — a project has no fixed eligible roster the way a team has members), `coverage_ratio`, `gap_hours`. The UI distinguishes **not configured** (no requirements exist — `requirements: []`) from **fully covered** (`gap_hours == 0`) from **partially covered** (some qualified capacity, still a gap) from **uncovered** (`qualified_available_hours == 0`) — these are never conflated into one status.

Team skill capacity reports **supply only** — qualified available hours and holders per skill across a team's members — with no "team demand" figure. A team has no stored or derivable skill demand of its own; only `ProjectSkillRequirement` carries one, so demand-vs-supply comparison happens at the project level. Likewise, "allocated hours associated with a skill" is not reported anywhere: `Allocation` has no skill dimension, and inventing a proportional-attribution rule would be the same category of fabricated distribution rule ADR 0004 already declined for project demand.

### Bottleneck signals

Three new signal types plug into the **existing** Phase 5 framework (`SignalRead`, `get_project_signals`/`get_team_signals`, the Insights page) — there is no separate bottlenecks API or page:

| Signal | Scope | Severity | Fires when |
|---|---|---|---|
| `skill_gap` | project | `critical` if zero qualified capacity, else `warning` | a requirement's `gap_hours > 0` |
| `single_skill_holder` | project, team | `warning` | exactly 1 qualified holder |
| `skill_concentration` | project, team | `info` | exactly 2 qualified holders |

Holder-count gating (1 or 2) is an existence condition, matching Phase 5's discipline of never inventing a magnitude threshold — more than 2 holders is not reported as concentrated at all.

### What Phase 7 does NOT do

No AI, no skill inference, no automated staffing recommendations ("move John to Project Alpha" never appears — only evidence like "28h qualified capacity gap"), no second capacity engine, no second signal system, no `/api/v1/bottlenecks/` endpoint. Full scenario/skill interaction (would a hypothetical hire close this gap?) is a documented seam, not a built integration — see the ADR.

## AI Insight Layer (Phase 8)

Phase 8 answers "why does this matter, and what might I consider?" — strictly on top of the facts Phases 2, 5, and 7 already computed. See [ADR 0008](adr/0008-phase-8-ai-insight-layer.md) for the full reasoning; this section is the vocabulary and rules.

### The central rule

**AI never calculates.** Capacity, utilization, over-allocation, signal severity, scenario deltas, skill coverage — every number an AI response references was computed by the deterministic engine before the AI ever sees it. The architecture is one direction only: `FACTS → DETERMINISTIC ENGINE → SIGNALS → AI INTERPRETATION`, never `RAW DATA → LLM → BUSINESS DECISION`.

### Provider abstraction

`AIProvider` is a single-method interface (`generate`). `AnthropicAIProvider` is the production implementation; `MockAIProvider` is a deterministic, non-LLM stand-in used by the entire backend test suite and by local development with no API key. `Settings.ai_provider` (`"anthropic"` / `"mock"` / `"none"`, default `"none"`) selects between them — with `"none"`, or `"anthropic"` with no `ANTHROPIC_API_KEY`, every AI endpoint returns a first-class `unavailable` response instead of erroring, and every deterministic feature in the app is completely unaffected.

### AI context

`AIInsightContext` (and its component `AICapacityFact`/`AISignalFact`/`AISkillCoverageFact`/`AIScenarioFact`/`AIPriorityFact`) is an explicit, minimal, typed snapshot built from the same `CapacityService`/`InsightService`/`ScenarioCalculationService`/`SkillCapacityService`/`ProjectPriorityScoreService` calls every other phase's UI already uses. No SQLAlchemy row and no field outside this typed shape is ever sent to a provider. Entity labels are display names, never emails — data minimization by construction. `AIPriorityFact` was added in Phase 19 (see below) — every other component predates it and is unchanged.

### Structured output and grounding

The provider returns a validated `AIModelOutput`: a `summary`, `key_findings`/`risks` (each a claim plus `source_references`), `recommendations` (each with a rationale, `source_references`, and stated `assumptions`), and a `confidence` category (`high`/`medium`/`low` — never a numeric probability). Every `source_reference` the model returns is checked against an allow-list of the facts actually present in the context that was sent (`AIInsightContext.known_references()`); anything that doesn't match is stripped before the response leaves the backend. A claim the model can't support with an in-context fact is dropped, not fabricated into looking supported.

### Response envelope

Every `/api/v1/ai/*` endpoint returns `{status, response, message}` with **HTTP 200 always**: `ok` (a grounded response), `unavailable` (no provider configured — expected, not an error), or `error` (a provider is configured but the call failed — timeout, rate limit, malformed output). The frontend branches on `status`, never on an HTTP error code, for these three cases.

### Capabilities

| Capability | Endpoint | Answers |
|---|---|---|
| Summary | `POST /api/v1/ai/summary` | What's the operational picture for this person/team/project and period? |
| Explain signal | `POST /api/v1/ai/explain-signal` | Why does this existing signal exist, and what's the evidence? (also covers skill bottlenecks — `skill_gap`/`single_skill_holder`/`skill_concentration` are signal types like any other) |
| Explain scenario | `POST /api/v1/ai/explain-scenario` | What changed between baseline and scenario, and why? |
| Explain priority | `POST /api/v1/ai/explain-priority` | Why is this project's priority score what it is, and what's missing? (Phase 19 — see [Prioritization](#prioritization-phases-17-19) below) |
| Ask | `POST /api/v1/ai/ask` | A controlled natural-language question about one scope, answered only from that scope's assembled facts — never generated SQL, never arbitrary tool/endpoint calls. |

### What Phase 8 does NOT do

No second capacity/signal/bottleneck engine. No AI-initiated writes of any kind — recommendations are always phrased as suggestions ("Consider...") and the schema gives them no path to mutate data. No skill or capability inference from job titles, project names, or allocation history. No hiring, performance, or health/legal judgments about any person. No persistent AI conversation history or analytics table (every request is stateless). No response caching (every explanation is generated fresh against current facts). No automatic AI generation on page load — every capability is triggered by an explicit user action.

## Organizations & Multi-Tenancy (Phase 12)

See `docs/adr/0012-organizations-multi-tenancy.md` for the full design and audit; this section is the concept summary.

### The tenant boundary

Every entity table in this document (Person, Team, Project, Allocation, WorkingSchedule, AvailabilityException, Skill, PersonSkill, ProjectSkillRequirement, Scenario) carries a direct `organization_id` foreign key — not an indirect join through some other table. A row belongs to exactly one `Organization`, always. There is no cross-organization sharing, no organization hierarchy, and no "global" data visible across organizations except the `User` account/login layer itself (see below).

### `User` vs `OrganizationMembership`

`User` is the login identity — one email, one password, usable across every organization the account belongs to. `OrganizationMembership` is where a `User` gets a `role` (Owner/Admin/Manager/Member/Viewer — the same five roles Phase 10 introduced, unchanged) *within one specific organization*. The same person can be Owner of one organization and Viewer of another; role is never a global property of the account.

### Active organization

A session has at most one *active* organization at a time (`UserSession.active_organization_id`), selected automatically at login when unambiguous (exactly one membership) or explicitly via `POST /api/v1/auth/switch-organization`. Every organization-scoped request re-verifies that membership is still active and the organization itself hasn't been deactivated — on every single request, not just at login. A session with no active organization can still authenticate (`GET /auth/me` works) but cannot reach any organization-scoped route until one is selected.

### Cross-organization access looks like "not found," never "forbidden"

Referencing another organization's Person/Team/Project/etc. by id returns 404, the same response a genuinely nonexistent id would produce — never 403. A 403 would confirm the resource exists somewhere just not to you, which is itself a leak this system is designed not to have.

### What Phase 12 does NOT do

No billing or subscription concept. No SSO/OAuth or external identity provider integration. No organization hierarchies or sub-organizations. No cross-organization data sharing of any kind. No hard delete of an organization (deactivation only, matching `Skill.is_active`'s soft-delete precedent). No per-organization feature flags.

## Risk Management (Phase 13)

Phase 13 answers "what could go wrong on this project, how exposed are we, and who owns following up?" (CLAUDE.md §17). See [ADR 0013](adr/0013-phase-13-risk-management.md) for the full reasoning; this section is the vocabulary and rules.

### `Risk`

A project-scoped record: `description` (required), `cause`, `potential_effect`, `probability`, `impact`, `response`, `owner_person_id`, `status`, `review_date`. Organization-scoped like every entity since Phase 12, `CASCADE`-deleted with its `Project` (a risk is meaningless without the project it's about — same convention as `ProjectSkillRequirement`). `owner_person_id` points at `Person`, not `User` (CLAUDE.md §9: an owner is an accountable individual, not necessarily a login), and is `SET NULL` on delete — the risk record outlives whichever person currently owns it.

### Exposure is derived, never stored

`probability` and `impact` are each a coarse 3-tier scale (`low`/`medium`/`high`) — CLAUDE.md §17: "Do not create risk scores that imply false precision." `exposure` is computed at read time from an explicit 3×3 lookup table (`app/domain/risk.py::calculate_risk_exposure`), never a multiplication and never a persisted column — the same "compute, don't store" discipline Phase 5 already applies to `Severity`.

### Status is a lifecycle, not a toggle

`open` → `mitigating` (a response is underway) → `monitoring` (mitigated but still watched, or a low-priority risk tracked passively) → `closed` (terminal — CLAUDE.md §12: "risk management should be continuous," not a one-time assessment). A `closed` risk never produces a signal regardless of exposure or a lapsed review date — closing a risk is the explicit "no longer live" action.

### Bottleneck signals

Two new signal types plug into the **existing** Phase 5 framework (`SignalRead`, `get_project_signals`, the Insights page) — no new route, same mechanism Phase 7 established for skill signals:

| Signal | Scope | Severity | Fires when |
|---|---|---|---|
| `risk_high_exposure` | project | `critical` while `open`, `warning` once `mitigating`/`monitoring` | exposure is `high` and status is not `closed` |
| `risk_review_overdue` | project | `warning` | `review_date` is in the past, status is not `closed`, and exposure is not already `high` |

A risk reports at most one signal — `risk_high_exposure` takes priority when both conditions hold, matching Phase 5's "existence gate, not a magnitude judgment" discipline (no invented risk score, no double-counting the same underlying risk).

### What Phase 13 does NOT do

No Import/Export registration (deferred — CLAUDE.md §17 doesn't require it, and it's a large enough addition to warrant its own phase). No org-wide/cross-project risk register (every route is nested under one project). No Prioritization entity (CLAUDE.md §18 — a separate, unbuilt concept; Stakeholder Management, CLAUDE.md §16, was built in Phase 14 — see below). No per-organization "last active Owner" account-disable invariant (a pre-existing gap from Phase 12, out of this phase's scope — see ADR 0012's Consequences). No risk score, no probability/impact numeric weighting, no AI-generated risk assessments.

## Stakeholder Management (Phase 14)

Phase 14 answers "who needs to know, and who decides?" (CLAUDE.md §16). See [ADR 0014](adr/0014-phase-14-stakeholder-management.md) for the full reasoning; this section is the vocabulary and rules.

### `Stakeholder`

A project-scoped record: `name` (required — always the stakeholder's own recorded identity), `person_id` (optional link to an existing `Person`), `role` (free text — e.g. "Sponsor," "End user," "Regulator"), `influence`, `interest`, `decision_authority`, `communication_needs`. Organization-scoped like every entity since Phase 12, `CASCADE`-deleted with its `Project` — "relevant project/work context" from §16's field list is satisfied by this scoping itself, not a separate stored field, the same reasoning `Risk` applies to the identical phrase in §17.

### Not every stakeholder is a `Person`

Real stakeholders are frequently external to the organization's own staffed roster — a client contact, a regulator, an executive at a partner organization. `Stakeholder.name` is always required and always stored explicitly; `person_id` is an *optional* nullable link, `SET NULL` on delete (matching `Risk.owner_person_id`'s precedent) — the stakeholder record outlives whichever `Person` it happens to be linked to, and a stakeholder never has to be a fabricated `Person` row just to exist. `(project_id, person_id)` is a composite unique constraint (a person can be a stakeholder on a given project at most once); multiple external stakeholders with no linked person don't collide, matching `Project.external_id`'s nullable-uniqueness precedent.

### Influence, interest, and decision authority — stored, never combined

`influence`/`interest` are each a 3-tier scale (`low`/`medium`/`high`) — the two axes of the well-established stakeholder power/interest grid, at the same granularity CapacityOS already uses for `Risk.probability`/`Risk.impact`. `decision_authority` is a 3-level scale (`decision_maker` / `advisor` / `informed`) answering CLAUDE.md §5's "every important decision should have an accountable owner" for exactly the one field §16 names — not a full RACI matrix. None of these are ever combined into a score, health rating, or "engagement quadrant" label — CLAUDE.md §16/§17's "no false precision" rule applies here exactly as it does to Risk. `communication_needs` is free text (open vocabulary, like `AvailabilityType`) — communication preferences vary too much to fit a fixed set.

### What Phase 14 does NOT do

No Insights integration — CLAUDE.md §16 defines no threshold or derived fact to classify into a signal, so none was invented (the existing Phase 5/7/13 signals each exist because a real, specified, deterministic condition is being checked; nothing comparable exists for Stakeholder). No Import/Export registration (deferred, matching Phase 13's own precedent for a new entity not explicitly asked for). No org-wide/cross-project stakeholder register (every route is nested under one project). No stakeholder score, health score, or engagement-quadrant classification. No Prioritization entity (CLAUDE.md §18 — still a separate, unbuilt concept).

## Last-Owner Invariant (Phase 15)

Phase 15 closes the gap ADR 0012 deferred: every active `Organization` must retain at least one Owner who can actually act — not merely an `OrganizationMembership` row that says `role=Owner`. See [ADR 0015](adr/0015-last-owner-invariant.md) for the full reasoning; this section is the vocabulary and rules.

### "Active Owner" — the definition this phase settles

An active Owner is an `OrganizationMembership` with `role=Owner` and `status=Active`, whose linked `User.status` is *also* `Active`. `User.status` and `MembershipStatus` remain independent concepts everywhere else in the system (Phase 12: revoking a membership never disables the account) — but for THIS invariant specifically, both must hold, because `AuthService.login`/`resolve_session` already refuse to authenticate a disabled account outright. An Owner membership pointing at a disabled account cannot exercise Owner authority today regardless of what this phase does; counting it would make the invariant lie about whether the organization has a *working* Owner.

### What's guarded, and how

Three mutation paths can reduce an organization's active-Owner count to zero: demoting an Owner's role, revoking an Owner's membership, and disabling an Owner's account. All three are guarded by the same technique — the invariant is folded directly into the write statement's own `WHERE` clause (an atomic guarded `UPDATE`, re-evaluated at write time), not decided in application code from a separate prior read. A plain "read the count, decide, then write" is unsafe under concurrent requests: two simultaneous demotions of an organization's last two Owners could each observe "2 Owners, not the last one" before either writes, and both succeed — leaving zero. The guarded-`UPDATE` technique closes exactly that race; see the ADR for the mechanism and what was and wasn't independently verified.

### What this is not

Not a new permission — an Owner is blocked from removing the last Owner (even themselves) by the same invariant that blocks an Admin, not by a permission check. Not a new error status — the existing `DomainValidationError` → 422 convention the pre-existing role-change/revoke guards already used. Not a schema change — the count is derived from existing `OrganizationMembership`/`User` columns, never a stored `organization.owner_id`. Not a new UI — no membership- or user-management page exists yet in the frontend to add a guard to; the backend enforces this unconditionally regardless of what UI eventually calls these routes.

## Instance-Authorization Completion (Phase 16)

Phase 16 answers the question Phase 11 (§"Which resources are scoped, and which are deliberately deferred") left open: should Team access ever imply Project access, should a Person's schedule/availability/skills be instance-scoped, and should Scenario be? See [ADR 0016](adr/0016-instance-authorization-completion.md) for the full audit; this section is the resulting, settled vocabulary.

### Three deferrals, each resolved the same way: retained

Team→Project inheritance, Person-keyed instance scoping (`WorkingSchedule`, `AvailabilityException`, `PersonSkill`), and Scenario instance scoping are each **deliberately retained as role-only**, not built. In every case the reason is the same one Phase 11 originally gave: there is no single, unambiguous parent resource to key an instance-level grant on without inventing a derived-authorization chain CLAUDE.md never specified (`Project` has no `team_id`; `Person` relates to `Team` many-to-many via `TeamMembership` and to `Project` only indirectly and time-boxed via `Allocation`; `Scenario` has no Team/Project/Person foreign key at all). Building any of these now would mean inventing product/ownership semantics no existing specification defines — the thing CLAUDE.md's own instructions warn against doing.

### What this means in practice

Any Manager (a role that holds `schedule.write`/`skill.write`/`scenario.write` unconditionally) may mutate **any** Person's `WorkingSchedule`/`AvailabilityException`/`PersonSkill`, and **any** `Scenario`, anywhere in their organization — regardless of which Teams or Projects they hold an explicit `TeamAccessGrant`/`ProjectAccessGrant` for. This is not a gap that slipped through; it is the deliberately retained Phase 11 design, now re-confirmed and locked in with regression tests (`tests/api/test_cross_resource_escalation.py`) specifically so an accidental future change would be caught as a test failure rather than discovered as a real authorization bug.

### What Phase 16 actually found and fixed

Not an authorization bug — a test-coverage gap. Every organization-owned entity's repository already enforced the Phase 12 tenant boundary; only Risk and Stakeholder had a regression test proving it. `tests/api/test_cross_organization_boundaries.py` closes that gap for every remaining entity (Person, Team, TeamMembership, Skill, PersonSkill, ProjectSkillRequirement, WorkingSchedule, AvailabilityException, Allocation, Scenario), and one instance-level Manager-grant test block was added to `Risk`'s own test file to match its sibling `Stakeholder`'s existing coverage. Zero production code changed as a result — every one of these tests passed against the existing implementation on the first run.

## Prioritization (Phases 17-22)

Phase 17 answers CLAUDE.md §18's question: "given limited people, time, and capacity, what should this organization work on first?" See [the PRD](PRD-phase-17-prioritization.md) for the original product design (written and confirmed with the user before any code was written — the first CapacityOS phase that is a new product module, not an extension of existing infrastructure), [ADR 0017](adr/0017-prioritization-engine.md) for the v1 slice, [ADR 0018](adr/0018-prioritization-frameworks-and-dependencies.md) for the framework-set/criteria-editing/dependency-graph slice that followed it, [ADR 0019](adr/0019-ai-priority-explanation.md) for the AI explanation capability built on top of both, [ADR 0020](adr/0020-scenario-priority-comparison.md) for the scenario-vs-baseline comparison that resolved the one product decision Phase 19 left open, [ADR 0021](adr/0021-portfolio-snapshots.md) for the point-in-time saved ranking that resolves the other item both those phases left named but unbuilt, [ADR 0022](adr/0022-portfolio-snapshot-comparison.md) for the snapshot diff/trend layer built on top of it, [ADR 0023](adr/0023-ai-snapshot-comparison-explanation.md) for the AI explanation of that diff/trend layer, [ADR 0024](adr/0024-portfolio-snapshot-trend.md) for the multi-snapshot score-over-time visualization built on top of the same frozen data, and [ADR 0025](adr/0025-wsjf-breakdown-visualization.md) for the PRD's own WSJF breakdown visualization built on top of the live portfolio ranking; this section is the resulting vocabulary and rules.

### `PrioritizationFramework` — an organization-chosen method, never a CapacityOS default

CLAUDE.md §18 is explicit: "do not prescribe one prioritization framework as universally correct." An organization defines however many frameworks it wants (`name`, `framework_type`, its `PrioritizationCriterion` rows). Five framework types are supported, all named in CLAUDE.md §18: **RICE** (`(Reach x Impact x Confidence) / Effort`), **ICE** (`(Impact + Confidence + Ease) / 3`), **WSJF** (`(Business Value + Time Criticality + Risk Reduction/Opportunity Enablement) / Job Size`, SAFe's own formula) — each with fixed, non-organization-editable criteria seeded automatically from `app/domain/prioritization.py::FIXED_CRITERION_KEYS` — **Weighted Scoring** (`Σ value x weight` across fully organization-defined, editable criteria), and **MoSCoW** (categorical: `Must`/`Should`/`Could`/`Won't`, no criteria and no numeric score at all — CLAUDE.md §17's "do not create scores that imply false precision" applied here exactly as it is to Risk). All five are routed through the one dispatch point, `app/domain/prioritization.py::calculate_priority_score`.

### A score is always derived, never stored

Only the human-entered criterion **values** (`ProjectPriorityCriterionValue`, or — for MoSCoW only — the `category` column directly on `ProjectPriorityScore`) are persisted — the computed score itself is recalculated on every read from those values plus the framework's current criteria/weights, the same "derive, never cache" discipline `Risk.exposure` and every Scenario result already follow. A score with incomplete inputs reports `score: null` and exactly which criteria are `missing_criteria`, never a value computed by treating a gap as zero; the portfolio ranking lists such a project (or an un-categorized MoSCoW score) last, unranked.

### Editing a Weighted Scoring framework's criteria after creation

A Weighted Scoring framework's criteria can be added, renamed, reweighted, and removed after creation via three dedicated endpoints (never a bulk field on the framework's own PATCH, so a route shaped like a generic update can't accidentally reach a fixed criterion). Every one of the three independently re-checks `PrioritizationCriterion.is_editable` server-side — RICE/ICE/WSJF/MoSCoW's criteria stay unreachable through these routes regardless of what the frontend shows. A criterion's `key` never changes on rename, so a rename can never orphan a previously recorded `ProjectPriorityCriterionValue`. Removing a framework's last remaining criterion is rejected — the same "needs at least one" invariant enforced at creation time.

### `ProjectDependency` — one directed edge, three types

A project may `block`, `relate to`, or `enable` another (`ProjectDependencyType`) — one directed edge per (from, to, type) triple, with the inverse ("blocked by") view always derived by querying the other direction rather than stored separately (matching `ProjectAccessGrant`'s "store one direction, derive the inverse" precedent). Cycle detection (`app/domain/prioritization.py::detects_cycle`) only runs against `blocks` edges — `related`/`enables` don't imply a strict ordering, so a graph mixing all three types isn't meaningful to cycle-check. A dependency is created or deleted only through its `from_project`'s URL (`/api/v1/projects/{id}/dependencies`) — the same project-nesting shape as Risk/Stakeholder/`ProjectPriorityScore` — gated by the existing `Permission.PRIORITIZATION_SCORE` + `require_project_access`, no new permission introduced.

### Framework management vs. scoring — two different authorization tiers

Creating or editing a `PrioritizationFramework` (including its criteria) is Owner/Admin only (`Permission.PRIORITIZATION_MANAGE`) — deliberately stricter than Skill's Manager-writable org-wide-catalog precedent, since a framework change reshuffles every project's rank across the whole organization at once. Scoring one specific project under an existing framework, and creating/deleting its dependencies, is Manager+, gated by the same Phase 11 `ProjectAccessGrant` mechanism Risk/Stakeholder/Allocation already use (`Permission.PRIORITIZATION_SCORE` + `require_project_access`) — "Managers can score projects (and record their dependencies) they manage," not the whole portfolio.

### AI priority explanation — interpretation only, never a second scoring engine

`POST /api/v1/ai/explain-priority` (`AIService.explain_priority`) explains an *existing* `ProjectPriorityScore` — a fifth capability on the unchanged Phase 8 pipeline (`AIContextBuilder`/`AIService`/grounding), alongside `summarize`/`explain-signal`/`explain-scenario`/`ask`. `AIContextBuilder.build_for_priority_score` calls `ProjectPriorityScoreService.get` verbatim; no score, breakdown, or category is ever recalculated by the AI layer (CLAUDE.md §4/§21 — AI is never the source of truth for a calculation). Gated by `Permission.AI_USE` only, granted to every role, exactly like every other AI endpoint — no new permission, no new grant-scoping, since the underlying read already goes through the same organization-scoped `ProjectPriorityScoreService` every other prioritization route uses.

### Scenario-vs-baseline prioritization comparison — explicit, scenario-scoped overrides

A `Scenario` can declare hypothetical prioritization inputs for a project under a framework — `ScenarioPriorityOverride` (one row per (scenario, project, framework), a JSON `values` dict of criterion_key -> Decimal-as-string plus an optional MoSCoW `category`). This resolves the exact product decision [ADR 0019](adr/0019-ai-priority-explanation.md) deferred: no `ScenarioOperationType` touches a criterion value, and no criterion is derived from allocation/capacity data anywhere — an override is a deliberate, human-declared "what if this input were different," never an automatic one. It is **not** a `ScenarioOperation` (no replay/ordering semantics, never touches capacity) and it never mutates the real, persisted `ProjectPriorityScore` — it is read alongside it, at comparison time, and merged in memory only (`GET /api/v1/scenarios/{id}/priority-comparison?framework_id=`). Both the baseline ranking and the scenario ranking are computed through the identical `calculate_priority_score` engine every other framework type already uses, and through one shared ranking function (`app/domain/prioritization.py::rank_priority_results`, also used by the live portfolio board) — never a second scoring or ranking engine. A project's `changed` flag compares the two computed results (score, category, rank) directly, never inferring a change from "an override exists," so a no-op override or an unaffected project correctly reports no change; the comparison's own `has_changes` flag is `any(item.changed)`, so a scenario with no real effect explicitly says so. Gated by the existing `SCENARIO_READ`/`WRITE`/`DELETE` permissions — role-only, no `ProjectAccessGrant` — a deliberate choice: creating a hypothetical override is a Scenario-authoring action, not a real-score-authoring action, so it doesn't share `ProjectPriorityScore`'s grant-scoped `PRIORITIZATION_SCORE` gate.

### AI priority explanation — interpretation only, never a second scoring engine

`POST /api/v1/ai/explain-priority` (`AIService.explain_priority`) explains an *existing* `ProjectPriorityScore` — a fifth capability on the unchanged Phase 8 pipeline (`AIContextBuilder`/`AIService`/grounding), alongside `summarize`/`explain-signal`/`explain-scenario`/`ask`. `AIContextBuilder.build_for_priority_score` calls `ProjectPriorityScoreService.get` verbatim; no score, breakdown, or category is ever recalculated by the AI layer (CLAUDE.md §4/§21 — AI is never the source of truth for a calculation). Gated by `Permission.AI_USE` only, granted to every role, exactly like every other AI endpoint — no new permission, no new grant-scoping, since the underlying read already goes through the same organization-scoped `ProjectPriorityScoreService` every other prioritization route uses.

### `PortfolioSnapshot` — an explicit, immutable, point-in-time saved ranking

`POST /api/v1/prioritization/snapshots` freezes the CURRENT live ranking for one framework (`ProjectPriorityScoreService.rank_portfolio`, unchanged — never a second ranking computation) into a standalone, immutable row. Every value the frontend would need to redraw that historical ranking — `framework_name`, `framework_type`, and one entry per project (`project_name`, `score`, `rank`, `missing_criteria`, `breakdown`, `category`) — is copied out at capture time into the row itself, not re-derived from a live join: a project rename, a re-score, a project deletion, or a framework rename must never change what an already-taken snapshot shows, since the entire purpose of this entity is historical reproducibility (verified live: re-scoring a project after taking a snapshot left that snapshot's frozen score untouched; a later new snapshot correctly reflected the updated score). This is a deliberately different discipline from every other Phase 17-20 entity: `ProjectPriorityScore`/`ScenarioPriorityOverride` are inputs a score is *derived from* at read time; a `PortfolioSnapshot` is the derived *output*, captured once and never recomputed again. No PATCH/DELETE route exists — immutable and append-only, matching `AuditEvent`'s own shape exactly. Creating one is gated by `Permission.PRIORITIZATION_MANAGE` (Admin/Owner only, reused unchanged) rather than the project-instance-scoped `PRIORITIZATION_SCORE` — a snapshot spans every project scored under a framework at once, not a single project a Manager might hold a grant on, matching framework CRUD's own "org-wide configuration surface" reasoning exactly. See [ADR 0021](adr/0021-portfolio-snapshots.md).

### Snapshot diff/trend — pure comparison over already-frozen data, no scoring engine involved

`GET /api/v1/prioritization/snapshots/compare?from_snapshot_id=&to_snapshot_id=` diffs two already-taken, immutable `PortfolioSnapshot`s. `app/domain/portfolio_snapshot.py::compare_snapshot_entries` is pure and DB-free — it never imports `calculate_priority_score` or any other piece of the scoring engine, because a snapshot's entries are historical facts already computed once by Phase 17-18's engine at capture time; a diff is nothing more than comparing those frozen facts pairwise. Each project appearing in either snapshot gets one of four statuses — `entered` (in `to` only), `left` (in `from` only), `changed` (in both, but `(rank, score, category)` differs), or `unchanged` (in both, identical) — compared as a tuple, not per-field, so a project whose rank moved only because a new, higher-scoring project entered the ranking is correctly `changed` even though its own score never moved (rank is relative to the whole ranked set, not an intrinsic property of one project). Comparing two snapshots from different frameworks is rejected (`DomainValidationError`, 422) — a RICE score and a WSJF score aren't comparable numbers, so this is refused rather than silently producing a meaningless diff. The comparison itself is never persisted — computed fresh on every read, the same "derive, never cache" discipline every Phase 17-21 result follows (verified live: reading a snapshot immediately before and after comparing it left its frozen `entries` byte-identical). Gated by the existing `Permission.PRIORITIZATION_READ` (every role, reused unchanged) — no new permission, no audit event, matching every other read in this router. See [ADR 0022](adr/0022-portfolio-snapshot-comparison.md).

### AI snapshot comparison explanation — interpretation only, never a second diff engine

`POST /api/v1/ai/explain-snapshot-comparison` (`AIService.explain_snapshot_comparison`) explains an *existing* Phase 22 snapshot comparison — a sixth capability on the unchanged Phase 8 pipeline (`AIContextBuilder`/`AIService`/grounding), alongside `summarize`/`explain-signal`/`explain-scenario`/`explain-priority`. `AIContextBuilder.build_for_snapshot_comparison` calls `PortfolioSnapshotService.compare` verbatim; no status (entered/left/changed/unchanged), rank, score, or category is ever recomputed by the AI layer (CLAUDE.md §4/§21), and the framework-mismatch (422) and cross-organization/unknown-snapshot (404) behavior that call already enforces carries straight through to this route with no new authorization or tenancy code. A new `snapshot_comparison` grounding reference type adds one `(type, project_id)` pair per comparison item — unlike `priority_score`'s single fact, a comparison is a set of per-project facts, so this follows the same "one reference per collection member" shape `signal`/`skill_coverage` already established rather than a new pattern. Gated by `Permission.AI_USE` only, granted to every role, exactly like every other AI endpoint — no new permission, no new grant-scoping. See [ADR 0023](adr/0023-ai-snapshot-comparison-explanation.md).

### Multi-snapshot score trend — a frontend reshaping of already-frozen data, zero backend changes

A score-over-time line chart across two or more Phase 21 snapshots (`features/prioritization/utils/snapshotTrend.ts::buildSnapshotTrend`, `features/prioritization/components/PortfolioSnapshotTrendChart.tsx`). Unlike every other Phase 17-23 capability, this one required no new backend code at all: `GET /api/v1/prioritization/snapshots` already returns every selected snapshot's frozen `entries` with `score`, sufficient to build a per-project time series with nothing new to fetch. `buildSnapshotTrend` is a pure, unit-tested function mirroring `compare_snapshot_entries`'s own discipline translated to the frontend — it never recomputes a score, never fabricates a value for a snapshot where a project has none (represented as a gap, never interpolated), deduplicates a repeated snapshot selection, and never mutates the snapshots it reads. Only same-framework snapshots can ever be selected together, since the picker only ever offers snapshots already fetched for one `framework_id` — the same reasoning ADR 0022 established for the two-point diff, extended structurally rather than re-validated. A MoSCoW framework's snapshots (or any selection with no numeric score at all) render an explanatory empty state rather than a misleading blank chart, since `calculate_moscow_result` never produces a numeric score to plot. A rank-over-time variant was audited and explicitly not selected: `rank_priority_results` gives a MoSCoW result `rank=None` too, and a rank trend risks conflating a project's own change with a sibling project entering/leaving the ranking — the same confound ADR 0022 already flagged for the two-point diff's rank field. See [ADR 0024](adr/0024-portfolio-snapshot-trend.md).

### WSJF breakdown — one of the PRD's own five §15 visualizations, zero backend changes

A bar chart, per project scored under a WSJF framework, of the four fixed criteria `app/domain/prioritization.py::WSJF_CRITERION_KEYS` already computes (`features/prioritization/utils/wsjfBreakdown.ts::buildWsjfBreakdown`, `features/prioritization/components/WsjfBreakdownChart.tsx`). Like Phase 24, this required no new backend code: `GET /api/v1/prioritization/portfolio` (unchanged since Phase 17) already returns every scored project's `breakdown` dict with all four criterion values. `buildWsjfBreakdown` copies each value verbatim — never recomputing anything — and excludes any project without a complete WSJF score (`score !== null`, which `calculate_wsjf_score` guarantees means all four criteria are present) rather than plotting a fabricated zero. The PRD's own §15 text ("stacked bar of the four inputs") does not specify how to stack them; a literal four-way stack would be misleading, since `business_value`/`time_criticality`/`risk_reduction_opportunity_enablement` sum to a real, meaningful quantity (SAFe's own "Cost of Delay," the WSJF numerator) but `job_size` is the formula's *divisor*, not a fourth additive term — stacking it in would produce a combined bar height that is not the score, not Cost of Delay, and not any other meaningful number (CLAUDE.md §17/§29's "no false precision"/"no misleading chart"). The three additive criteria are stacked together; `job_size` renders as its own adjacent bar in the same chart — all four values are still shown, together, per project. See [ADR 0025](adr/0025-wsjf-breakdown-visualization.md).

### What's still deferred

No AI interpretation of the Phase 20 scenario comparison — that phase's own brief was explicit that AI may only interpret an established deterministic comparison, never be its source, and left this for a future phase to consider deliberately. No rank-over-time or toggleable score/rank variant of the Phase 24 trend chart — audited and explicitly not selected (a MoSCoW score and rank are each always null, and rank conflates a project's own change with the portfolio around it). No Priority Explanation frontend panel beyond the single `ExplainPriorityButton`; the remaining four Recharts visualizations the PRD's own §15 names (Priority-vs-Effort scatter, Capacity-vs-Priority matrix, Risk-vs-Value quadrant, dependency timeline) are still unbuilt — a Phase 25 audit found Capacity-vs-Priority and Risk-vs-Value each carry real, unspecified cross-domain ambiguity (whose capacity over what period; which of a project's several risks), and the dependency timeline remains blocked (`ProjectDependency` still has no date/duration data). No Import/Export registration for `ProjectPriorityScore`, `ProjectDependency`, `ScenarioPriorityOverride`, or `PortfolioSnapshot` (deferred, matching Risk/Stakeholder's own Phase 13/14 precedent) — a Phase 22 audit of the actual import/export code confirmed the gap directly and found a further open question: neither Risk nor Stakeholder has a Person/Project-style natural identity key for CSV upsert-matching, reconfirmed still open by the Phase 25 audit. No snapshot of a scenario's hypothetical (rather than baseline) ranking — audited for Phase 22 and re-confirmed by the Phase 23, Phase 24, and Phase 25 audits (directly against current code — `ScenarioService.delete` still hard-deletes) as still genuinely blocked on a product decision, not merely unbuilt: `Scenario` (unlike `PrioritizationFramework`) supports a real, non-soft delete, so what happens to a scenario snapshot when its scenario is deleted needs deciding before this is buildable. No membership/user-management frontend — re-confirmed fully backend-ready with zero frontend surface by the Phase 22 and Phase 25 audits, but not selected for either phase (a materially larger multi-flow vertical slice than a single chart). Each is a named, deliberately scoped boundary confirmed with the user before implementation — see the PRD's "Recommended v1 slice," ADR 0017's Consequences, ADR 0018's Consequences, ADR 0019's Consequences, ADR 0020's Consequences, ADR 0021's Consequences, ADR 0022's Consequences, ADR 0023's Consequences, ADR 0024's Consequences, and ADR 0025's Consequences for the full list and reasoning.
