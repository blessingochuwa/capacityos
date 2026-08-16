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

| Entity | Answers | Lives in |
|---|---|---|
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
