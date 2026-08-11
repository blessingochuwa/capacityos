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
