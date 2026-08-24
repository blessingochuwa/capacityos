# ADR 0016: Phase 16 instance-authorization completion

- **Status:** Accepted
- **Date:** 2026-08-24

## Context

Phase 11 introduced instance-level resource authorization for Team and
Project via explicit `TeamAccessGrant`/`ProjectAccessGrant` rows, and
deliberately left several things unscoped or unbuilt, each documented as a
deferral rather than an oversight: Team→Project inheritance, instance-level
scoping for Person-keyed resources (`WorkingSchedule`,
`AvailabilityException`, `PersonSkill`) and `Scenario`. Phase 12 (multi-
tenancy), Phase 13 (Risk), Phase 14 (Stakeholder), and Phase 15 (last-owner
invariant) each re-affirmed these same deferrals without closing them.
CLAUDE.md §39 asks that they "be picked up deliberately, not assumed" by a
future phase. Phase 16 is that phase.

## Audit findings (before any code changed)

Read in full: CLAUDE.md, `docs/architecture.md`, `docs/domain-concepts.md`,
ADRs 0010–0015. Audited every repository/service/route touching Team,
TeamMembership, Project, ProjectSkillRequirement, Risk, Stakeholder,
Allocation, WorkingSchedule, AvailabilityException, PersonSkill, Scenario,
`app/domain/authorization.py`, `app/api/deps.py`, `AccessGrantService`, the
frontend `AuthContext`/`features/access/`, and the entire `tests/` directory
for existing IDOR/multi-tenancy coverage per resource.

**Every route's actual authorization dependency was read directly** (not
inferred from documentation) to build the authorization matrix below.

| Resource | Read | Write/Delete | Scope mechanism |
|---|---|---|---|
| Team | role-only (`TEAM_READ`) | `require_team_access` | `TeamAccessGrant` |
| TeamMembership | role-only | `require_team_access` | `TeamAccessGrant` (via Team) |
| Project | role-only (`PROJECT_READ`) | `require_project_access` | `ProjectAccessGrant` |
| ProjectSkillRequirement | role-only | `require_project_access` | `ProjectAccessGrant` (via Project) |
| Risk | role-only | `require_project_access` | `ProjectAccessGrant` (via Project) |
| Stakeholder | role-only | `require_project_access` | `ProjectAccessGrant` (via Project) |
| Allocation | role-only | `require_permission` + inline `enforce_project_access` | `ProjectAccessGrant` (resolved from body on create, existing row on update/delete — `AllocationUpdate` has no `project_id` field, confirmed by reading the schema) |
| Person | role-only | role-only | none (deliberately, Phase 11) |
| WorkingSchedule | role-only | role-only | none (deliberately, Phase 11) |
| AvailabilityException | role-only | role-only | none (deliberately, Phase 11) |
| PersonSkill | role-only | role-only | none (deliberately, Phase 11) |
| Scenario | role-only | role-only | none (deliberately, Phase 11 — no Team/Project/Person FK exists) |

**Every one of the instance-scoped rows above was already correctly
implemented** — Risk and Stakeholder (Phases 13/14) both already used
`require_project_access`, and Allocation's inline enforcement (Phase 11)
already resolves scope from the existing row on update/delete, never a
client-suppliable `project_id`. Phase 16 found **zero mutation paths with
an actual authorization bug** in any of these.

**What Phase 16 did find: a real, sizable test-coverage gap.** Grepping
`tests/api/` for cross-organization/IDOR test patterns
(`another organization`, `org_b`, `organization_b`, `second_org`,
`invisible`) turned up exactly two hits: `test_risks.py` and
`test_stakeholders.py`. Every other organization-owned entity — Person,
Team, TeamMembership, Skill, PersonSkill, ProjectSkillRequirement,
WorkingSchedule, AvailabilityException, Allocation, Scenario — had **no
dedicated cross-organization regression test at all**, despite Phase 12
(ADR 0012) claiming to have hardened every one of them. Separately,
`test_risks.py` was missing the Manager-without-grant/with-grant/
grant-revoked instance-level test block its sibling `test_stakeholders.py`
already had, even though the underlying route code (`require_project_access`)
was identical. Both are closed in this phase — see Consequences.

## Decisions

### Team → Project inheritance: retained as independent axes, not built

CLAUDE.md defines no requirement that Team access imply Project access.
Phase 11's original rationale for independence — `Project` has no `team_id`
FK, and adding one purely to make authorization easier "would be a role-
ordering inversion... worth a much larger, more deliberate design than this
phase's scope" — remains fully valid; nothing in Phases 12–15 changed the
underlying domain model to make inheritance safe or well-defined (what would
"Team access implies Project access" even mean for a Project touched by
three different Teams' members via Allocations, with no single owning
Team?). Building it now would be inventing product semantics CLAUDE.md
never specified — exactly what §25 of this phase's own brief warns against.
**Decision: retained, not built.** Regression test:
`tests/api/test_cross_resource_escalation.py::test_team_grant_does_not_extend_to_project_mutation`.

### Person-scoped resources: retained as role-only, no `PersonAccessGrant`

The same reasoning Phase 11 gave for deferring this holds today, reinforced
rather than weakened by everything built since: `Person` has an inherently
*many-to-many* relationship to `Team` via `TeamMembership` (a person can be
on multiple teams, or none), and no relationship to `Project` at all except
indirectly through `Allocation` (also many-to-many, time-boxed). There is no
single, unambiguous "owning" Team or Project to key a `PersonAccessGrant`
on without inventing a derived-authorization chain — precisely the "don't
infer authorization from unrelated business relationships" warning both
Phase 11's original brief and this phase's brief repeat. No CLAUDE.md
section specifies who should be authorized to manage a Person's schedule,
availability, or skills beyond ordinary role-based access. **Decision:
retained, not built.** `WorkingSchedule`, `AvailabilityException`, and
`PersonSkill` remain governed by `Permission.SCHEDULE_*`/`SKILL_*` alone —
any Manager may mutate any Person's schedule/availability/skills within the
organization, unconditionally. Regression test:
`tests/api/test_cross_resource_escalation.py::test_project_grant_does_not_extend_to_an_unrelated_persons_skills`.

### Scenario: retained as role-only and organization-scoped only

`Scenario` has no `Team`/`Project`/`Person` foreign key in the schema at
all — it is a hypothetical planning exercise, not owned by any single
operational entity. `created_by` is free text (Phase 10, explicitly not a
`User` FK — "per the original prompt's instruction not to invent user
identities," per the model's own docstring) and this phase leaves it
exactly as-is, per the brief's explicit instruction not to convert it into
a real actor FK. Converting `created_by` into an ownership relationship
would be inventing a new authorization concept unsupported by any existing
specification. **Decision: retained, not built.** Any Manager may mutate
any Scenario in the organization. Regression test:
`tests/api/test_cross_resource_escalation.py::test_project_grant_does_not_extend_to_an_unrelated_scenario`.

### Allocation, ProjectSkillRequirement: re-audited, confirmed correct, no change

Allocation's create/update/delete handlers were re-read line by line.
`AllocationCreate.project_id` is validated via `enforce_project_access`
before the write; `AllocationUpdate` has no `project_id` field at all (an
allocation cannot be re-pointed to a different project as an authorization-
bypass vector), so update/delete resolve scope from the *existing* row,
fetched through the organization-scoped repository first. No gap found.
`ProjectSkillRequirement` already uses `require_project_access` on every
write route and already had full Manager-without-grant/with-grant test
coverage in `tests/api/test_project_access_scope.py`. No gap found, no
change made — only the missing cross-organization regression test was
added (see Consequences).

### Risk: test-coverage gap closed, no behavior change

`test_risks.py` never got the Manager-without-grant/with-grant/cross-
project/grant-revoked test block `test_stakeholders.py` already had, even
though both entities use identical `require_project_access` dependencies.
Added six tests mirroring `test_stakeholders.py`'s exactly (see
Consequences) — all pass unmodified against the existing route code,
confirming this was a coverage gap, not a behavior gap. Also added the
one test *neither* file had (`granted Project A still denied on Project
B`) to both, for full parity with the underlying Project/Team-level
precedent in `test_project_access_scope.py`/`test_team_access_scope.py`.

### Nested-resource authorization: audited, confirmed correct

Every nested route's parent-scope resolution was traced: `TeamMembership`
resolves through `Team` (`require_team_access`), `ProjectSkillRequirement`/
`Risk`/`Stakeholder`/`Allocation` all resolve through `Project`
(`require_project_access` or inline `enforce_project_access`), `PersonSkill`
resolves through `Person` (role-only, matching Person's own scope) — no
nested resource is ever authorized by its own id alone without first
resolving and checking its parent. `tests/api/test_cross_organization_boundaries.py`
adds the "authorized parent A + child belonging to B" regression case
(the brief's §10 requirement) for every nested resource type that lacked
it.

### Organization boundary: audited comprehensively, one real test gap closed

This was the phase's single largest finding. Every organization-owned
entity's repository methods were already required-`organization_id`
(Phase 12's blanket hardening, verified again here by direct code read),
but only Risk and Stakeholder had a dedicated regression test proving the
boundary holds for real requests. `tests/api/test_cross_organization_boundaries.py`
closes this for Person, Team, TeamMembership, Skill, PersonSkill,
ProjectSkillRequirement, WorkingSchedule, AvailabilityException, Allocation,
and Scenario — twelve tests, all passing against the existing,
**unmodified** production code. One genuinely new (and correct) fact
surfaced by writing these tests: `WorkingScheduleService.list_for_person`
resolves the `Person` through the organization-scoped repository *before*
listing, so filtering by another organization's `person_id` 404s (Person
not found) rather than silently returning an empty list — stricter than
the test's own first assumption, and left as-is (it is the more defensible
behavior: a 404 on a bad filter can never be mistaken for "this person
genuinely has zero schedules").

### Import/Export, Insights, AI: audited, confirmed correct, coverage added

ADR 0012 already named `ExportService`, `ImportService`, `InsightService`,
and `AIContextBuilder`/`AIService` as the four highest cross-tenant-leak-
risk areas and hardened all four. Phase 16 re-verified this by reading the
current code (`ExportService._collect_rows`'s optional `person_id`/
`team_id`/`project_id` filters are each resolved through an organization-
scoped repository `.get()` before being applied; `ImportService`'s identity
resolution — email, external_id — is `organization_id`-scoped at every
lookup; `InsightService`/`AIService` take `organization_id` as their first
parameter on every method, threaded from `get_current_membership`, never
client-supplied) and added one regression test per layer, all passing
unmodified: exporting Allocation filtered by another organization's real
`project_id` returns zero rows (not that project's data); importing an
Allocation CSV row referencing another organization's real person email +
project external_id is rejected as an unresolvable reference (not silently
attached to the wrong organization); requesting Insight signals or an AI
summary for a person that genuinely exists, but in another organization,
404s exactly like a nonexistent id. AI is safe *by construction* (it makes
zero independent repository queries, calling back only into
Capacity/Insight/Scenario/Skill services — ADR 0012), so the Insights-level
fix already covers it; the AI test exists to prove that construction
actually holds end-to-end, not just in the code's own claim.

### No new grant model, no new permission, no migration

Every decision above is "retained, not built" or "already correct, tested
more thoroughly." No `PersonAccessGrant` table, no `Scenario` ownership FK,
no `Project.team_id`, no new `Permission` enum member, and consequently no
Alembic migration. `alembic upgrade head` against a fresh database and
`alembic current` were re-verified to confirm this — head is unchanged from
Phase 14's revision (`c756ff8bebe5`); Phase 15 added none either.

### Concurrency

No new grant-creation/revocation surface was introduced (no new grant
table), so no new concurrency test was needed — the existing
`TeamAccessGrant`/`ProjectAccessGrant` concurrency suite
(`tests/api/test_access_grant_concurrency.py`, Phase 11) and the Last-Owner
concurrency suite (`tests/api/test_last_owner_concurrency.py`, Phase 15)
were re-run unmodified as regression and both pass.

### Frontend: no changes

No new grant type, no new authorization concept — `AuthContext`,
`canManageResource`, and the existing `features/access/` admin surface
already cover every instance-level grant this phase touches (Team/Project,
unchanged). Nothing to extend.

## Consequences

- 0 new tables, 0 migrations, 0 new `Permission` members, 0 behavior
  changes to any existing authorization decision.
- New test files: `tests/api/test_cross_organization_boundaries.py` (12
  tests), `tests/api/test_cross_resource_escalation.py` (3 tests). Extended:
  `tests/api/test_risks.py` (+6 tests, mirroring `test_stakeholders.py`),
  `tests/api/test_stakeholders.py` (+1 test, the missing cross-project-grant
  case), `tests/api/test_exports.py` (+1), `tests/api/test_imports.py` (+1),
  `tests/api/test_insights.py` (+1), `tests/api/test_ai.py` (+1). New
  factory: `tests/factories.py::make_scenario` (every other entity already
  had one; Scenario tests had only ever gone through the API until this
  phase needed a direct-DB cross-organization fixture).
- Backend: +26 tests — 769 total (up from 743 after Phase 15), all passing.
  `ruff check` and `uv run pyright` (strict) both fully clean.
- Frontend: unchanged — 0 files touched, existing suite unaffected.
- **Deliberate non-findings, stated explicitly rather than silently
  dropped**: Team→Project inheritance, `PersonAccessGrant`, and Scenario
  instance-scoping are now *closed* deferrals in the sense CLAUDE.md §39
  asked for ("picked up deliberately, not assumed") — the decision is to
  retain the Phase 11 design, not to leave the question open. A future
  phase should not re-open any of these three without a new, explicit
  product requirement naming the missing ownership concept CLAUDE.md
  itself would need to define first (see the per-decision sections above
  for exactly what's missing in each case).
- **Residual risk**: none newly introduced. The pre-existing, documented
  residual risks from ADRs 0011/0012/0015 (no Team→Project inheritance, no
  Person-level instance scoping, SQLite-only concurrency verification for
  the last-owner invariant) all remain exactly as previously stated — this
  phase re-confirmed rather than changed any of them.
