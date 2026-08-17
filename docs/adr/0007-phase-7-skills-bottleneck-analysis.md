# ADR 0007: Phase 7 skills & bottleneck analysis decisions

- **Status:** Accepted
- **Date:** 2026-08-17

## Context

Phases 1–6 answer "how much capacity does a person/team/project have?" without
ever asking whether that capacity is the *right kind*. A team can look
perfectly healthy in aggregate hours and still be unable to deliver, because
the specific capability the work needs is held by nobody, or by one person
who is already booked elsewhere. CLAUDE.md §14 names this explicitly: "A team
may have spare aggregate capacity while a specific skill is constrained."

Phase 7's job is to make that distinction visible — SKILL capacity vs TOTAL
capacity — and to surface the resulting constraints (skill gaps, single
points of failure, concentrated capability) as evidence, not
recommendations. It must not become a second capacity engine, a second
signal framework, or a second import/export system; every one of those
already exists (Phase 2, Phase 5, Phase 6 respectively) and Phase 7's entire
job is to compose on top of them.

## Decisions

**Three new entities, normalized, no JSON blobs.** `Skill` (name, optional
description/category, `is_active`), `PersonSkill` (person × skill, unique
pair, an explicit `proficiency`, optional notes), `ProjectSkillRequirement`
(project × skill, unique pair, `required_hours`, optional
`minimum_proficiency`). Proficiency is never inferred from job title,
allocation history, or AI — it is a value someone explicitly recorded, full
stop (CLAUDE.md §21, spec §4).

**Proficiency is a fixed, DB-CHECK-constrained 5-level scale** (`beginner` /
`working` / `proficient` / `advanced` / `expert`), stored as a `StrEnum` like
`EmploymentStatus`/`ProjectStatus` (fixed business vocabulary), *not* like
`AvailabilityType` (open vocabulary, no DB constraint). Ordering is not
expressed by enum declaration order — Python's `StrEnum` has none — but by an
explicit `PROFICIENCY_RANK: dict[SkillProficiency, int]` table in
`app/domain/skills.py`, the single place proficiency comparison happens.
This matches the codebase's existing convention of explicit rank tables
(`_SEVERITY_RANK`, `_TYPE_RANK` in `app/services/insight_service.py`) over
relying on incidental ordering.

**`Skill.is_active` is a soft delete, never a hard `DELETE`.** `PersonSkill`
and `ProjectSkillRequirement` reference a skill by id; hard-deleting a skill
would either cascade-destroy historical proficiency/requirement records or
leave orphaned foreign keys, and would silently change what past coverage
calculations "would have" reported. Deactivating (`DELETE
/api/v1/skills/{id}` sets `is_active=False`) preserves history. Every
qualification/coverage/signal calculation explicitly filters out inactive
skills, even when a stale `PersonSkill`/`ProjectSkillRequirement` row still
references one — this is the CLAUDE.md invariant "inactive skills should not
accidentally appear as active requirements," enforced at read time rather
than by trying to keep write-time state perfectly consistent.

**Qualification = skill + proficiency + capacity, three independent
conditions, never conflated.** A person qualifies for a requirement when (1)
they hold the skill, active, (2) their `PROFICIENCY_RANK` meets the
requirement's `minimum_proficiency` (or the requirement has none, meaning any
recorded proficiency qualifies), and (3) they have capacity — but "capacity"
for a qualified person is a *Phase 7 derived quantity*
(`qualified_available_hours = max(remaining_capacity, 0)`), not a
redefinition of Phase 2's `remaining_capacity`. A negative remaining capacity
(over-allocated) is real information Phase 2 preserves; Phase 7 clamps it
only when asking "how much of this person's spare time can new qualified
work draw on" — a genuinely different question. Everywhere the population of
"who holds this skill at all" matters (single-point-of-failure detection,
concentration), an over-committed holder still counts as a holder; only the
*hours* contribution clamps to zero.

**Skill-aware capacity is composed, never recalculated.** Every
`remaining_capacity` number Phase 7 uses comes from
`app/services/planning_facts.py::load_people_facts` +
`app/domain/capacity.py::calculate_period_capacity` — the identical batched
pipeline `CapacityService` and `InsightService` already use. `app/domain/
skills.py` contains exactly two new calculations: `calculate_skill_coverage`
(required hours vs. summed qualified-available hours → `coverage_ratio`,
`gap_hours`) and `calculate_skill_concentration` (how a skill's qualified
available capacity is distributed among its holders). Neither touches a
schedule, exception, or allocation row directly.

**Project skill coverage is evaluated against the ORG-WIDE population of
skill holders, not just people already allocated to the project.** A project
has no fixed "eligible roster" the way a team has members — Allocation rows
express *current* assignment, not eligibility. Restricting coverage to
current contributors would make "do we have the capacity to do this?"
unanswerable for a project that hasn't started yet. Team skill capacity, by
contrast, *is* scoped to that team's members (`TeamMembership`), since a
team's roster is a real, stored boundary.

**Team skill capacity reports supply only — no invented "team demand."**
Section 6 of the brief describes a team view with "required/relevant
demand," but Team has no stored or derivable skill demand of its own; only
`ProjectSkillRequirement` carries one. Inventing a team-level demand
aggregation (e.g. summing the requirements of every project a team's members
touch) would require choosing an attribution rule with no data to justify
it — the same category of fabricated-distribution problem ADR 0004 already
declined to solve for allocation-vs-project demand. `GET
/api/v1/teams/{id}/skill-capacity` therefore returns qualified capacity and
holders per skill, nothing else; demand-vs-supply comparison is expressed at
the project level, where a real stored requirement exists.

**"Allocated capacity associated with Skill X" is not attempted.**
`Allocation` carries no skill dimension — a person's hours are attributed to
a project, never to a specific capability within it. Rather than invent a
proportional-attribution rule (e.g. "assume all of this person's allocated
hours on this project count toward the skill it requires"), Phase 7 reports
only what the data actually supports: a qualified person's *available*
capacity, never a skill-specific *allocated* number. This is a known,
deliberate limitation — see Known Limitations below.

**Bottleneck signals plug into the EXISTING Phase 5 framework — no
`/api/v1/bottlenecks/` prefix.** Three new `SignalType` members
(`skill_gap`, `single_skill_holder`, `skill_concentration`) were added to the
same flat `SignalRead` model, the same `_TYPE_RANK`/`_prioritize` ordering,
and the same `get_project_signals`/`get_team_signals` endpoints every other
signal already flows through. This is a deliberate deviation from the
phase brief's illustrative `GET .../bottlenecks` endpoint list: CLAUDE.md
§14 and §9's "do not create a second signal system" instruction takes
precedence over an illustrative path name. The practical effect: the
existing Insights page (`features/insights/`) shows skill bottlenecks
automatically, with zero new frontend routes, once `Signal`'s TypeScript
type and `SignalDetailPanel` gained the matching optional fields.

**Signal scope: `skill_gap` is project-scoped only** (a `ProjectSkillRequirement`
is the only thing with a `required_hours` to fall short of).
**`single_skill_holder`/`skill_concentration` are both project- and
team-scoped** (holder concentration is meaningful anywhere a population of
people can be asked "how many of you hold this skill"). Person-level skill
signals were not added — a signal about an individual's own skill inventory
doesn't fit the "where should I look across many people" framing every other
Phase 5 signal shares.

**Severity rules, mirroring `capacity_signal_severity`'s existing
discipline:**

| Signal | Severity | Rule |
|---|---|---|
| `skill_gap` | `critical` | `qualified_available_hours == 0` — a confirmed blocker, no qualified spare capacity exists at all |
| `skill_gap` | `warning` | `qualified_available_hours > 0` but `gap_hours > 0` — partial coverage, worth a look |
| `single_skill_holder` | `warning` | exactly one qualified holder — a real risk (single point of failure) even though nothing has failed yet |
| `skill_concentration` | `info` | exactly two qualified holders — a structural observation, same severity Phase 5 already gives `concentration_risk` |

**Concentration/SPOF gating is an existence condition (holder count ∈ {1,
2}), never a magnitude threshold** — the same discipline ADR 0005 locked in
for `calculate_concentration`/`calculate_imbalance`. `holder_count > 2`
returns `None`: not concentrated. No invented percentage cutoff exists
anywhere in this phase (`calculate_skill_concentration`'s `top_n` is a
*reporting window*, matching `calculate_concentration`'s own `top_n=2`
precedent, not a pass/fail line). `single_skill_holder` and
`skill_concentration` deliberately use SEPARATE `SignalRead` fields
(`skill_holder_*`) from the pre-existing `concentration_*` fields —
`concentration_risk` is project *allocation* concentration (Phase 5); this
is skill-*holder* concentration (Phase 7), a different fact about a
different population that can legitimately co-occur on the same project.

**"Person dependency" is not a separate signal type.** The brief's example
("Person A is carrying 68% of the team's allocated hours for Skill Z") is
already exactly what `skill_concentration`'s `skill_holder_ratio` reports —
the top holder's share of a skill's qualified available capacity.
Duplicating it as a fourth signal type would be reporting the same
computed fact under two names.

**Import/export: three entities registered into the EXISTING Phase 6
system**, not a parallel one. `Skill` (identity: `name`, like `Team`),
`PersonSkill` (identity: resolved `(person, skill)` pair, WITH an update
path — unlike `TeamMembership`'s create-or-noop-only pattern, because
proficiency/notes are mutable), `ProjectSkillRequirement` (identity: resolved
`(project, skill)` pair, also with an update path for
`required_hours`/`minimum_proficiency`/notes). Both composite-identity
entities needed a genuinely new normalize-function shape: a hybrid of
`TeamMembership`'s composite-key existence check and `Allocation`'s
external-id update-path diffing — written as `normalize_person_skill_row`/
`normalize_project_skill_requirement_row` in `app/domain/
import_export_diff.py`. A referenced-but-inactive skill is rejected on
CREATE with `domain_rule_violated` (mirroring the API's own
`PersonSkillService.add`/`ProjectSkillRequirementService.add` checks) —
existing rows referencing a since-deactivated skill are left untouched by
import, same as everywhere else. `Skill.is_active` on a CSV row is ignored
on create (`SkillCreate` has no such field — new skills always import
active) but respected on update, so a re-import can deactivate/reactivate a
skill the same way the API's `PATCH` can.

**Deliberately excluded from import/export:** derived coverage/capacity
results (recalculated from source facts every time, same reasoning ADR
0006 already applied to Scenario/Insight data).

**Scenario integration: a documented seam, not a built integration.** Full
"does this hypothetical resource close this skill gap?" support would
require `AddHypotheticalResourceOperation` (Phase 4) to carry skill/
proficiency data it doesn't have today, and `ScenarioCalculationService`'s
`PlanningState` to grow a skills dimension alongside its schedule/exception/
allocation facts. That is a real, coherent piece of work, but bolting it on
inside this phase — under time pressure, without its own design pass — is
exactly the kind of fragile code the phase brief warns against. The clean
seam that exists today: `PlanningState`'s virtual person ids already work
identically to real `Person.id`s everywhere `app/domain/skills.py` looks
things up, so a future phase can extend `AddHypotheticalResourceOperation`
with an optional skill/proficiency and feed the resulting virtual
`PersonSkill`-shaped fact through the unmodified qualification functions
here — no engine change required when that phase arrives. Not built now;
recorded as the recommended Phase 8+ (or earlier, if reprioritized) scope
extension.

**API surface**, thin per CLAUDE.md §6, layered per the existing repository/
service/domain/schema convention:

```text
/api/v1/skills                                    CRUD (+ deactivate)
/api/v1/people/{id}/skills                         nested CRUD (mirrors /teams/{id}/members)
/api/v1/projects/{id}/skill-requirements           nested CRUD
/api/v1/projects/{id}/skill-coverage               GET, read-only, date-ranged
/api/v1/teams/{id}/skill-capacity                  GET, read-only, date-ranged
```

No speculative endpoints — every route exists because a frontend view or a
documented calculation needs it.

**Performance:** every coverage/capacity endpoint batches its
`load_people_facts` call once for the FULL set of relevant people (every
qualified holder across every requirement on a project, or every team
member), never once per requirement/skill/person. `SkillRepository.
person_counts` batches the "how many people hold each skill" count for a
whole page of skills with one `GROUP BY` query, never one `COUNT` per row.

## Consequences

- 3 new tables (`skills`, `person_skills`, `project_skill_requirements`), one
  migration (`e79054e949ad`), no changes to any Phase 1–6 table.
- 1 new domain module (`app/domain/skills.py`, pure, no I/O), 3 new
  repositories, 3 new CRUD services, 1 new orchestration service
  (`SkillCapacityService`), 6 new/extended API route files.
- Phase 5's `InsightService` grew 3 new private methods and 3 new
  `SignalType`s; its public method signatures and every existing signal's
  behavior are unchanged (regression-tested: all 346 pre-Phase-7 backend
  tests and 87 pre-Phase-7 frontend tests still pass unmodified).
- Phase 6's `ENTITY_COLUMNS`, `ImportEntityType`, `ImportService`,
  `ExportService` each grew by exactly the pattern every prior entity
  already established.
- Backend: +72 tests (18 domain, 23 CRUD/coverage API, 8 signal-integration,
  23 import/export), 418 total, all passing. Frontend: +11 component tests,
  98 total, all passing.
- **A real bug was caught by live browser/API verification, not by the unit
  suite**: `_skill_gap_signal` initially omitted `skill_id`/`skill_label` on
  the emitted `SignalRead`, even though the schema's own field-group comment
  documented them as populated for that type. Caught by inspecting the raw
  API response during golden-path testing, fixed, and locked in with a new
  regression assertion in `test_skill_bottleneck_signals.py`. This is the
  reason Step 29's "do not rely solely on unit tests" instruction exists —
  the unit tests were internally consistent with the bug and would not have
  caught it alone.
- **Known limitation:** "allocated hours associated with a skill" cannot be
  reported — Allocation has no skill dimension, and Phase 7 deliberately
  declines to invent an attribution rule for it (see Decisions). A future
  phase could add an optional `skill_id` to `Allocation` or a per-allocation
  skill-hours breakdown if this becomes a real product need.
- **Known limitation:** team skill capacity has no demand comparison (supply
  only) — see Decisions.
- **Deferred:** full scenario/skill integration (documented seam only, not
  built — see Decisions).
- **Deferred, matching the phase boundary:** AI, authentication, Slack/Jira/
  Linear/calendar integrations, automated staffing recommendations, skill
  inference of any kind.
