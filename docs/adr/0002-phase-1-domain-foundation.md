# ADR 0002: Phase 1 domain foundation decisions

- **Status:** Accepted
- **Date:** 2026-08-10

## Context

Phase 1 introduces CapacityOS's first real domain tables (Person, Team, TeamMembership, Project, Allocation, WorkingSchedule/WorkingScheduleEntry, AvailabilityException) — see [docs/domain-concepts.md](../domain-concepts.md) for what each one means. This ADR records the implementation decisions made along the way, several of which were only discovered to be necessary by actually building and testing the schema rather than by design alone.

## Decisions

**Primary keys: UUID**, confirmed with the user before implementation — no PK strategy existed yet (Phase 0 created no domain tables), and this was flagged as the one genuinely hard-to-reverse fork in the road. Implemented via a shared `UUIDPrimaryKeyMixin` (`app/models/base.py`), Python-side `uuid.uuid4()` default so the ID is known before flush.

**Timestamps** are timezone-aware (`DateTime(timezone=True)`), set application-side via `datetime.now(UTC)` rather than `server_default`, so dev (SQLite) and production (PostgreSQL) behave identically without relying on either database's own clock functions.

**Controlled vocabularies are `enum.StrEnum` + SQLAlchemy `Enum(..., native_enum=False)`.** `native_enum=False` stores them as portable `VARCHAR` (works identically on SQLite and PostgreSQL, no `ALTER TYPE` needed to extend). Three of the four enums (`EmploymentStatus`, `ProjectStatus`, `AllocationUnit`) additionally pass `create_constraint=True` to get a real database CHECK constraint — this was **not** the default outcome and had to be fixed: SQLAlchemy's `Enum` type has defaulted `create_constraint` to `False` since 1.1, so the first migration generated had *no* CHECK constraints on any enum column despite `native_enum=False` being set. This was caught by directly inspecting the generated SQLite DDL rather than trusting the ORM layer, and fixed by adding `create_constraint=True` explicitly to the three columns that should be database-enforced.

**`AvailabilityType` is the one enum without `create_constraint`** (left at the default `False`) — CLAUDE.md is explicit that availability reasons "must not be hard-coded into the database structure," so this vocabulary is enforced at the Pydantic/API layer only. This is proven by a dedicated test (`test_availability_type_has_no_db_check_constraint`) that writes an arbitrary string directly via raw SQL and confirms the database accepts it.

**Naming convention on `Base.metadata`** (`app/core/database.py`): gives every otherwise-unnamed constraint (foreign keys, primary keys, the `teams.name` unique constraint) a deterministic, table-scoped name. Without this, SQLite and PostgreSQL each auto-name unnamed constraints differently and non-reproducibly, which would break a future migration's ability to reference them (e.g. to drop or alter one). There is deliberately no `"ck"` entry in the convention — every `CheckConstraint` in this codebase already has an explicit, hand-chosen name; adding a `"ck"` template as well would have wrapped that name a second time (confirmed by generating the migration both ways: with the `"ck"` entry, `ck_project_end_after_start` became `ck_projects_ck_project_end_after_start`).

**`display_name` is a stored column**, defaulted by `PersonService.create` to `"{first_name} {last_name}"` when not supplied, but overridable. A pure computed property was considered (true single source of truth, zero drift risk) but rejected because a real preferred/display name distinct from the legal name is common, and a stored column stays queryable/sortable in SQL.

**`allocation_hours`/`WorkingScheduleEntry.hours`/`AvailabilityException.hours` use `Numeric`/`Decimal`, not `float`** — avoids float-rounding surprises on values a future capacity engine will sum and compare.

**List responses use a `Page[T]` envelope** (`{"items": [...], "total": N}`) instead of bare arrays, so pagination fields can be added later without a breaking response-shape change.

**Deletes are hard deletes** for Phase 1 — simplest CRUD, matches "basic CRUD to validate the domain." `Person.employment_status` already covers "is this person currently engaged"; soft-delete/deactivation workflows are deferred.

**Transaction handling moved into `get_db`** (`app/core/database.py`): commit once at the end of a successful request, rollback on any exception, always close. This didn't exist in Phase 0 (the health check never wrote anything) and had to be added now that routes perform real writes. Repositories only `flush()` (never commit/rollback), so constraint violations surface immediately mid-request without ending the transaction early, and the single commit point stays in one place.

**`WorkingScheduleService.update` flushes after clearing old entries, before adding new ones.** This was a real bug caught by the API test suite, not a design choice made up front: replacing a schedule's entries via `collection.clear()` followed immediately by `collection.extend(...)` let SQLAlchemy's unit-of-work insert the replacement row for a given weekday *before* deleting the old one in the same flush, tripping the `(working_schedule_id, weekday)` unique constraint whenever the new entries reused a weekday from the old set — which is the common case (e.g. changing Monday's hours from 8 to 4). Fixed by flushing the deletion before adding replacements.

**Dependency: `pydantic[email]`** (pulls in `email-validator`) — Pydantic's own official companion package, needed for the spec's explicit "valid email format" requirement.

**Lint exceptions, both narrow and justified** (`apps/api/pyproject.toml`): `B008` (flake8-bugbear's "no function calls in argument defaults") is ignored under `app/api/**` — FastAPI's `Depends()`/`Query()` are *designed* to be used exactly this way (FastAPI inspects the default value itself to wire up dependency injection); this is the correct, framework-mandated pattern, not the mutable-default bug B008 exists to catch. `E501` is ignored under `alembic/versions/**` — hand-rewrapping Alembic's autogenerated long lines would make the file diverge from what `alembic revision --autogenerate` actually produced.

**Modernized to Python 3.14 idioms during lint cleanup**: `class Foo(str, Enum)` → `class Foo(StrEnum)`; `Generic[T]` + `TypeVar` → PEP 695 syntax (`class BaseRepository[ModelT: Base]`, `class Page[T](BaseModel)`) for both the repository base class and the `Page` schema. Verified Pydantic 2.13 supports PEP 695 generics directly.

**`alembic check` reports a false-positive diff for the three CHECK-constrained enum columns** (`ck_people_employment_status`, `ck_projects_status`, `ck_allocations_allocation_unit`) even immediately after generating and applying a fresh migration from current models. This is a documented Alembic/SQLAlchemy limitation: SQLite reflects a CHECK constraint's stored SQL as a literal `IN ('ACTIVE', 'INACTIVE')` string, while SQLAlchemy's freshly-compiled in-memory version of the same constraint renders as a bind-parameter placeholder (`IN (__[POSTCOMPILE_param_1])`) — semantically identical, textually different, and Alembic's constraint comparator does a text match. Verified this is cosmetic, not a real defect, two ways: (1) direct SQLite DDL inspection shows the correct literal constraint is actually stored and enforced; (2) `test_employment_status_check_constraint_rejects_arbitrary_value` and the other CHECK-constraint tests pass against the live applied database. A future engineer running `alembic check` on these three tables can expect this specific diff and should not "fix" it by regenerating migrations — it will reappear every time.

## Consequences

- Extending `EmploymentStatus`, `ProjectStatus`, or `AllocationUnit` requires a migration (to widen the CHECK constraint); extending `AvailabilityType` does not.
- `alembic check` / `alembic revision --autogenerate` will always show a spurious diff for the three CHECK-constrained enum columns; this is expected (see above), not a sign of real drift, as long as no other constraint changes are mixed into the same diff.
- Any future entity needing the same "replace a full child collection" pattern as `WorkingSchedule.entries` should follow the same clear-then-flush-then-extend sequence.
