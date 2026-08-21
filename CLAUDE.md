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

Remaining unclaimed from the original "Phase 9+" line: external
integrations and the Chrome extension — still explicitly deferred (§22,
§23, §32) pending an explicit request, not implied to be the next phase.
Deferred items accumulated across Phases 11/12/13/14 that a future phase
should pick up deliberately, not assume: Team→Project access-grant
inheritance and instance-level scoping for Person-keyed resources
(WorkingSchedule, AvailabilityException, PersonSkill, Scenario — see ADR
0011's "Future multi-tenancy seam"/this document's Phase 12 section);
SSO/OAuth, billing, organization hierarchies, cross-organization data
sharing, per-organization feature flags, and a per-organization "last
active Owner account" disable invariant (see ADR 0012's Consequences);
Risk Import/Export registration, an org-wide cross-project risk register,
and the Prioritization (§18) domain concept (see ADR 0013's Consequences);
Stakeholder Import/Export registration and an org-wide cross-project
stakeholder register (see ADR 0014's Consequences). None of these are
scheduled — do not build any of them without an explicit request, per §32.

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
