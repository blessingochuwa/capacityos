# ADR 0009: Phase 9 production readiness, governance & observability

- **Status:** Accepted
- **Date:** 2026-08-17

## Context

Phases 1–8 built CapacityOS's functionality: a deterministic capacity
engine, scenario planning, operational insights, import/export, skills,
and an optional AI interpretation layer. None of that work made the
*application itself* — as a running process an operator has to start,
watch, and trust — production-ready. There was no structured logging, no
request correlation, no distinction between "the process is alive" and
"the process can serve requests," no validation preventing a misconfigured
deployment from silently running on development defaults, and no
consistent way to tell an expected client error apart from an unexpected
server failure in the logs.

Phase 9's job is explicitly NOT another feature. It closes those gaps
without adding a second engine, a vendor observability platform, or
authentication that nothing in this phase's objectives actually requires.

## Audit findings (before any code changed)

Read in full: CLAUDE.md, `docs/architecture.md`, `docs/domain-concepts.md`,
all 8 prior ADRs, both CI workflows, `app/core/{config,database,exceptions}.py`,
`app/main.py`, the health endpoint, Alembic's `env.py` and all 4 migrations,
every Pydantic schema for unbounded free-text fields, and every frontend
feature page for loading/error/empty-state coverage.

**Solid, unchanged**: the deterministic-engine boundary; CSV
formula-injection defense and import file/row limits (Phase 6); AI
grounding, typed provider exceptions, and mock-provider determinism (Phase
8); parameterized SQLAlchemy queries throughout (no raw SQL string
building); every query-driven frontend page's `QueryBoundary`/`ErrorState`/
`EmptyState` coverage, and the mutation-driven Import/Export page's
equivalent inline handling; Alembic migrations, which apply cleanly from an
empty database in a deterministic order.

**Real gaps, closed by this phase**: zero structured logging anywhere in
the backend; no request correlation; no environment/production-safety
validation; one endpoint that checked nothing standing in for both
liveness and readiness; no catch-all exception handler (an unexpected
failure fell through to Starlette's bare default response, unlogged); eight
free-text schema fields (`description`/`notes` across Project, Team,
Skill, Scenario, Allocation, AvailabilityException, PersonSkill,
ProjectSkillRequirement) with no length bound, unlike `name`/`label`
fields, which already had one; no request body-size ceiling outside the
import endpoints.

**Deliberately absent, and staying that way**: authentication. CLAUDE.md
§39 lists it under "Phase 9+" — a multi-phase future bucket, not a
requirement of this specific phase — and nothing in this phase's seven
objectives (CI, configuration, observability, error handling, security
hardening, database safety, documentation) depends on knowing who's
calling the API. Introducing it here would be exactly the "large
authentication project" this phase's own brief says not to become.

## Decisions

**Structured logging: stdlib `logging` + a custom JSON `Formatter`, no new
dependency.** `app/core/logging.py`'s `JsonFormatter` emits one JSON object
per line to stdout; `configure_logging()` installs it on the root logger
once, at import time, so every module's `logging.getLogger(__name__)`
inherits it with zero per-module setup. No `structlog`, no
`python-json-logger`, no vendor SDK — `logging` and `json` already do
everything this phase needs (CLAUDE.md §34, spec §14).

**Request correlation via a `ContextVar`, not a parameter threaded through
every function.** `request_id_var` is set once per request by
`RequestContextMiddleware` (`app/api/middleware.py`) — reading an incoming
`X-Request-ID` header or generating a UUID — and `JsonFormatter` picks it
up automatically for every log line made anywhere during that request
(a route, a service, an exception handler), without any call site having
to know about it. The middleware also times the request and logs exactly
one "request completed" line per request (INFO, or WARNING for a 5xx),
and echoes the id back in the response header so a caller can hand an
operator "the response I got" and have it map directly to specific log
lines.

**One middleware, not a framework, and it only ever sees responses, never
exceptions.** `RequestContextMiddleware` sits outside FastAPI's
`ExceptionMiddleware` layer (added last in `main.py`, making it outermost
per Starlette's middleware-stack ordering). By the time control returns to
it, any exception a route raised has already become a normal `Response`
via a registered `@app.exception_handler` — including the new catch-all
below — so request-lifecycle logging (this middleware) and error-detail
logging (the handlers) never duplicate or race each other.

**A stdlib logging landmine, found and documented**: `extra={"filename":
...}` raises `KeyError` at log time, not at lint/import time, because
`filename` collides with one of `LogRecord`'s own reserved constructor
attributes. Hit while adding import-endpoint logging (`app/api/v1/imports.py`),
caught immediately by the full test suite (52 tests failed with an
identical traceback), fixed by renaming the field to `upload_filename`, and
now documented directly in `app/core/logging.py`'s module docstring with
the complete reserved-name list, so the next call site doesn't rediscover
it the same way.

**What logging deliberately never includes**: API keys, the
`ANTHROPIC_API_KEY` value, authorization tokens, passwords, full AI prompts
(`AIGenerationRequest.context`/`.question` — can contain project
descriptions, skill notes, and other business text), the model's raw
output, full uploaded import files, or raw database/SQL error text. AI
provider-failure logging (`AIService._log_provider_failure`) carries only
`provider`, `model`, `duration_ms`, and a `failure_kind` enum-like string
(`timeout`/`rate_limited`/`malformed_output`/`provider_unavailable`) —
proven, not just asserted, by
`test_provider_failure_logging_never_includes_the_prompt_context_or_question`,
which plants a marker string in the context and asserts it appears in zero
log records. Import-endpoint logging carries entity type, mode, upload
filename, and row/error counts — never file content. The catch-all and
database-error exception handlers log `exception_type` and a full
traceback server-side via `exc_info`, but the client only ever receives a
fixed, generic message.

**Liveness and readiness are two routes with two different failure
meanings, not one endpoint with a query parameter.** `GET /api/v1/health`
(liveness) checks nothing external — a response only means the ASGI app is
routing requests. `GET /api/v1/health/ready` (readiness) checks database
connectivity through a dedicated, isolated `engine.connect()` call, never
the request-scoped `get_db` session (so a failed probe can't interact with
that session's commit/rollback lifecycle). Readiness deliberately does NOT
check AI provider availability, matching CLAUDE.md §21 and ADR 0008: AI is
optional, so a missing or unreachable Anthropic key must never make an
otherwise-healthy instance report "not ready." `GET /api/v1/ai/status`
remains the dedicated, separate way to check AI-specific availability.

**Configuration safety is an explicit, testable pure function, called only
at startup, only for `environment=production`.**
`validate_production_config(settings) -> list[str]` (`app/core/config.py`)
checks three concrete, realistic risks: a SQLite `DATABASE_URL` (production
requires PostgreSQL-compatible storage per CLAUDE.md §7), `AI_PROVIDER=mock`
(documented in ADR 0008 as dev/demo-only, never real decision support), and
an empty or wildcard `API_CORS_ORIGINS`. It is a pure function — no I/O, no
app, fully unit-testable — and it is NEVER called for `environment=
development` or `environment=test`, where every one of those defaults is
intentional. `main.py`'s new `lifespan` context manager is the one caller
that turns a non-empty result into a hard startup failure
(`ProductionConfigError`), logged in full before raising. This is a
deliberate fail-fast choice over a warning: an operator who sets
`ENVIRONMENT=production` while `DATABASE_URL` is still pointed at SQLite
gets an immediate, actionable failure instead of a silently misconfigured
deployment. `environment` itself defaults to `"development"`, so an
unconfigured checkout never silently behaves as production, and nothing
else in the application branches on this value — it exists solely to drive
this one validation gate.

**A consistent error contract, extending FastAPI's own conventions rather
than replacing them.** The existing `{"detail": ...}` body shape stays —
it's already what the frontend's `extractDetail` parses, and it already
distinguishes a field-validation array (FastAPI's native
`RequestValidationError`) from a business-rule string (the existing
`DomainValidationError` handler). Two handlers were added, both dispatched
by Starlette's MRO-based exception lookup (the most specific registered
class always wins, regardless of registration order — verified by
`test_integrity_error_still_takes_precedence_over_the_broader_database_handler`):
a `SQLAlchemyError` handler → 503 "The database is temporarily unavailable,"
distinguishing an infrastructure failure from an application bug, and a
catch-all `Exception` handler → 500 with a fixed generic message. Neither
ever echoes the real exception's message to the client — only the
server-side log gets it, with a full traceback via `exc_info`.

**Free-text field length bounds, added uniformly, not selectively.** Every
writable `description`/`notes` field across Project, Team, Skill, Scenario,
Allocation, AvailabilityException, PersonSkill, and
ProjectSkillRequirement now has `max_length=2000` — generous for legitimate
multi-paragraph notes, small enough to bound worst-case storage/transport
cost. `name`/`label` fields already had bounds (200 chars) from earlier
phases; this closes the one category of input that didn't. Read-only
response schemas were left unbounded — they reflect already-stored data
that can never exceed the write-side bound once it's enforced, so a bound
there would be redundant defensive validation with no real boundary to
protect.

**A single, uniform request body-size ceiling, not a per-route policy.**
`MaxBodySizeMiddleware` rejects any request whose declared `Content-Length`
exceeds `Settings.max_request_body_bytes` (default 5 MiB) with a 413,
before any body is read. Set to match `import_max_file_size_bytes` exactly,
rather than a smaller general limit plus a path-based exemption for import
routes — simpler, and the import endpoints' own, more specific Level-1
file-size check still runs afterward and gives a more actionable error for
that case. This is a `Content-Length` check, not a streaming byte-count, so
it only catches honestly-reported sizes — a deliberate, documented
limitation appropriate to this app's realistic threat model (an
accidentally-or-deliberately oversized legitimate JSON payload), not a
hardened anti-DoS measure.

**CI gained one new step — migration consistency — and deliberately not
`alembic check`.** `uv run alembic upgrade head` now runs in `api-ci.yml`
before lint/typecheck/test, proving every migration applies cleanly to an
empty database in order. `alembic check` was considered and rejected for
this purpose: it currently fails on this repository for a known, benign,
already-documented reason (ADR 0007) — SQLite's `CHECK` constraint
reflection doesn't match what SQLAlchemy's autogenerate expects, for every
`CheckConstraint` in every migration, regardless of correctness. Wiring
that into CI would make every single run red for a reason that isn't a
real migration problem, which is worse than not checking migrations in CI
at all.

**The setup-uv CI failure this phase started with** (`astral-sh/setup-uv`
resolving `version: '0.11.x'`, an unsupported wildcard selector) was fixed
in a prior session turn, before this phase's audit began: pinned via
`[tool.uv] required-version = "==0.11.25"` in `apps/api/pyproject.toml`
(uv enforces this at runtime itself — verified by deliberately breaking the
pin and confirming `uv` rejects it) and `version-file:
apps/api/pyproject.toml` on the `setup-uv` step, reading that pin as the
source of truth instead of a second, separately-maintained value in the
workflow YAML. `astral-sh/setup-uv` is pinned to the exact commit SHA for
`v10.0.1` (their own documented recommended usage, and a hard requirement
discovered mid-fix: the project stopped publishing floating major-version
tags at v8.0.0 — `astral-sh/setup-uv@v10` does not resolve to anything).

## Consequences

- New modules: `app/core/logging.py`, `app/api/middleware.py`. Extended:
  `app/core/config.py` (+`environment`, +`log_level`,
  +`max_request_body_bytes`, +`validate_production_config`,
  +`ProductionConfigError`), `app/core/exceptions.py` (+2 handlers, logging
  added to all 4 existing ones), `app/main.py` (+`lifespan`, +2
  middleware), `app/api/v1/health.py` (+readiness route),
  `app/api/v1/imports.py` (+logging), `app/services/ai_service.py`
  (+logging, never of prompt content).
- 8 schema files gained a `max_length=2000` bound on a free-text field.
- 0 new database tables, 0 new migrations — every Phase 9 change is
  application-layer, not data-layer.
- Backend: +30 tests across 6 new files
  (`tests/core/test_config.py`, `tests/core/test_logging.py`,
  `tests/api/test_health.py`, `tests/api/test_middleware.py`,
  `tests/api/test_error_handling.py`, `tests/api/test_lifespan.py`) plus
  1 added to `tests/services/test_ai_service.py` — 485 total (454
  pre-Phase-9 + 31 new), all passing with zero regressions.
- **A real bug was caught by the full test suite, not a targeted one**: the
  `filename`/`LogRecord` collision above broke 52 pre-existing import tests
  the moment logging was added to the import endpoints — found and fixed
  within the same session before it could reach a commit.
- **Known limitation**: `MaxBodySizeMiddleware` trusts the declared
  `Content-Length` header rather than counting streamed bytes — a
  deliberate, documented scope decision (see Decisions), not an oversight.
- **Known limitation**: readiness checks database connectivity only, by
  design — see Decisions for why AI is excluded.
- **Deferred, matching the phase boundary**: authentication, a paid
  observability platform, async import job infrastructure, any change to
  the deterministic engine, SQLite migration-away (production posture is
  documented, not enforced by a migration).
