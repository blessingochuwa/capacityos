# CapacityOS — Claude Code Project Instructions

## 1. Product Mission

CapacityOS is an open-source-first resource and capacity planning platform for growing teams.

Its purpose is to help teams answer:

> Can we realistically take on this work with the people, time, skills, and capacity we currently have?

Primary users:
- Project managers
- Operations/resource managers
- Team leads
- Agency and creative teams
- Product and engineering teams
- Startup teams
- Founders

The product should scale conceptually from small teams to enterprise environments.

---

## 2. Product North Star

CapacityOS turns capacity planning from a spreadsheet exercise into a decision-support system.

Users should be able to understand:
- Who has capacity?
- Who is over-allocated?
- Who has remaining capacity?
- Where is work accumulating?
- Which projects are consuming capacity?
- Which skills are becoming bottlenecks?
- What happens if new work is accepted?
- How will a resource decision affect delivery?

Prioritize decision usefulness over dashboard decoration.

---

## 3. Operating Philosophy

CapacityOS should embody established project-management, operations-management, product-management, and systems-thinking principles.

### Core principles

**Flow over busyness**
Measure elapsed time, queues, work in progress, handoffs, and bottlenecks—not just activity.

**Capacity before commitment**
Do not treat new work as free. Evaluate people, time, skills, dependencies, and existing commitments before accepting or scheduling work.

**Pull over overload**
Avoid maximizing individual utilization at the expense of system throughput. Protect realistic capacity and limit work in progress.

**Clear ownership**
Every important allocation, decision, risk, dependency, and workflow should have an accountable owner.

**Stakeholder visibility**
Planning information should make assumptions, decisions, trade-offs, risks, and changes visible to the people affected.

**Value-based prioritization**
When demand exceeds capacity, prioritize using explicit value, strategic fit, urgency, cost, risk, dependency, and effort criteria rather than arbitrary sequencing.

**Progressive elaboration**
Do not pretend uncertain estimates are precise. Represent assumptions and uncertainty explicitly and refine estimates as information improves.

**Risk is continuous**
Identify, assess, respond to, monitor, and assign ownership to risks throughout planning—not only during project kickoff.

**Quality is built into the flow**
Do not optimize throughput by pushing defects, rework, or ambiguity downstream.

**Systems thinking**
Optimize the end-to-end system, not isolated individual utilization.

**Tailoring**
Small teams should not be forced through enterprise-grade process overhead. Controls should be proportional to risk, complexity, and organizational context.

**Change is expected**
Plans should be adaptable. Changes should be visible, traceable, and assessed for impact rather than silently mutating the plan.

These principles align with established PMI principles around value, stakeholders, systems thinking, quality, complexity, risk, adaptability, and tailoring, and with Lean concepts around flow, waiting, work in progress, and bottlenecks.

---

## 4. Deterministic Source of Truth

**All business-critical capacity calculations must be deterministic, independently testable, and explainable.**

This includes:
- Working hours
- Availability
- Realistic capacity
- Allocated hours
- Remaining capacity
- Utilization
- Over-allocation
- Under-utilization
- Leave
- Holidays
- Working schedules
- Date calculations
- Scenario calculations
- Skill capacity
- Bottleneck detection

AI must never be the source of truth for numerical capacity calculations.

AI may explain, summarize, recommend, or help users explore deterministic application data.

If AI output conflicts with deterministic application data, deterministic data wins.

---

## 5. Architecture

CapacityOS is a monorepo.

Initial target:

```text
capacityos/
├── CLAUDE.md
├── README.md
├── CONTRIBUTING.md
├── SECURITY.md
├── LICENSE
├── .env.example
├── .gitignore
│
├── .github/
│
├── apps/
│   ├── web/
│   └── api/
│
├── packages/
│   └── contracts/
│
├── scripts/
├── data/
├── docs/
└── tests/
```

Do not create future directories merely for completeness. Add structure when functionality requires it.

---

## 6. Application Boundaries

### `apps/web`

React + TypeScript + Vite frontend.

Responsible for:
- UI
- Routing
- User interaction
- Presentation
- Client-side state
- API consumption

Complex business calculations do not belong in React components.

Prefer feature-oriented organization:

```text
src/
├── app/
├── components/
├── features/
├── hooks/
├── lib/
├── api/
├── types/
└── styles/
```

### `apps/api`

Python + FastAPI backend.

Responsible for:
- HTTP/API routing
- Validation
- Serialization
- Dependency injection
- Authentication when introduced
- Orchestration

API routes should remain thin. Complex business logic belongs in domain/services layers.

Preferred conceptual structure:

```text
app/
├── main.py
├── api/
├── core/
├── domain/
├── services/
├── repositories/
├── models/
├── schemas/
└── integrations/
```

### `packages/contracts`

Shared contracts only where genuinely useful across applications.

Do not duplicate business logic here.

### `scripts`

Deterministic operational utilities such as:
- Seed generation
- Imports/exports
- Maintenance
- Development utilities

Reusable business logic must not exist only inside scripts.

### `data`

Development-only:
- Seed data
- Fixtures
- Samples

Never include private, confidential, client, employee, or production data.

### `docs`

Architecture, domain concepts, API documentation, product decisions, integrations, and significant architectural decisions.

### `tests`

Cross-application and end-to-end tests. Application-specific unit tests may remain near the code they test.

---

## 7. Technology Direction

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- Recharts or another mature open-source charting library when justified

Use strict TypeScript. Avoid `any`.

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- pytest
- Ruff
- Appropriate static/type checking

### Database
Development may begin with SQLite.

Production architecture must remain PostgreSQL-compatible.

Do not introduce SQLite-specific assumptions into domain logic.

### Testing
Use mature open-source tooling appropriate to the stack.

Frontend: TypeScript, linting, unit/component tests as appropriate.

Backend: pytest, linting, type checking.

End-to-end: Playwright or another mature open-source option when needed.

---

## 8. Domain Model

CapacityOS distinguishes between:

### Contractual Hours
The theoretical hours a person is contracted to work.

### Available Hours
Contractual hours minus known unavailable time.

### Realistic Capacity
Available hours minus recurring non-project work required to operate effectively.

Example:

```text
40h contractual
- 5h meetings
- 3h administration
- 2h internal work
- 4h leave
= 26h realistic project capacity
```

### Allocated Hours
Work currently assigned to a person.

### Remaining Capacity
Realistic capacity minus allocated work.

### Utilization
Allocated work divided by the explicitly defined capacity denominator.

The denominator must be visible and consistent.

Do not silently change the definition of utilization.

---

## 9. Initial Entities

Initial domain entities:
- Person
- Team
- Project
- Allocation
- Availability
- WorkingSchedule

Potential later entities:
- Organization
- Skill
- PersonSkill
- Leave
- Holiday
- CapacityPlan
- Scenario
- ScenarioChange
- WorkItem
- Integration
- AuditEvent

Do not implement future entities until required.

---

## 10. Capacity Engine

The capacity engine is the core of CapacityOS.

Business logic should be expressed through small, deterministic, testable functions.

Potential operations:

```text
calculate_contractual_hours()
calculate_available_hours()
calculate_realistic_capacity()
calculate_allocated_hours()
calculate_remaining_capacity()
calculate_utilisation()
detect_overallocation()
detect_underutilisation()
calculate_skill_capacity()
detect_skill_bottlenecks()
```

Avoid hidden global state.

Avoid UI dependencies.

Avoid database dependencies inside pure calculation functions where possible.

---

## 11. Capacity and Resource Management Principles

Capacity planning must account for more than headcount.

Consider:
- Time
- Working schedules
- Availability
- Existing allocations
- Non-project work
- Skills
- Dependencies
- Project priorities
- Leave
- Holidays
- Time zones
- Part-time schedules
- Cross-project commitments

Do not assume that a person with free hours is automatically suitable for the work.

A person may have capacity but lack the required skill.

A team may have spare aggregate capacity while a specific skill is constrained.

---

## 12. Flow and Operations Principles

The system should help users distinguish:
- Work time vs lead time
- Active work vs waiting
- Capacity vs utilization
- Individual efficiency vs system throughput
- Activity vs progress
- Demand vs available capacity
- Work in progress vs completed work
- Handoffs vs ownership
- Planned work vs unplanned work
- Output vs outcome

Where relevant, use concepts such as:
- Waiting waste
- Queues
- Work in progress
- Bottlenecks
- Flow efficiency
- Little's Law
- Rework
- Handoff friction
- Decision latency

Do not turn these concepts into decorative terminology. Use them only when they improve diagnosis or decision-making.

---

## 13. Resource Allocation

A person may work across multiple projects.

Allocations should eventually support:
- Person
- Project
- Start date
- End date
- Estimated hours
- Percentage where appropriate
- Priority
- Skill
- Notes

The system must aggregate allocations correctly across projects and time periods.

Avoid optimizing every person to 100% utilization.

Sustainable capacity should leave room for:
- Meetings
- Support
- Planning
- Unplanned work
- Context switching
- Learning
- Recovery
- Operational overhead

---

## 14. Skills and Bottlenecks

CapacityOS should eventually reason about capacity by skill, not only by person or department.

Example:

A team may have 10 designers but only 2 motion designers.

If upcoming motion-design demand exceeds those two people's capacity, motion design is the bottleneck even if the broader design team has spare hours.

Do not implement advanced skill planning before the basic capacity engine is reliable.

---

## 15. Project Management Principles

The product should support disciplined project execution without forcing unnecessary process.

Important concepts include:
- Scope
- Schedule
- Resources
- Dependencies
- Stakeholders
- Risks
- Issues
- Assumptions
- Constraints
- Milestones
- Deliverables
- Decisions
- Change
- Quality
- Benefits/value

When a project changes, consider:
- What changed?
- Why?
- Who owns it?
- What capacity is affected?
- What dependencies move?
- What risks change?
- What other work must move?
- What decision is required?

Do not allow silent changes to materially affect planning data.

---

## 16. Stakeholder Management

Stakeholders should be treated as part of the operating system, not merely as contacts.

Where appropriate, capture:
- Stakeholder
- Role
- Influence
- Interest
- Decision authority
- Communication needs
- Relevant project/work context

Important decisions should have clear ownership.

Avoid creating administrative overhead for information that does not affect decisions.

---

## 17. Risk Management

Risk management should be continuous.

A risk should be understandable through:
- Description
- Cause
- Potential effect
- Probability
- Impact
- Exposure
- Response
- Owner
- Status
- Review date

Responses should be proportional to the significance of the risk.

Do not create risk scores that imply false precision.

Where useful, distinguish:
- Risk
- Issue
- Assumption
- Dependency
- Constraint

---

## 18. Prioritization and Product Management

When demand exceeds capacity, the system should support explicit prioritization.

Useful dimensions may include:
- Strategic alignment
- Customer/user value
- Business value
- Urgency
- Cost/effort
- Risk
- Dependencies
- Opportunity cost
- Confidence

Do not prescribe one prioritization framework as universally correct.

Frameworks such as RICE, WSJF, MoSCoW, weighted scoring, or cost-of-delay may be supported later where appropriate.

The system should preserve the rationale behind a decision where possible.

Prioritization should connect strategy to execution rather than simply producing a ranked list.

---

## 19. Scenario Planning

Scenarios are hypothetical planning exercises.

A scenario must not mutate live planning data.

Example:

```text
Add Project X

Designer: 20h
Copywriter: 10h
Strategist: 15h
```

Calculate hypothetical impact on:
- Utilization
- Remaining capacity
- Over-allocation
- Skills
- Projects
- Delivery risk

Applying a scenario to live data must be explicit.

---

## 20. Estimation and Uncertainty

Estimates are assumptions, not facts.

Where practical, preserve:
- Estimate
- Unit
- Source
- Confidence
- Assumptions
- Date created
- Last updated

Do not imply precision beyond the available information.

As actuals become available, the system should eventually support comparison between:
- Planned
- Forecast
- Actual

Do not introduce actuals until the planning model is stable.

---

## 21. AI Boundaries

AI is an interpretation layer, not the calculation engine.

Potential AI capabilities:
- Capacity summaries
- Risk explanations
- Natural-language queries
- Planning suggestions
- Trend explanations
- Report generation
- Scenario explanations

AI must operate only on available application data.

AI must not invent:
- People
- Hours
- Allocations
- Availability
- Deadlines
- Skills
- Project information

If data is insufficient, state that explicitly.

Keep AI integrations provider-agnostic where practical.

---

## 22. Integration Architecture

External services must be isolated behind adapters.

Potential future integrations:
- Slack
- Jira
- Linear
- Asana
- ClickUp
- Google Calendar

Preferred pattern:

```text
External System
      ↓
Integration Adapter
      ↓
CapacityOS Internal Model
      ↓
Domain Engine
```

Vendor-specific logic must not spread throughout the domain layer.

Do not implement external integrations in the MVP unless explicitly requested.

---

## 23. Chrome Extension

A Chrome extension is a future application.

Do not duplicate CapacityOS business logic inside it.

Future architecture:

```text
Chrome Extension
      ↓
CapacityOS API
      ↓
Domain Engine
      ↓
Database
```

Use Manifest V3 when eventually implemented.

Use least-privilege permissions.

Do not implement the extension during the initial MVP.

---

## 24. Database and Persistence

Use migrations.

Separate persistence from business logic.

Repositories handle persistence.

Services coordinate operations.

Domain functions contain business rules.

Do not put complex business logic inside API route handlers or database models.

---

## 25. Demo Data

CapacityOS should eventually include realistic fictional seed data covering:
- Healthy capacity
- Near-capacity resources
- Overloaded resources
- Under-utilized resources
- Multiple projects
- Multiple teams
- Multiple skills
- Leave
- Holidays
- Different schedules
- Cross-project allocations

Seed generation must be reproducible.

Do not use uncontrolled randomness.

---

## 26. No Fake Functionality

Never present mocked functionality as production functionality.

Do not create:
- Fake API calls presented as real
- Hardcoded dashboard values presented as live data
- Fake AI responses presented as generated insights
- Random capacity values
- Buttons that appear functional but do nothing
- Fake integrations

If functionality is intentionally mocked, label it clearly:
- DEMO DATA
- MOCK
- NOT CONNECTED
- DEVELOPMENT ONLY

---

## 27. Security

Never:
- Commit secrets
- Hardcode tokens/API keys/credentials
- Expose backend secrets to the frontend
- Log access tokens
- Execute arbitrary uploaded code
- Expose production stack traces
- Let a user read, modify, export, infer, or otherwise interact with data belonging to an organization they are not an active member of (Phase 12 — see [docs/adr/0012-organizations-multi-tenancy.md](./docs/adr/0012-organizations-multi-tenancy.md)). A resource in another organization must respond identically to a nonexistent one (404), never 403 — confirming it exists elsewhere is itself a leak. This applies uniformly across reads, writes, imports, exports, scenarios, skills, insights, AI requests, and audit queries, not only the obviously "sensitive" ones.

Use environment variables.

Maintain `.env.example`.

Keep `.env` out of version control.

Use least privilege for integrations and browser permissions.

Security-sensitive changes require additional review.

---

## 28. API

Use versioned APIs:

```text
/api/v1/people
/api/v1/projects
/api/v1/capacity
/api/v1/allocations
```

API contracts should use explicit schemas.

API routes should orchestrate rather than contain domain logic.

API errors should be consistent and useful.

Do not expose internal stack traces.

---

## 29. Frontend UX

CapacityOS is a serious B2B operations product.

The interface should be:
- Clean
- Professional
- Calm
- Readable
- Data-dense without being overwhelming
- Accessible
- Purposeful

Avoid unnecessary:
- Animations
- Gradients
- Decorative charts
- Visual noise
- Generic dashboard patterns

Every major visualization should answer a meaningful planning question.

Provide appropriate:
- Loading states
- Empty states
- Error states
- Success states

Never rely on colour alone to communicate state.

Target WCAG 2.2 AA where practical.

---

## 30. Testing

Business-critical domain logic requires strong test coverage.

Test at minimum:
- Full-time workers
- Part-time workers
- Custom schedules
- Leave
- Holidays
- Multiple projects
- Zero capacity
- Over-allocation
- Under-utilization
- Allocation overlaps
- Date boundaries
- Timezone boundaries
- Cross-project allocations
- Skill bottlenecks

Test edge cases, not only happy paths.

A feature is not complete because the UI renders.

---

## 31. Development Workflow

For meaningful features:

1. Inspect the existing repository.
2. Identify the relevant architecture.
3. Form a short implementation plan.
4. Identify assumptions and risks.
5. Implement the smallest complete slice.
6. Add or update tests.
7. Run relevant checks.
8. Review the result.
9. Update documentation when necessary.
10. Report what changed and what remains.

Do not rebuild existing functionality unnecessarily.

Do not modify unrelated files.

For complex or ambiguous work, use a planning-first approach and confirm major architectural changes before implementation.

---

## 32. Scope Discipline

Do not implement future-phase functionality unless explicitly requested.

Deferred capabilities include:
- Slack integration
- Jira integration
- Linear integration
- Calendar integrations
- AI provider integration
- Authentication
- RBAC
- Multi-tenancy
- Chrome extension

The architecture may anticipate these capabilities.

The implementation should remain within the current phase.

---

## 33. Approval Gates

Ask before:
- Destructive database operations
- Deleting important files
- Changing Git history
- Force pushing
- Adding major dependencies
- Changing deployment architecture
- Introducing external services
- Adding secrets
- Connecting third-party integrations
- Adding sensitive browser permissions
- Making major architectural changes

Never bypass safety controls merely to accelerate development.

---

## 34. Dependency Discipline

Before adding a significant dependency, evaluate:
- Necessity
- Maintenance
- License
- Security
- Compatibility
- Bundle/runtime impact
- Vendor lock-in
- Whether the functionality can reasonably be implemented without it

Prefer mature open-source dependencies.

Do not add a dependency simply because it is popular.

---

## 35. Documentation

Keep current:
- README.md
- CONTRIBUTING.md
- SECURITY.md
- Architecture documentation
- Domain documentation
- API documentation
- Meaningful architectural decisions

Use Architecture Decision Records for significant long-term decisions.

Do not document trivial implementation details.

---

## 36. Source of Truth

When information conflicts, use this order:

1. Executable code and tests
2. Database schema and migrations
3. API contracts
4. Architecture Decision Records
5. CLAUDE.md
6. General assumptions

If documentation conflicts with implementation:
- Identify the discrepancy
- Verify intended behavior
- Update the appropriate source
- Do not silently guess

---

## 37. Research Standards

When external research is necessary, prefer:
- Official documentation
- Official GitHub repositories
- Official API documentation
- Standards
- Maintained open-source projects
- Established professional bodies

Use community sources such as GitHub discussions and Reddit for practical experience, not authoritative technical specifications.

Verify current APIs and compatibility before implementing third-party libraries.

For product/operations concepts, prefer established frameworks and distinguish established practice from opinion.

---

## 38. Product Decision Principle

Every major screen should help answer a decision question.

Dashboard:
> Where is capacity at risk?

Person:
> Can I give this person more work?

Project:
> Do we have enough capacity to deliver this?

Scenario:
> What happens if we accept this work?

Bottleneck:
> What capability is constraining delivery?

If a feature does not help users understand, plan, decide, or act on capacity, question whether it belongs.

---

## 39. Development Priority

Build in this order unless explicitly changed:

### Phase 0
Repository and architecture bootstrap.

### Phase 1
People, teams, projects, availability, and allocations.

### Phase 2
Deterministic capacity engine.

### Phase 3
Core dashboard and planning views.

### Phase 4
Scenario planning.

### Phase 5
Operational insights — deterministic, explainable decision-support signals
(over-allocation, capacity risk, concentration, imbalance, project pressure,
scenario deltas) surfaced from the existing capacity and scenario engines.
No AI, no integrations, no new capacity formulas. See
docs/adr/0005-phase-5-operational-insights.md.

### Phase 6
Import/export.

### Phase 7
Skills and bottleneck analysis.

### Phase 8
AI insight layer.

### Phase 9+
External integrations, authentication, RBAC, multi-tenancy, and Chrome extension.

**Amendment (2026-08-14):** Operational Insights was originally scoped as a
later phase but is being pulled forward and renumbered as Phase 5, pushing
Import/Export and Skills/Bottleneck analysis to Phase 6/7 respectively (AI
insight layer becomes Phase 8). Rationale: insights sit directly on top of
the Phase 2 capacity engine and Phase 4 scenario engine with no new
subsystem dependencies, while import/export and skills/bottleneck each
introduce their own new domain concepts. See
docs/adr/0005-phase-5-operational-insights.md.

**Amendment (2026-08-20):** The "Phase 9+" line above was never broken out
into individually numbered phases as it was actually built, and this list
was never updated to record what happened. For the record: Phase 9 became
production readiness/observability (docs/adr/0009), Phase 10 became
authentication/RBAC/audit (docs/adr/0010), Phase 11 became instance-level
resource authorization (docs/adr/0011), and Phase 12 became organizations
and multi-tenancy (docs/adr/0012) — four phases where this section implied
one. This gap caused a genuine ambiguity at the start of Phase 13 (no
document anywhere named what "Phase 13" was supposed to be); it was
resolved by asking the user, who chose Risk Management (§17) from three
audited candidates. That choice, and the audit behind it, is recorded in
docs/adr/0013-phase-13-risk-management.md.

### Phase 13
Risk management (§17) — a project-scoped risk register (description,
cause, potential effect, probability, impact, response, owner, status,
review date) on top of the existing organization-scoped, RBAC-protected,
audited foundation. No new capacity formula, no second signal system
(exposure and two new signal types plug into the existing Phase 5/7
Insights pipeline), no risk score implying false precision. See
docs/adr/0013-phase-13-risk-management.md.

### Phase 14
Stakeholder management (§16) — a project-scoped stakeholder register
(name, optional link to an existing Person, role, influence, interest,
decision authority, communication needs) on the same organization-scoped,
RBAC-protected, Phase-11-instance-scoped, audited foundation Risk (Phase
13) already established — CRUD nested under `/projects/{id}/stakeholders`,
identical authorization shape to `ProjectSkillRequirement`/`Risk`. No
numeric score, health score, or engagement-quadrant classification is
computed anywhere — influence/interest/decision authority are stored
3-tier/3-level enums, never combined into a derived value. Deliberately
**not** integrated into Insights (§16 defines no deterministic signal —
no threshold, no fact to classify — so none was invented) and deliberately
**not** registered into Import/Export (not specified; deferred, matching
Phase 13's own precedent for a new entity that wasn't explicitly asked
for). See docs/adr/0014-phase-14-stakeholder-management.md.

### Phase 15
Last-owner invariant (§27's spirit — an organization must never be left
without an active Owner) — closes the Phase 12 gap ADR 0012 deferred, now
resolved: every active Organization retains at least one Owner whose
membership AND whose linked User account are both active (a disabled
account cannot authenticate, so an Owner membership pointing at one cannot
exercise Owner authority — see docs/adr/0015-last-owner-invariant.md for
why this settles the "active Owner" definition this way). Three mutation
paths guarded — Owner role change, Owner membership revocation, Owner
account deactivation — each via an atomically guarded UPDATE (the
invariant folded into the write's own WHERE clause, not a separate
read-then-decide-then-write) closing a genuine concurrent-request race,
verified against a real file-backed SQLite database. No schema change, no
new permission, no frontend change (no membership- or user-management UI
exists yet to guard — building one was explicitly out of this phase's
scope). See docs/adr/0015-last-owner-invariant.md.

### Phase 16
Instance-authorization completion — closes the Phase 11 "which resources
are deliberately deferred" question ADR 0011/CLAUDE.md §39 carried forward
across Phases 12-15, now resolved: audited every remaining gap (Team→
Project inheritance, instance-level scoping for Person-keyed resources —
WorkingSchedule, AvailabilityException, PersonSkill — and Scenario) against
the current codebase and every existing specification, and **retained**
each as role-only by deliberate decision, not oversight — no
PersonAccessGrant, no Project.team_id, no Scenario ownership FK, since none
is required by CLAUDE.md or any ADR and inventing one would be exactly the
unrequested product semantics §25 of this phase's own brief (and this
document's general philosophy) warns against. What the audit actually
found and closed was a test-coverage gap, not an authorization bug: only
Risk and Stakeholder (Phases 13/14) had a dedicated cross-organization
regression test; every other organization-owned entity (Person, Team,
TeamMembership, Skill, PersonSkill, ProjectSkillRequirement,
WorkingSchedule, AvailabilityException, Allocation, Scenario) did not,
despite Phase 12 already enforcing the boundary in the repository layer.
Closed with 26 new tests, all passing against unmodified production code;
Import/Export, Insights, and AI-context boundaries were independently
re-verified with one regression test each. 0 new tables, 0 migrations, 0
new permissions, 0 behavior changes. See
docs/adr/0016-instance-authorization-completion.md.

### Phase 17 (v1 slice)
Prioritization engine (§18) — "given limited people, time, and capacity,
what should this organization work on first?", answered by an
organization-chosen framework, never one CapacityOS prescribes (§18: "do
not prescribe one prioritization framework as universally correct"). The
first phase that is a new product module rather than an extension of
existing infrastructure — a PRD (docs/PRD-phase-17-prioritization.md) was
written and confirmed with the user before any code was written, per
CLAUDE.md §31's planning-first instruction for complex/ambiguous work.
Two decisions were confirmed before implementation: build a reduced v1
slice first (RICE + Weighted Scoring only, no dependency graph, no
scenario comparison, no AI yet), and use the PRD's own recommended
defaults for the remaining open questions (normalized criterion-value
storage, RICE/WSJF criteria non-editable, framework management Admin/
Owner only). A score is always derived at read time from recorded
criterion inputs plus the framework's current definition, never stored
or cached — the same discipline Risk.exposure and every Scenario result
already follow. 4 new tables, 3 new permissions
(PRIORITIZATION_READ/SCORE/MANAGE — framework management is deliberately
Admin/Owner only, scoring is Manager+ via the existing Phase 11
ProjectAccessGrant mechanism), 0 changes to any existing table or
permission. See docs/adr/0017-prioritization-engine.md.

### Phase 18
Prioritization frameworks & dependencies (§18, completing the "Phase 17b"
remainder named in docs/roadmap.md) — a further-reduced slice proposed in
plain text (not a second blocking question) after the user confirmed the
macro-scope "rest of Prioritization," per CLAUDE.md §31's "smallest
complete slice" principle applied a second time to this same feature area.
Built: ICE and WSJF formulas (both dispatch through the same
`FIXED_CRITERION_KEYS`-driven engine RICE already proved, generalized
rather than duplicated); MoSCoW, deliberately categorical and never
numeric (§17: "do not create scores that imply false precision" — a
project's `category` is a stored `MoscowCategory` enum, never coerced onto
an invented scale); editing a Weighted Scoring framework's criteria after
creation (add/rename/reweight/remove, each independently re-checking
`is_editable` server-side — RICE/ICE/WSJF/MoSCoW's criteria remain
unreachable through these routes regardless of what the UI shows);
`ProjectDependency` (blocks/related/enables) with cycle detection scoped
to `blocks` edges only, and a Dependency Graph frontend view (a table, not
a new charting dependency — §29 forbids decorative charts and none was
added). 1 new table, 1 new column on an existing table, 0 new permissions
(criterion edits reuse PRIORITIZATION_MANAGE; dependency create/delete
reuse PRIORITIZATION_SCORE via the existing Phase 11 ProjectAccessGrant
mechanism), 0 changes to any existing permission's grant set. See
docs/adr/0018-prioritization-frameworks-and-dependencies.md.

### Phase 19
AI priority explanation — of the six items docs/roadmap.md's "Proposed
next" section named as the still-open remainder of the Phase 17 PRD
(PortfolioSnapshot, scenario-vs-baseline ranking comparison, AI priority
explanation, the Priority Explanation Panel and Scenario Comparison
frontend views, and five Recharts visualizations), only this one was
built — chosen after an explicit repository audit because it is a
same-shape fifth capability on the existing Phase 8 AI pipeline
(`summarize`/`explain-signal`/`explain-scenario`/`ask` already establish
the pattern `explain_priority` follows exactly), requires no new
persistence concept, and resolves no ambiguous domain-model question.
Scenario-vs-baseline comparison was specifically audited and found to
require a genuine product decision first — Scenario operations
(ADD_ALLOCATION, etc.) never touch a project's prioritization criterion
values today, so "how does accepting this scenario change portfolio
priority" has no defined computation — and was deliberately left
unbuilt rather than guessed at. `AIContextBuilder.build_for_priority_score`
calls `ProjectPriorityScoreService.get` verbatim — no number is
recalculated, every fact handed to the model was already produced by the
Phase 17/18 deterministic engine. 0 new tables, 0 migrations, 0 new
permissions (`Permission.AI_USE`, already granted to every role, is the
only gate) — reuses the existing organization-scoped
`ProjectPriorityScoreService.get` for tenancy, exactly like every other
prioritization route. See docs/adr/0019-ai-priority-explanation.md.

### Phase 20
Scenario-vs-baseline prioritization comparison (§18/§19) — the one item
Phase 19 explicitly flagged as requiring a genuine product decision before
implementation, since no ScenarioOperationType can touch a project's
prioritization criterion values and no criterion is derived from
allocation/capacity data anywhere in the codebase. Per the phase brief's
explicit instruction, the repository was audited first and the resulting
options were put to the user via a blocking question rather than guessed;
the user chose **explicit, scenario-scoped criterion overrides** — a
Scenario can declare "in this hypothetical, Project X's Effort is 6
instead of 4" (or a different MoSCoW category), a human-declared value
never auto-derived from capacity data. Built as a new, standalone
`ScenarioPriorityOverride` table (deliberately not a ninth
ScenarioOperationType — it has no ordering/replay semantics and never
touches capacity, so extending PlanningState would have been the wrong
shape) that is read alongside the real, persisted ProjectPriorityScore at
comparison time and never written back to it — baseline and scenario
results are both computed through the exact same
ProjectPriorityScoreService.compute_result/calculate_priority_score path
Phases 17/18 already built (RICE/ICE/WSJF/Weighted/MoSCoW all covered),
never a second scoring engine. Ranking itself was extracted to one shared
pure function (`rank_priority_results`) so the live portfolio board and
this comparison can never disagree about a project's rank. Gated entirely
by the existing SCENARIO_READ/WRITE/DELETE permissions (role-only, no
ProjectAccessGrant) — a deliberate choice, since the action being
authorized is "editing a hypothetical scenario," not "editing a real
score." 1 new table, 0 new permissions, 0 changes to any existing
permission's grant set. No AI in this phase — establishing the
deterministic comparison was the whole scope; an AI explanation of it is
left for a future phase to consider deliberately. See
docs/adr/0020-scenario-priority-comparison.md.

### Phase 21
Portfolio snapshots (§18/§38) — the other item Phases 19-20 named as
requiring a genuine audit-first decision before implementation, unlike
Phase 20's flagged item this one required no new product decision: the
original Phase 17 PRD's own §8 had already specified `PortfolioSnapshot`
precisely ("an explicit, user-triggered 'save today's computed
ranking' record... stored as a genuine historical record (like
`AuditEvent`), never read back as an input to a live computation").
Per the phase brief's audit-first instruction, the repository was
audited against every remaining named Phase 17-20 remainder — Portfolio
Snapshots, an AI explanation of the Phase 20 comparison, and the five
Recharts visualizations — and the resulting candidates put to the user
as a blocking product decision rather than guessed; Portfolio Snapshots
was chosen as the most self-contained slice, depending on nothing
unfinished. `PortfolioSnapshotService.create` calls
`ProjectPriorityScoreService.rank_portfolio` verbatim — never a second
ranking computation — then freezes every value a later read would need
(`framework_name`, `framework_type`, and each entry's `project_name`/
`score`/`rank`/`missing_criteria`/`breakdown`/`category`) directly into
the row, so a later project rename, re-score, deletion, or framework
rename can never retroactively change an already-taken snapshot —
verified live against a real file-backed SQLite database. No PATCH/
DELETE route — immutable and append-only, matching `AuditEvent`'s own
shape. Creating one is gated by the existing `Permission.
PRIORITIZATION_MANAGE` (Admin/Owner, reused unchanged) rather than the
project-instance-scoped `PRIORITIZATION_SCORE`, since a snapshot spans
every project scored under a framework at once, not a single project a
Manager might hold a grant on. 1 new table, 1 migration, 0 new
permissions. See docs/adr/0021-portfolio-snapshots.md.

### Phase 22
Portfolio snapshot diff/trend (§18/§38) — the item Phase 21 itself named
as the still-open remainder. Per the phase brief's audit-first
instruction, the repository was audited against every remaining named
candidate — snapshot diff/trend, scenario snapshots, an AI explanation of
the Phase 20 comparison, the five Recharts visualizations,
Risk/Stakeholder import/export, and a membership/user-management UI
(this audit newly inspected the organization/membership API and the
Phase 6 import/export code, neither examined in depth by any prior
phase's audit) — and two candidates (scenario snapshots;
Risk/Stakeholder import/export) were found to each carry a genuine open
sub-question needing its own decision before being buildable, not
selectable as-is. The resulting candidates were put to the user as a
blocking product decision; snapshot diff/trend was chosen as the only
one with no open sub-question, building directly on the now-stable Phase
21 foundation. `app/domain/portfolio_snapshot.py::compare_snapshot_entries`
is pure and DB-free, diffing two already-frozen `PortfolioSnapshot.entries`
payloads — never imports the scoring engine, since a snapshot's entries
are historical facts already computed once at capture time. Four
statuses (entered/left/changed/unchanged), tuple-compared
(rank, score, category) so a project whose rank moved only because a new
project entered the ranking is correctly `changed`, not `unchanged`.
Comparing snapshots from different frameworks is rejected (422) — a
RICE score and a WSJF score aren't comparable numbers. Never persisted —
computed fresh on every read, verified live to leave both compared
snapshots byte-identical afterward. Gated by the existing
`Permission.PRIORITIZATION_READ` (every role, reused unchanged) — no new
permission, no audit event (matches every other read in this router). 0
new tables, 0 migrations, 0 new permissions. See
docs/adr/0022-portfolio-snapshot-comparison.md.

### Phase 23
AI snapshot comparison explanation (§18/§21) — the item Phase 22 itself
named as its own still-open remainder, and this phase's brief confirmed
directly rather than re-deriving from a candidate list: an AI capability
explaining an already-computed Phase 22 snapshot comparison in plain
language, never calculating, ranking, scoring, or reinterpreting the
comparison itself. A sixth capability on the unchanged Phase 8 pipeline
(`AIContextBuilder`/`AIService`/grounding/`AiTriggerButton`), alongside
`summarize`/`explain-signal`/`explain-scenario`/`explain-priority`.
`AIContextBuilder.build_for_snapshot_comparison` calls
`PortfolioSnapshotService.compare` verbatim — no status
(entered/left/changed/unchanged), rank, score, or category is ever
recomputed by the AI layer; framework-mismatch (422) and
cross-organization/unknown-snapshot (404) behavior is inherited from
that unchanged Phase 22 service call, not re-implemented. A new
`snapshot_comparison` grounding reference type adds one
(type, project_id) pair per comparison item, the same "one reference per
collection member" shape `signal`/`skill_coverage` already established.
`POST /api/v1/ai/explain-snapshot-comparison`, gated by the existing
`Permission.AI_USE` only (every role) — no new permission, no CSRF
requirement (matching every other AI route, none of which mutate data).
0 new tables, 0 migrations, 0 new permissions. See
docs/adr/0023-ai-snapshot-comparison-explanation.md.

### Phase 24
Multi-snapshot portfolio trend visualization (§18/§38) — the "multi-
snapshot trend chart beyond a two-point diff" named across ADRs 0021-0023
as deferred but never actually specified anywhere, including the original
Phase 17 PRD (whose §15 names five different Recharts visualizations —
Priority-vs-Effort scatter, Capacity-vs-Priority matrix, Risk-vs-Value
quadrant, WSJF breakdown, dependency timeline — none of them this chart).
Per the phase brief's audit-first instruction, the repository was audited
and found one genuine open product decision — what the Y-axis plots,
since `app/domain/prioritization.py::calculate_moscow_result`/
`rank_priority_results` confirm a MoSCoW score and rank are each always
null, making "score over time," "rank over time," and "both" three
materially different features, not a styling choice — and a rank trend
specifically risks conflating a project's own change with a sibling
project entering/leaving the ranking (a confound ADR 0022 already flagged
for the two-point diff). This was presented to the user as a blocking
question with three concrete options before any code was written; the
user chose **score over time**. Built as a frontend-only feature with
**zero backend changes** — `GET /api/v1/prioritization/snapshots` (Phase
21, unchanged) already returns every selected snapshot's frozen `entries`
with `score`, sufficient to build a per-project time series with no new
endpoint, matching the phase brief's own "extend the API only if it
cannot already provide the data" instruction.
`app/domain/portfolio_snapshot.py` was not touched; the new
`features/prioritization/utils/snapshotTrend.ts::buildSnapshotTrend` is a
pure, unit-tested frontend function mirroring `compare_snapshot_entries`'s
own discipline (never recomputes a score, never fabricates a value for a
project absent from a snapshot — represented as a gap, not interpolated;
deduplicates a repeated snapshot selection; never mutates its input).
`PortfolioSnapshotTrendChart` pairs the Recharts line chart with an
accessible data table, matching `ProjectDemandTimeline`'s existing
precedent — colour is never the only signal. 0 new tables, 0 migrations,
0 new permissions, 0 backend files changed. See
docs/adr/0024-portfolio-snapshot-trend.md.

### Phase 25
WSJF breakdown visualization (§18/§38) — one of the five Recharts
visualizations the Phase 17 PRD's own §15 actually names (Priority-vs-
Effort scatter, Capacity-vs-Priority matrix, Risk-vs-Value quadrant, WSJF
breakdown, dependency timeline). Per the phase brief's audit-first
instruction, the repository was audited against every named candidate
(the five PRD visualizations, Scenario snapshots, Risk/Stakeholder/
Prioritization/`ProjectDependency`/`PortfolioSnapshot` import/export, a
membership/user-management UI) and confirmed directly against current
code — not merely repeated from a prior ADR's claim — that Scenario
snapshots and import/export registration are both still genuinely
blocked on the same unresolved product decisions ADR 0022 first flagged
(`ScenarioService.delete` still hard-deletes; `ImportEntityType` still
has the same 10 members). Of the five PRD visualizations, three carry
real cross-domain ambiguity not specified anywhere (Capacity-vs-Priority:
whose capacity, over what period; Risk-vs-Value: which of a project's
several risks; dependency timeline: `ProjectDependency` still has no
date/duration data, per ADR 0021's own unchanged finding) — WSJF
breakdown alone has zero ambiguity, since its "four inputs" are
`app/domain/prioritization.py::WSJF_CRITERION_KEYS` verbatim, already
returned in full by the unchanged Phase 17 `GET .../portfolio` response.
A membership/user-management UI was re-confirmed fully backend-ready but
not selected — a materially larger multi-flow vertical slice than one
chart. Because WSJF breakdown was already-specified, zero-backend-risk,
and carried no open product decision, no blocking question was needed
for the selection itself (per the phase brief's own "do not ask merely
for confirmation when the repository already specifies the answer").
One execution-level interpretation was made within the selected scope,
not a product decision: the PRD's "stacked bar of the four inputs" would
be misleading if all four were literally stacked together, since
`job_size` is WSJF's divisor, not a fourth additive term alongside
`business_value`/`time_criticality`/`risk_reduction_opportunity_enablement`
(whose sum genuinely is SAFe's own "Cost of Delay") — those three are
stacked, `job_size` renders as its own adjacent bar in the same chart, so
all four values are still shown together per project. Built with **zero
backend changes**, matching Phase 24's own "reuse what already exists"
precedent — `GET /api/v1/prioritization/portfolio` was already fetched by
this exact page before this phase. `features/prioritization/utils/
wsjfBreakdown.ts::buildWsjfBreakdown` is a pure, unit-tested frontend
function that copies each criterion value verbatim from `breakdown`,
never recomputing anything, and excludes any project without a complete
WSJF score rather than plotting a fabricated zero. 0 new tables, 0
migrations, 0 new permissions, 0 backend files changed. See
docs/adr/0025-wsjf-breakdown-visualization.md.

### Phase 26
AI scenario-vs-baseline prioritization comparison explanation (§18/§21) —
the item Phase 20's own brief explicitly named as intentionally deferred
"for a future phase to consider deliberately." Per the phase brief's
audit-first instruction, every item Phase 25 left deferred was
re-verified directly against current code, not merely repeated from a
prior ADR's claim: `ScenarioService.delete` still hard-deletes (Scenario
snapshots still blocked), `ImportEntityType` still has the same 10
members (import/export still blocked), `ProjectDependency` still has
only `created_at` (dependency timeline still blocked). No capability
named `explain_scenario_priority`/`explain-scenario-comparison` existed
anywhere, and `ScenarioPriorityService.compare` already returns a
complete, stable comparison shape via the unchanged Phase 20
`GET .../priority-comparison` endpoint — the third instance of an
already-proven pattern (`explain-priority`, Phase 19;
`explain-snapshot-comparison`, Phase 23), so no blocking question was
needed. Unlike Phase 25's WSJF chart, no source-material interpretation
gap existed here: every field needed (baseline/scenario score, rank,
category, `has_override`, `changed`) already exists verbatim in the
Phase 20 response, and the AI-capability shape is fully determined by
two already-shipped precedents.
`AIContextBuilder.build_for_scenario_priority_comparison` calls
`ScenarioPriorityService.compare` verbatim — no score, rank, or category
is ever recomputed by the AI layer; an unknown or cross-organization
scenario/framework id (404) is inherited from that unchanged service
call, not re-implemented. A new `scenario_priority_comparison` grounding
reference type adds one (type, project_id) pair per comparison item, the
same "one reference per collection member" shape `snapshot_comparison`/
`signal`/`skill_coverage` already established.
`POST /api/v1/ai/explain-scenario-priority-comparison`, gated by the
existing `Permission.AI_USE` only (every role) — no new permission, no
CSRF requirement (matching every other AI route). 0 new tables, 0
migrations, 0 new permissions. See
docs/adr/0026-ai-scenario-priority-comparison-explanation.md.

### Phase 27
Priority vs. Effort scatter visualization (§18/§38) — one of the five
Recharts visualizations the Phase 17 PRD's own §15 actually names. Per
the phase brief's audit-first instruction, every candidate Phase 26 left
deferred was re-verified directly against current code, not merely
repeated from a prior ADR's claim: `ScenarioService.delete` still
hard-deletes (Scenario snapshots still blocked), `ImportEntityType`
still has the same 10 members (import/export still blocked),
`app/api/v1/organizations.py` still exposes the same 10 routes
(membership UI still viable but oversized), `ProjectDependency` still
has only `created_at` (dependency timeline still blocked). Of the four
remaining PRD visualizations, Capacity-vs-Priority and Risk-vs-Value
remain genuinely blocked (no specification exists for "a project's
capacity" or for aggregating a project's several risks into one value);
Priority-vs-Effort alone is buildable with no invented semantics —
`app/domain/prioritization.py::RICE_CRITERION_KEYS` names its effort
criterion literally `"effort"`, `WSJF_CRITERION_KEYS` names the
structurally analogous denominator `"job_size"` (the PRD's own §5.1
table already lists both formulas as value-divided-by-effort), and
`calculate_ice_score` confirms ICE has no effort-like denominator at all
(a plain average, never divided by anything) — so RICE/WSJF-only scoping
is grounded in existing code, not guessed at. Because this required no
open product decision, no blocking question was needed for the
selection. Built with **zero backend changes**, matching Phase 25's own
precedent — `GET /api/v1/prioritization/portfolio` was already fetched
by this exact page before this phase.
`features/prioritization/utils/priorityEffortScatter.ts::buildPriorityEffortScatter`
is a pure, unit-tested frontend function that copies `score` and the
resolved effort-criterion value verbatim, never recomputing anything,
and excludes any project without a complete score rather than plotting
a fabricated zero; a framework with no defined effort criterion (ICE,
Weighted, MoSCoW) returns no points rather than guessing one. No
quadrant lines or "quick win" threshold are drawn — no such boundary is
defined anywhere in this codebase, and CLAUDE.md §17/§29 forbid inventing
one for display. 0 new tables, 0 migrations, 0 new permissions, 0
backend files changed. See
docs/adr/0027-priority-effort-scatter-visualization.md.

### Phase 28
Membership management UI, first slice (§16/§27) — the item every audit
from Phase 22 onward named as "fully backend-ready, deferred for size
only." Per the phase brief's audit-first instruction, every other
deferred candidate was re-verified directly against current code and
found still blocked: `ScenarioService.delete` still hard-deletes
(Scenario snapshots), `ImportEntityType` still has the same 10 members
(Import/Export registration), `ProjectDependency` still has only
`created_at` (dependency timeline), and the Capacity-vs-Priority and
Risk-vs-Value quadrant charts still have no cross-domain specification.
The membership UI was the only viable, non-blocked candidate, so no
"which candidate" blocking question was warranted — but its first-slice
boundary (a "materially larger multi-flow vertical slice") is a genuine
scoping decision, so it was put to the user, who chose **roster +
role/status management** (list every membership, change a member's role,
revoke, reactivate, add an existing account by email) over a read-only
roster or a larger slice that also created/disabled `User` accounts.
Built with **zero backend changes**: every route consumed
(`app/api/v1/organizations.py`, list/add/change-role/revoke/reactivate
memberships) already exists (Phases 12/15), is already
`Permission.MEMBERSHIP_MANAGE`-gated (Admin/Owner), already
organization-scoped (a path `organization_id` that isn't the caller's
active org 404s — `_require_active_organization`), already audited, and
already enforces the Owner-escalation rule (only an Owner may grant or
change an Owner/Admin role → 403) and the Phase 15 last-Owner invariant
(→ 422). The new frontend (`apps/web/src/features/members/`, one new
`/admin/members` route, one new nav entry) re-implements **none** of
that authorization — it is gated by `can('membership.manage')` for UX
only and surfaces the backend's own 403/422/404/409 message inline,
mirroring `features/access/views/AccessManagementPage` one-for-one.
Deliberately **out of scope**: creating or disabling `User` accounts
(`app/api/v1/users.py` untouched — "add member" takes an existing
account's email, and no account is created if none matches, per §26);
organization rename/deactivation (a separate `ORGANIZATION_MANAGE`
surface — §32-style discipline, not combined); any invitation / email /
password-reset / onboarding flow (the backend defines none, so none was
invented). 0 new tables, 0 migrations, 0 new permissions, 0 backend
files changed. See docs/adr/0028-membership-management-ui.md.

### Phase 29
User account management UI (§21/§26/§27) — the companion slice Phase 28
named as fully backend-ready and deliberately excluded. Per the phase
brief's audit-first instruction, `POST /api/v1/users`, `PATCH
/api/v1/users/{id}`, `GET /api/v1/users`, `UserService`,
`UserRepository.disable_if_safe`, `AuthService.login`, and
`ROLE_PERMISSIONS` were re-audited: the backend already supports the
full account lifecycle (create → `active` by default; `PATCH
{status: "disabled"}` routes through the Phase 15 last-Owner guard;
`PATCH {status: "active"}` re-enables), all gated by
`Permission.USER_WRITE`/`USER_READ` (Admin/Owner). No unresolved product
decision — no hard stop. Built with **zero backend changes**: a new
frontend (`apps/web/src/features/users/`, one new `/admin/users` route,
one new "Accounts" nav entry) gated by `can('user.write')` for UX only,
mirroring `features/members/` (Phase 28) and
`features/access/AccessManagementPage` one-for-one. Create an account
(email, password — exactly `UserCreate`'s `min_length=10`/`max_length=128`,
nothing more —, display name, optional link to a `Person` in the acting
organization); disable an account (behind the existing inline
confirm-then-act pattern, no modal); re-enable a `disabled` or `invited`
one. A Phase 15 last-Owner 422 is rendered **verbatim** on the row, never
re-explained by the frontend. **Multi-tenancy determined from the actual
backend, not assumed from Phase 28**: `User` management is **global** and
permission-gated, not organization-scoped — `GET /api/v1/users` is a
cross-organization account directory (ADR 0012 Decision 8) and
`PATCH /users/{id}` resolves the account globally; the *only*
organization-scoped element is the optional `person_id` link, validated
against the acting organization's People. A pre-existing property this
audit surfaced and left unchanged (the brief forbids redesigning
authorization): an Admin/Owner can, through this global `USER_WRITE`
contract, disable an account whose only membership is another
organization — guarded by the global last-Owner check, recorded in ADR
0029 as a candidate for a future explicit product decision.
Deliberately **out of scope**: organization rename/deactivate;
invitations; email verification; password-reset; SSO/OAuth; billing; any
account-directory search/filter; any new permission. 0 new tables, 0
migrations, 0 new permissions, 0 backend files changed. See
docs/adr/0029-user-account-management-ui.md.

### Phase 30
Organization settings UI — **rename only** (§21/§26/§27/§33). The last
backend-ready admin surface Phases 28-29 named. Per the phase brief's
audit-first instruction, the full organization-management contract was
established against executable code: `GET`/`PATCH /api/v1/organizations/{id}`
and `POST .../{id}/deactivate` are all `ORGANIZATION_MANAGE`-gated
(**Owner-only** — `ROLE_PERMISSIONS[OWNER] − ROLE_PERMISSIONS[ADMIN] ==
{ORGANIZATION_MANAGE}`) and `_require_active_organization`-gated (a path
id that isn't the caller's active org 404s — no IDOR). `OrganizationUpdate`
is `{name: 1..200}` only (slug immutable, `is_active` excluded); rename
preserves every relationship. **Deactivation was audited and deferred by
explicit product decision** (put to the user, three options offered):
`OrganizationService.deactivate` just flips `is_active=False` with **no
cascade, no backend guard, and no reactivation path anywhere in the
codebase** — it is irreversible through the product and denies every
member (including the acting Owner) on their next request via
`get_current_membership`. Exposing that as a one-click settings action
was judged disproportionate for a bounded slice; it stays backend-only
until a reactivation path / safety guard exists. Built with **zero
backend production changes**: a new frontend
(`apps/web/src/features/organization/`, one new `/admin/organization`
route, one new "Organization" nav entry) gated by
`can('organization.manage')` for UX only, mirroring `features/members/`
and `features/users/`. Reads `GET /organizations/{id}`; renames via
`PATCH`; on success invalidates the `['session']` query too so the
header switcher/user-menu pick up the new name. Shows the immutable slug
read-only and an Active/Inactive status badge. No deactivation control
anywhere on the page. `tests/api/test_organizations.py` gained 5 tests
documenting the previously-uncovered `GET`/`PATCH` contract (Owner
round-trip, empty-name 422, `organization.update` audit event, non-Owner
403, non-active-org id 404) — test-only, 0 production code touched. 0 new
tables, 0 migrations, 0 new permissions. See
docs/adr/0030-organization-settings-ui.md.

### Phase 31
Organization deactivation safety guard + reactivation — **backend only,
no frontend** (§4/§21/§27/§33). Phase 30 deferred the deactivation UI
because the backend was unsafe: `OrganizationService.deactivate` set
`is_active=False` with no guard, there was **no reactivation path
anywhere** (nothing set `is_active=True` except `create`), and
`get_current_membership` denies every member — the acting Owner included
— on their next request. Phase 31 makes it a safe, reversible lifecycle
a future Phase 32 UI can consume. **Safety invariant** (Phase 30's own
stated preferred direction): an organization may be deactivated only
while it has **≥ 2 active Owners** (an `OrganizationMembership`
role=Owner/status=Active whose linked `User` is also Active — Phase 15's
`count_active_owners` definition), so there is always another Owner able
to reactivate — enforced by an **atomic guarded UPDATE**
(`OrganizationRepository.deactivate_if_safe`, folding the count into the
`WHERE`, exactly like Phase 15's `change_role_if_safe`), rejection →
`DomainValidationError` → **422** (the established convention, no new
error type). Deliberate consequence: a **single-Owner org cannot be
deactivated** until a second Owner is added. **Reactivation**: new
`POST /api/v1/organizations/{id}/reactivate` → `OrganizationRead`,
CSRF-protected, authorized by resolving the caller's membership in the
**target** org directly (**not** `get_current_membership` /
`_require_active_organization`, which a deactivated org can't satisfy) —
exactly `AuthService.switch_organization`'s pattern; only an active Owner
membership may reactivate (non-member → 404, non-Owner member → 403,
unauthenticated → 401). `OrganizationService.reactivate` flips only
`is_active` — **no cascade, no membership/project/scenario/snapshot
touched**, identity and every relationship preserved, idempotent for an
already-active org. New `AuditAction.ORGANIZATION_REACTIVATE`
(open-vocabulary `String` column → **no migration**). Session/switching
behavior is **unchanged** — after reactivation the Owner's existing
session works on the next request with no re-login. Concurrency proven
against a **real file-backed SQLite database** with per-thread
connections (`tests/api/test_organization_deactivation_safety.py`,
mirroring `test_last_owner_concurrency.py`): the invariant "an inactive
org always keeps ≥ 1 active Owner and stays reactivatable" holds under
concurrent deactivate + Owner-removal. **0 new tables, 0 migrations, 0
new permissions, 0 new roles, 0 frontend changes.** `docs/openapi.json`
regenerated (also absorbed pre-existing Phase 23/26 AI-route drift). See
docs/adr/0031-organization-deactivation-safety.md.

### Phase 32
Organization deactivation / reactivation **UI** (§21/§26/§29/§33) —
**frontend only**, consuming the Phase 31 backend contract with **0
backend files changed**. On the existing Owner-gated
`/admin/organization` page (`apps/web/src/features/organization/`): a
**Deactivation section** (`DeactivateOrganizationSection`, the
established two-step inline-confirm pattern — no modal primitive)
calling `POST .../deactivate`, and an **`InactiveOrganizationPanel`**
recovery surface calling `POST .../reactivate`. The frontend performs
**no** safety logic: it does **not** compute the ≥2-active-Owner count
(no endpoint usable here exposes it — `/auth/me` lacks it and
`/memberships` lacks the linked `User.status` the guard also needs), so
per §21 it lets the backend's **422** be authoritative and surfaces it
**verbatim**, never a false success. Recovery detection is **scoped**:
`OrganizationSettingsManager` treats a **409** from its own
`GET /organizations/{id}` as "deactivated" only because the page is
already `organization.manage`-gated (a revoked membership would null the
caller's role/permissions and never reach it) — **no global 409
reinterpretation**. On deactivate/reactivate success the hooks
`invalidateQueries()` so every surface refetches into its correct state;
**no forced logout**, the existing session keeps working after
reactivation with no re-login (Phase 31's verified behavior). No new
route (the existing page hosts the recovery state), no new permission,
no new role, no `OrganizationSummary` change. **Known limitation,
deferred to Phase 33:** no global inactive-org banner (an Owner
returning to a cold app lands on a generic "no longer active" error
first, then recovers via the still-visible "Organization" nav link) — a
clean banner needs a small read-only `OrganizationSummary.is_active`
addition to `/auth/me`; and deactivated orgs still appear in the
`OrganizationSwitcher` (pre-existing, ADR 0031). See
docs/adr/0032-organization-deactivation-reactivation-ui.md.

### Phase 33
Global inactive-organization awareness & switcher cleanup (§21/§27/§29) —
closes the two Phase 32 known limitations. **Backend: 1 line of behavior
change** — `OrganizationSummary` (the org shape in `/auth/me`) gains a
read-only `is_active: bool`, populated straight from the persisted
`Organization.is_active` via the existing `model_validate` (**no
`_build_me`/`me_to_read` change, no migration** — the column exists since
Phase 12; **no new endpoint/permission/role**; `GET /organizations/mine`
already returns `is_active` via `OrganizationRead` and has no frontend
consumer, so it's untouched). `is_active` is **never derived from a
409** — it is the persisted flag; `get_current_membership` re-checking it
per request stays the authorization boundary. **Frontend:** a persistent,
shell-level `InactiveOrganizationBanner` (a `role="alert"` feature
component composed from existing primitives + a `<Link>`, **not** a new
`components/ui` primitive, **not** a modal/toast) rendered in `AppShell`
when `useAuth().user.active_organization.is_active === false` — for an
Owner (`can('organization.manage')`) it links to the **existing** Phase
32 `/admin/organization` recovery panel (no new route, no duplicated
reactivation call); for a non-Owner it says "ask an Owner." The
`OrganizationSwitcher` and `SelectOrganizationPage` now filter out
deactivated organizations (the switcher keeps the *current* one, labelled
"(inactive)", so its `<Select>` value still resolves); this is **UX
only** — `switch-organization` already 404s an inactive org. Phase 32's
existing `useDeactivate/ReactivateOrganization` `invalidateQueries()`
already refetches `/auth/me`, so the banner appears/clears with **no
re-login and no new cache code** (verified by test + a live uvicorn run:
`/auth/me` `active_organization.is_active` flips `true→false→true` with
session/role/permissions intact). Phase 32's **scoped** 409 handling on
`OrganizationSettingsManager` is untouched — no global 409 interceptor.
**Backend: 1 schema file + 2 test files, 0 migrations. Frontend:**
1 new component + 4 edits. `docs/openapi.json` regenerated (7-line diff).
See docs/adr/0033-global-inactive-organization-awareness.md.

Remaining unclaimed from the original "Phase 9+" line: external
integrations and the Chrome extension — still explicitly deferred (§22,
§23, §32) pending an explicit request, not implied to be the next phase.
Deferred items accumulated across Phases 11-22 that a future phase should
pick up deliberately, not assume: SSO/OAuth, billing, organization
hierarchies, cross-organization data sharing, and per-organization feature
flags (see ADR 0012's Consequences — its other listed gap, the
per-organization "last active Owner account" disable invariant, is
resolved as of Phase 15, docs/adr/0015-last-owner-invariant.md; Team→
Project inheritance and Person-keyed/Scenario instance-scoping, ADR 0011's
gaps, are resolved-as-retained per Phase 16,
docs/adr/0016-instance-authorization-completion.md — re-opening either
requires a new, explicit product requirement naming the missing ownership
concept, not a rebuild of what Phase 16 already decided);
Risk Import/Export registration and an org-wide cross-project risk
register (see ADR 0013's Consequences — its other listed gap, the
Prioritization (§18) domain concept, is resolved as a v1 slice per Phase
17, docs/adr/0017-prioritization-engine.md);
Stakeholder Import/Export registration and an org-wide cross-project
stakeholder register (see ADR 0014's Consequences); independent
verification of the Phase 15 last-owner concurrency guard against a real
PostgreSQL instance under true multi-connection MVCC — only SQLite's
single-file writer serialization was actually tested (see ADR 0015's
Consequences); the organization-settings UI is now **complete** for the
current backend surface — **rename** as of Phase 30
(docs/adr/0030-organization-settings-ui.md), the backend
deactivation/reactivation lifecycle as of Phase 31
(docs/adr/0031-organization-deactivation-safety.md; ≥2-active-Owners
atomic guard + `POST /api/v1/organizations/{id}/reactivate`), and the
**deactivation/reactivation frontend** as of Phase 32
(docs/adr/0032-organization-deactivation-reactivation-ui.md;
frontend-only, a Deactivation section + an inactive-org recovery panel
that surfaces the backend's 422/403/404 verbatim and never re-derives
the Owner count), and completed as of Phase 33
(docs/adr/0033-global-inactive-organization-awareness.md;
`OrganizationSummary.is_active` on `/auth/me` + a persistent shell
`InactiveOrganizationBanner` + `OrganizationSwitcher`/
`SelectOrganizationPage` filtering out deactivated orgs — the two
follow-ups ADR 0032 named). The membership roster UI is
resolved as of Phase 28 (docs/adr/0028-membership-management-ui.md) and
the `User`-account create/disable/re-enable UI as of Phase 29
(docs/adr/0029-user-account-management-ui.md — so Phase 15's last-Owner
invariant now has two UI surfaces, both rendering its 422 inline; an
account-directory search/filter box and an explicit product decision on
whether `USER_WRITE` should be organization-scoped rather than global are
the named remainders from ADR 0029); the five remaining Recharts
prioritization visualizations (ICE/WSJF/MoSCoW formulas, project
dependency tracking/cycle detection, and criteria editing are resolved as
of Phase 18, docs/adr/0018-prioritization-frameworks-and-dependencies.md;
AI priority explanation and the Priority Explanation Panel are resolved
as of Phase 19, docs/adr/0019-ai-priority-explanation.md;
scenario-vs-baseline prioritization comparison, including its frontend
view, is resolved as of Phase 20,
docs/adr/0020-scenario-priority-comparison.md, via explicit
scenario-scoped criterion overrides — an AI interpretation of this
comparison, deliberately left for a future phase per Phase 20's own
brief, is resolved as of Phase 26,
docs/adr/0026-ai-scenario-priority-comparison-explanation.md; portfolio snapshots are resolved as of Phase
21, docs/adr/0021-portfolio-snapshots.md, and snapshot diff/trend is
resolved as of Phase 22, docs/adr/0022-portfolio-snapshot-comparison.md —
a snapshot of a scenario's hypothetical ranking remains unbuilt, genuinely
blocked on a product decision about `Scenario`'s hard-delete lifecycle
(unlike `PrioritizationFramework`, `Scenario` supports a real delete —
reconfirmed unresolved, directly against current code, by the Phase 26
audit);
an AI explanation of a snapshot comparison is resolved as of Phase 23,
docs/adr/0023-ai-snapshot-comparison-explanation.md, and a multi-snapshot
score-over-time trend chart is resolved as of Phase 24,
docs/adr/0024-portfolio-snapshot-trend.md (a frontend-only feature, zero
backend changes — a rank-over-time or toggleable variant was audited and
explicitly not selected, per that ADR's Decision); the PRD's own §15 WSJF
breakdown visualization is resolved as of Phase 25,
docs/adr/0025-wsjf-breakdown-visualization.md (also a frontend-only
feature, zero backend changes); the PRD's own §15 Priority-vs-Effort
scatter is resolved as of Phase 27,
docs/adr/0027-priority-effort-scatter-visualization.md (also a
frontend-only feature, zero backend changes, scoped to RICE/WSJF only
since ICE/Weighted have no defined effort criterion) — the remaining
three PRD visualizations (Capacity-vs-Priority matrix, Risk-vs-Value
quadrant, dependency timeline) remain unbuilt, all three genuinely
blocked on unspecified cross-domain semantics, reconfirmed unchanged by
the Phase 27 audit; see ADR 0020's, ADR 0021's, ADR 0022's, ADR 0023's,
ADR 0024's, ADR 0025's, ADR 0026's, and ADR 0027's Consequences for the
remaining named boundaries);
Prioritization, Project Dependency, and Portfolio Snapshot Import/Export
registration (matching Risk/Stakeholder's own precedent, not specified —
a Phase 22 audit of the actual import/export code confirmed neither Risk
nor Stakeholder has a natural identity key for CSV upsert-matching, a
further open question any future phase attempting this would need to
resolve first, reconfirmed still open by the Phase 25, Phase 26, and
Phase 27 audits); the membership roster/role/status-management UI is
resolved as of Phase 28 (docs/adr/0028-membership-management-ui.md) and
the `User`-account create/disable/re-enable UI as of Phase 29
(docs/adr/0029-user-account-management-ui.md), and organization **rename**
as of Phase 30 (docs/adr/0030-organization-settings-ui.md) — all
frontend-only. Phase 31 (docs/adr/0031-organization-deactivation-safety.md)
made the backend deactivation lifecycle safe and reversible (≥2-Owner
guard + reactivate endpoint), backend-only, and Phase 32
(docs/adr/0032-organization-deactivation-reactivation-ui.md) added the
frontend for it (Deactivation section + inactive-org recovery panel),
frontend-only, and Phase 33
(docs/adr/0033-global-inactive-organization-awareness.md) completed the
loop (`OrganizationSummary.is_active` on `/auth/me` + a shell
inactive-org banner + switcher filtering; 1 backend schema field, 0
migrations). The organization lifecycle UX is now complete for the
current backend surface.
None of these are scheduled — do not build any of them without an
explicit request, per §32.

Do not jump ahead while the underlying domain is unstable.

---

## 40. Final Principle

Do not optimize for writing the most code.

Optimize for building the most understandable, reliable, explainable, maintainable, and extensible system.

CapacityOS should eventually be capable of becoming:
- A useful internal operations tool
- An open-source project
- A portfolio-grade project
- An API platform
- A Slack-integrated planning system
- A Chrome extension
- A commercial product

None of those possibilities justify compromising the correctness of the core capacity engine.

Build the foundation properly.

Then build on it.
