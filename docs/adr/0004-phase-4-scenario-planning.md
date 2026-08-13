# ADR 0004: Phase 4 scenario planning decisions

- **Status:** Accepted
- **Date:** 2026-08-13

## Context

Phases 1–3 gave CapacityOS trustworthy source data (Person, Team, Project, Allocation, WorkingSchedule, AvailabilityException), a deterministic capacity engine (`app/domain/capacity.py`), and read-only planning views. Phase 4 adds the ability to ask "what if?" — add a hypothetical allocation, move work between people, model someone going on leave, add a hypothetical hire — and see the effect on utilization, over-allocation, and remaining capacity, without ever writing to production data (CLAUDE.md §19).

The task spec's own architectural principle (its §2) is the one non-negotiable constraint: the capacity engine must stay the single source of truth. A scenario is not a second calculator; it is a way of building a hypothetical set of *facts* and running them through the exact same engine Phase 2 already validated.

## Decisions

**No engine refactor was required.** `app/domain/capacity.py`'s `calculate_period_capacity`/`aggregate_team_capacity`/`calculate_project_demand` already take plain fact dataclasses (`ScheduleFact`, `AvailabilityExceptionFact`, `AllocationFact`, `ProjectAllocationFact`) and never touch the database — and `aggregate_team_capacity` takes an arbitrary `Sequence[PersonCapacityResult]`, not literally a `Team`. This was the seam scenario planning needed. `app/domain/capacity.py` and `app/domain/dates.py` are untouched by this phase.

**The only refactor: extracting `app/services/planning_facts.py` out of `CapacityService`.** `_schedule_to_fact`/`_exception_to_fact`/`_allocation_to_fact` and the batched-loading shape in `get_team_capacity` were private to `app/services/capacity.py`. They're now public functions in their own module (`schedule_to_fact`, `exception_to_fact`, `allocation_to_fact`, `load_people_facts`, plus the shared `group_by` helper), used by both `CapacityService` (Phase 2/3, unchanged behavior) and `ScenarioCalculationService` (Phase 4). This is behavior-preserving by construction — same repository calls, same fact construction — and proven by the existing Phase 2/3 test suite passing unchanged after the extraction.

**Scenario operations: 8 typed dataclasses, not the prompt's original 6 categories.** `Project` has no stored demand/hours field — demand is *derived* from `Allocation` rows (`docs/domain-concepts.md`: "a project has demand, not capacity of its own"). Inventing a distribution rule for "increase this project's demand by 20h" across an arbitrary number of existing allocations would be an undocumented business rule, which the spec explicitly warns against. Instead:

| `operation_type` | Answers |
|---|---|
| `add_allocation` | "add this project/assignment", "add N hours to X" |
| `adjust_allocation` | "increase/decrease this allocation's hours", "this allocation starts earlier" (targets a real, baseline allocation only — see below) |
| `remove_allocation` | "cancel this assignment" |
| `move_allocation` | "move 20h from Alex to Sarah" — `hours: None` moves the whole allocation; a value splits it, remainder stays with the original owner |
| `shift_project` | "project starts 2 weeks earlier" — shifts every allocation on that project, as of that point in the operation sequence, by `day_offset` days |
| `availability_override` | "unavailable for 3 days", "50% available" — clips baseline exceptions in the window, then adds a replacement |
| `availability_clear` | "returns from leave early" — clips baseline exceptions in the window, adds nothing (defers to the normal schedule) |
| `add_hypothetical_resource` | "would hiring someone solve this?" — the *operation's own id* becomes the virtual person_id for later `add_allocation` ops in the same scenario; no Person row is ever created |

Every example question in the prompt's own list is answerable through this set.

**Operations apply in stored `sequence` order, not creation-timestamp order or payload-array order.** `apply_scenario_operations` (`app/domain/scenario.py`) explicitly re-sorts by `sequence` before applying. A later operation sees the effect of every earlier one — a `shift_project` after an `add_allocation` on that project shifts the new allocation too; one before it doesn't. This is the documented conflict-resolution rule. `ScenarioOperation.sequence` is assigned server-side as `max(existing sequence) + 1` (not a row count, so a deleted operation's sequence number can never collide with a still-existing one).

**`adjust_allocation`/`remove_allocation`/`move_allocation` only target real, baseline allocations — never an allocation another operation in the same scenario just created.** This is a deliberate scope limitation, not an oversight: supporting it would require every operation to track and resolve synthetic ids produced by earlier operations (beyond the one necessary case, hypothetical-resource person ids, which the domain layer already treats as an ordinary id since `apply_scenario_operations` doesn't distinguish real from hypothetical people at all). To adjust or remove a scenario-added allocation, remove the `add_allocation` operation and add a corrected one.

**Persistence: `Scenario` + `ScenarioOperation`, one Alembic migration, `payload` as JSON validated through a Pydantic discriminated union — never a raw dict.** `ScenarioOperationCreate`/`Read` (`app/schemas/scenario.py`) are `Annotated[Union[...8 payload models...], Field(discriminator="operation_type")]`. `operation_payload_to_dict`/`operation_payload_from_dict` are the *only* two places a payload crosses the JSON boundary — the domain layer never sees an unvalidated dict. A table-per-operation-type was considered and rejected as 8x the migration/repository surface for a first version, with no benefit over a validated discriminated union. `operation_type` itself is a real column (`StrEnum` + DB `CHECK`, same pattern as `AllocationUnit`/`EmploymentStatus`) — only the type-specific fields live in JSON.

**No FK from `payload`'s embedded UUIDs to their tables.** A payload may legitimately reference a hypothetical id that was never a real row (an `add_hypothetical_resource` operation's own id, used as a person_id by a later `add_allocation`). Referenced real ids (person/project/allocation) are existence-checked by `ScenarioService` at write time instead. **Known limitation:** if a referenced real allocation is later deleted from production, recalculating that scenario raises a clear `DomainValidationError` ("...no longer exists in the current plan") rather than silently skipping the operation — acceptable for a first version, and surfaced loudly rather than papered over.

**`created_by` is nullable free text, not a foreign key.** CapacityOS has no authentication (CLAUDE.md §32); the prompt is explicit that user identity must not be fabricated. The field exists so a future auth phase can populate it without a schema change.

**No caching layer — `POST /calculate`, `GET /results`, and `GET /comparison` all recompute from current baseline data on every call.** Given the same baseline data and the same stored operations, computation is already deterministic (prompt §5). Caching a result would introduce a staleness question — what happens when baseline data changes after a scenario was calculated? — for no measured performance benefit (CLAUDE.md §26: don't optimize without evidence). `POST /calculate` exists as an explicit, separate action from the two GETs purely so the frontend never recalculates on every keystroke while editing the change list (prompt §13); it happens to return the identical shape `GET /results` does.

**Frontend mirrors this: editing the change list does not auto-refetch results/comparison.** `useCreateScenarioOperation`/`useUpdateScenarioOperation`/`useDeleteScenarioOperation` (`apps/web/src/features/scenarios/hooks/useScenarioOperationMutations.ts`) invalidate only the operations-list query. If they also invalidated the results/comparison queries, an already-mounted, already-`enabled` query (the workspace, after the first Calculate) would auto-refetch in the background on every edit — exactly the behavior prompt §13 forbids. Staleness after the first calculation is tracked in the UI instead (`ScenarioWorkspacePage` compares `operationsQuery.dataUpdatedAt` against when results were last computed) and surfaced as a "recalculate" prompt, never a silent background refetch.

**Risk detection is limited to two objective, already-computed facts: over-allocation (`> 0`) and exactly-zero remaining capacity.** No invented "unmet project demand" risk (there's no required-hours concept on `Project` to compare against without inventing one) and no utilization-threshold risk duplicated on the backend — that judgment call (e.g. "90% counts as at-capacity") is presentation-only and already lives in the frontend (`features/capacity/constants/thresholds.ts::AT_CAPACITY_MIN`); duplicating it server-side would create two thresholds that could drift. `zero_remaining_capacity` fires only on exactly `0`, not `<= 0`, so it never co-reports with `over_allocation` for the same person (negative remaining capacity is definitionally an over-allocation).

**Project-scope resolution: any project an operation references pulls in every other allocation on that project.** `ScenarioCalculationService._collect_scope` was initially written to only load facts for people an operation directly names — this undercounted a project's baseline demand whenever a scenario added or adjusted one allocation on a project that already had other contributors (their existing hours were silently excluded from both the baseline and scenario demand totals). Fixed by resolving full project membership (`allocation_repository.list_for_project`) for every referenced project_id, once, after collecting direct references. Caught by `test_calculate_and_comparison_reflect_scenario_changes` in `tests/api/test_scenarios.py`.

**Impact's affected-teams/affected-dates are derived facts, not invented ones.** Affected teams come from `TeamMembershipRepository.list_for_people` (new, batched, additive method — same pattern as `AllocationRepository.list_for_people`) over the final affected-person set. Affected date range is the min/max across every allocation fact in baseline ∪ scenario state plus every operation's own date fields — not a separately-tracked "touched dates" ledger.

## Consequences

- No changes to Phase 1/2/3 behavior; the full existing test suite (146 tests before this phase) passes unchanged.
- `alembic check` will report the same kind of SQLite CHECK-constraint false positive for `ck_scenarios_status` and `ck_scenario_operations_operation_type` that ADR 0002 already documents for the Phase 1 enums — confirmed by observing it fire identically for the untouched Phase 1 constraints in the same run, not something this migration introduced.
- Scenario planning has no AI, no integrations, no auth, no skills/bottleneck logic — strictly scenario planning + what-if calculation + comparison, per the prompt's explicit phase boundary (§34).
- `adjust_allocation`/`remove_allocation`/`move_allocation` being baseline-only is a real, user-visible limitation (documented above and in `app/domain/scenario.py`'s module docstring) that a future iteration could lift by giving `ScenarioOperation` a notion of "depends on operation X."
