# Production Readiness

Operational reference introduced in Phase 9. See
[docs/adr/0009-phase-9-production-readiness.md](adr/0009-phase-9-production-readiness.md)
for the reasoning behind these decisions; this document is the practical
"how do I run/operate/troubleshoot this" reference.

## Local development

Backend:

```bash
cd apps/api
uv sync
cp ../../.env.example ../../.env   # only if you haven't already
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Frontend:

```bash
cd apps/web
npm install
npm run dev
```

The backend runs completely without any AI provider configured
(`AI_PROVIDER=none`, the default) — every deterministic feature (Capacity,
Scenarios, Insights, Skills, Import/Export) works with zero API keys and
zero paid infrastructure. Set `AI_PROVIDER=mock` for deterministic,
non-LLM AI panels during local development, or `AI_PROVIDER=anthropic` plus
`ANTHROPIC_API_KEY` for real AI explanations.

**First-time setup requires one more step (Phase 10): create the first
Owner account.** There is no open self-registration — run this once,
after migrating:

```bash
uv run python ../../scripts/create_first_owner.py
```

Prompts for an email/display name/password (or set
`CAPACITYOS_OWNER_EMAIL`/`CAPACITYOS_OWNER_NAME`/`CAPACITYOS_OWNER_PASSWORD`
for scripted bootstrap). Refuses to run if an Owner already exists — every
subsequent user, including additional Owners, is created via `POST
/api/v1/users` by an existing Owner/Admin. See
[docs/adr/0010-authentication-rbac-audit.md](adr/0010-authentication-rbac-audit.md).

## Environment configuration

See `.env.example` for the full, documented list. The variables introduced
in Phase 9:

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `development` \| `test` \| `production`. Drives `validate_production_config` (see below) — nothing else in the app branches on it. |
| `LOG_LEVEL` | `INFO` | Standard Python logging level name. |
| `MAX_REQUEST_BODY_BYTES` | `5242880` (5 MiB) | Hard cap on every request body, enforced before any body is read. |

The variable introduced in Phase 10:

| Variable | Default | Purpose |
|---|---|---|
| `SESSION_TTL_HOURS` | `24` | Fixed absolute session lifetime from login — no silent sliding renewal. There is no `SESSION_SECRET_KEY`: session tokens are random opaque values compared by hash, never signed/encrypted, so there is nothing to provision or rotate. The session cookie is automatically `Secure` (HTTPS-only) whenever `ENVIRONMENT=production` — this is computed, not a separate setting an operator could forget to flip. |

## Running checks

Backend (from `apps/api`):

```bash
uv run ruff check .        # lint
uv run pyright              # type check
uv run pytest                # tests
uv run alembic upgrade head  # migration consistency — see "Migrations" below
```

Frontend (from `apps/web`):

```bash
npm run lint         # oxlint
npm run typecheck    # tsc -b --noEmit
npm run test          # vitest run
npm run build          # production build
```

## Migrations

Alembic migrations live in `apps/api/alembic/versions/`. To apply the
latest schema to a fresh or existing database:

```bash
cd apps/api
uv run alembic upgrade head
```

CI runs this exact command against an empty database on every push/PR that
touches `apps/api/**`, proving every migration applies cleanly and in
order — see `.github/workflows/api-ci.yml`.

**Do not run `uv run alembic check` as a correctness gate.** It currently
reports every `CheckConstraint` in every migration as a false-positive
"new upgrade operation detected" — a known SQLite `CHECK`-constraint
reflection limitation (SQLAlchemy's autogenerate can't read a
CHECK-constrained column's definition back out of SQLite the way it wrote
it), documented in
[ADR 0007](adr/0007-phase-7-skills-bottleneck-analysis.md) and
[ADR 0009](adr/0009-phase-9-production-readiness.md). It is not a sign of
schema drift; the migrations are correct.

## CI expectations

Two independent GitHub Actions workflows, each scoped to its own path
prefix so an `apps/web` change never triggers the API workflow or vice
versa:

- **`api-ci.yml`**: `uv sync` → `alembic upgrade head` → `ruff check` →
  `pyright` → `pytest`. Requires no secrets — every AI-related test uses
  the deterministic mock provider (`AI_PROVIDER` is never set in CI).
- **`web-ci.yml`**: `npm ci` → lint → typecheck → test → production
  build.

Both cache dependencies by default (`setup-uv`'s cache is on automatically
whenever `uv.lock` is present; `setup-node`'s `cache: 'npm'` caches
`node_modules`).

## Health and readiness

| Endpoint | Question it answers | Checks |
|---|---|---|
| `GET /api/v1/health` | Is the process alive? | Nothing external. Always cheap. |
| `GET /api/v1/health/ready` | Can this instance serve requests that need its dependencies? | Database connectivity, via an isolated connection. |

Readiness deliberately never checks AI provider availability — AI is
optional, so a missing or unreachable Anthropic key must never make an
otherwise-healthy instance report "not ready." Use `GET /api/v1/ai/status`
to check AI-specific availability.

## Logging

Every log line is one JSON object on stdout:

```json
{"timestamp": "...", "level": "INFO", "logger": "capacityos.request", "message": "request completed", "request_id": "...", "method": "GET", "path": "/api/v1/health", "status_code": 200, "duration_ms": 1.2}
```

- `request_id` appears on every log line made during a request (from a
  route, a service, or an exception handler) — read or generate it via the
  `X-Request-ID` request/response header to correlate a specific HTTP call
  with its log lines.
- Log level is configurable via `LOG_LEVEL`.
- **Never logged**: API keys, the Anthropic API key, authorization tokens,
  passwords, full AI prompts or model output, full uploaded import files,
  raw database/SQL error text. Exception handlers log the exception type
  and a full traceback server-side (`exc_info`); the client only ever
  receives a fixed, generic message.
- `uvicorn.access` logging is disabled — `RequestContextMiddleware`'s
  "request completed" line already covers the same information,
  structured and correlated, once per request.

## AI configuration

See [ADR 0008](adr/0008-phase-8-ai-insight-layer.md) for the full design.
In short: `AI_PROVIDER=none` (default) disables AI entirely with zero
impact on any deterministic feature; `AI_PROVIDER=mock` enables a
deterministic, non-LLM provider for local development/demos only, never
production (`validate_production_config` refuses to start a
`ENVIRONMENT=production` deployment configured this way); `AI_PROVIDER=
anthropic` plus `ANTHROPIC_API_KEY` enables real AI explanations. The key
is server-side only and never reaches `apps/web`.

## Production configuration considerations

Set `ENVIRONMENT=production` to enable `validate_production_config`, which
refuses to start (raising `ProductionConfigError`, logged in full first)
if any of the following are still in effect:

- `DATABASE_URL` pointing at SQLite — production requires
  PostgreSQL-compatible storage (CLAUDE.md §7).
- `AI_PROVIDER=mock` — canned demo output, never real decision support.
- `API_CORS_ORIGINS` empty or containing a wildcard — production CORS must
  explicitly allowlist the deployed frontend origin(s).

This check runs once, at startup, and only when `ENVIRONMENT=production`.
`development` and `test` are never subject to it — SQLite, the mock
provider, and permissive CORS are all intentional defaults there.

### Known SQLite limitations

- Development/demo convenience only — the domain layer makes no
  SQLite-specific assumptions, but SQLite itself has real limitations
  (single-writer locking, weaker concurrent-write semantics, and the
  `CHECK`-constraint reflection quirk mentioned above under Migrations)
  that make it unsuitable for concurrent production traffic.
- `validate_production_config` refuses to start a `production`-labeled
  deployment on SQLite (see above) — this is a startup guard, not a
  migration; CapacityOS does not automatically convert a SQLite database
  to PostgreSQL.

## Prototype deployment (Phase 52)

Status, as of Phase 52: **ready for deployment, not deployed.** Everything
below was verified locally (PostgreSQL 16 included). Nothing has been
verified on Vercel or on a hosted backend yet; see "Still unverified".

### Topology

```text
browser ──https──▶ Vercel (apps/web static build)
                     ├─ /api/*  ──proxy──▶ Python web service (apps/api, uvicorn)
                     └─ /*      ──▶ index.html (SPA fallback)        │
                                                                     ▼
                                                        managed PostgreSQL
```

**The browser must only ever talk to one origin.** Authentication uses two
host-only, `SameSite=Lax` cookies set by the API (`capacityos_session`,
httpOnly; `capacityos_csrf`, readable by JS). The frontend reads the CSRF
cookie through `document.cookie` and echoes it as `X-CSRF-Token` on every
mutation (`apps/web/src/api/client.ts`). If the frontend and API were on
different sites, the browser would never send the Lax session cookie (every
request would 401) and the frontend could not read the API's CSRF cookie
(every mutation would 403). Local development only works because browsers
treat `localhost:5173` and `localhost:8000` as the same site. The Vercel
proxy keeps everything on the Vercel origin, so no authentication, cookie,
or CSRF code changes are needed. Do not "fix" a split deployment by
loosening cookies or CSRF.

### Frontend: Vercel

`apps/web/vercel.json` (validated against Vercel's published schema):

- `routes`: `/api/(.*)` → `${CAPACITYOS_API_ORIGIN}/api/$1`, expanded from a
  Vercel environment variable at request time, so no backend hostname is
  committed. If the variable is unset, Vercel leaves the literal
  `${CAPACITYOS_API_ORIGIN}` in place and API calls fail visibly; there is
  no fallback.
- `/api` responses get `Cache-Control: private, no-store` and the documented
  `x-vercel-enable-rewrite-caching: 0` opt-out, so authenticated or
  mutation responses are never CDN-cached. The API itself sends no
  caching headers.
- `rewrites`: `/(.*)` → `/index.html`. Vercel checks real files first, so
  `/assets/*` is served directly and every client route (`/capacity`,
  `/scenarios/:id`, ...) survives a refresh or direct link.
- `buildCommand`: `VITE_API_URL= npm run build`. An **empty**
  `VITE_API_URL` makes the bundle call relative `/api/...` URLs, i.e. the
  same origin. (If it were unset, the bundle would fall back to
  `http://localhost:8000`.) Local `npm run dev` is unaffected.

Vercel project settings: **Root Directory** `apps/web`; framework Vite;
environment variable `CAPACITYOS_API_ORIGIN` = the backend's public origin,
e.g. `https://<service>.onrender.com`, with no trailing slash and no
`/api`. The repo uses npm workspaces with the lockfile at the repo root.

### Backend: Python web service

Verified against the repo: `apps/api/pyproject.toml` requires Python
≥ 3.14, and uv enforces `required-version = "==0.11.25"`, so any other uv
version refuses to run. The app entry point is `app.main:app`, run from
`apps/api`, where `alembic.ini` also lives.

| Setting | Value |
|---|---|
| Root / working directory | `apps/api` |
| Python | 3.14 (e.g. `PYTHON_VERSION=3.14` on Render) |
| Build command | `pip install uv==0.11.25 && uv sync --frozen --no-dev` |
| Start command | `.venv/bin/python -m alembic upgrade head && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/v1/health/ready` (runs `SELECT 1`) |

- `--frozen` installs exactly `uv.lock`; `--no-dev` leaves out pytest,
  ruff and pyright. The start command calls the venv's Python directly, so
  uv isn't needed at runtime.
- Migrations run on every start. `alembic upgrade head` is a no-op when
  already current. That's fine for **one** instance. If the host offers a
  pre-deploy/release command, move the migration there before scaling
  beyond one instance.
- A Dockerfile was deliberately not added. The native commands above were
  verified locally; add one only if a host's native Python runtime proves
  incompatible.

Backend environment variables:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` (enables the startup safety gate and `Secure` cookies) |
| `DATABASE_URL` | `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME` (synchronous psycopg 3; `psycopg[binary]` is a dependency) |
| `API_CORS_ORIGINS` | the Vercel origin, e.g. `https://<project>.vercel.app`. The browser never makes cross-origin calls through the proxy, but the production gate requires an explicit non-wildcard value. |
| `AI_PROVIDER` | `none` (the default; `mock` is refused in production) |

Never put secrets in `apps/web` or in `vercel.json`.

### Database

Any PostgreSQL ≥ 16 (verified on 16.2). Create an empty database; the
start command applies all migrations and creates the "Default
Organization" (slug `default`). To verify compatibility against any
disposable database:

```bash
cd apps/api
DATABASE_URL=postgresql+psycopg://... uv run python -m alembic upgrade head
DATABASE_URL=postgresql+psycopg://... uv run python ../../scripts/seed_demo_data.py --organization-slug default
```

### First Owner and demo data

From an operator machine, with the production `DATABASE_URL` set (no
public demo account exists, and none should be added):

```bash
cd apps/api
uv run python ../../scripts/create_first_owner.py      # prompts; password never echoed
uv run python ../../scripts/seed_demo_data.py --organization-slug default
```

Share the Owner credentials out of band. Additional (e.g. Viewer) accounts
are created in the app under Accounts/Members.

### Demo data

`scripts/seed_demo_data.py` seeds **one named organization** with fictional
data (`@example.com`, every name suffixed "(Demo)"):

- three teams, nine people, five projects (including the unstaffed
  "Project X (Proposed, Demo)");
- 13 allocations, one annual-leave day, and one partial training day;
- three skills, seven person-skills, and three skill requirements.

It is atomic (all or nothing), refuses an unknown or deactivated slug
(exit 2), and is idempotent per organization: if "Product Design (Demo)"
already exists, it writes nothing. `--week-of DATE` anchors the data to
that date's Monday-to-Friday week (default: the current week).

Expected values for that Monday-to-Friday week, derived by hand from
`app/domain/capacity.py` and asserted against the real engine in
`apps/api/tests/scripts/test_seed_demo_data.py`. "Capacity" here is the
engine's **effective capacity**: scheduled hours minus leave/exceptions. The
engine has no separate non-project-work deduction.

| Person | Schedule | Effective | Allocated | Remaining | Utilization |
|---|---|---|---|---|---|
| Alex Morgan | 8h Mon–Fri | 40 | 28 | 12 | 0.7000 |
| Priya Shah | 8h Mon–Fri | 40 | 36 | 4 | 0.9000 |
| **Sam Ade** | 8h Mon–Fri, **Friday leave** | 32 | 40 | **−8 (over by 8)** | **1.2500** |
| Taylor Brooks | 8h Mon–Fri | 40 | 32 | 8 | 0.8000 |
| Morgan Reyes | 8h Mon–Fri | 40 | 36 | 4 | 0.9000 |
| **Casey Kim** | **10h Mon–Thu (4-day week)** | 40 | 12 | **28 (spare)** | 0.3000 |
| Riley Okafor | 8h Mon–Fri | 40 | 40 | 0 | 1.0000 |
| Jamie Novak | 4h Mon–Fri (part-time) | 20 | 16 | 4 | 0.8000 |
| Avery Chen | 6h Mon–Wed, 2h available Wed | 14 | 8 | 6 | 0.5714 |

| Team | Effective | Allocated | Remaining | Utilization |
|---|---|---|---|---|
| Product Design (Demo) | 112 | 104 | 8 | 0.9286 |
| Platform Engineering (Demo) | 120 | 80 | 40 | 0.6667 |
| Content & Motion (Demo) | 74 | 64 | 10 | 0.8649 |

Things worth noticing when evaluating the product:

- **Allocations spread evenly over every day in their range.** Sam's 8h
  Friday booking lands on a leave day, which is how his over-allocation
  shows up.
- **Team totals net out.** Utilization is weighted and over-allocation is
  net, so the Design team shows 0 over-allocation while Sam's own row shows
  8h.
- **Skill bottleneck.** For Project X, Product Design is covered (16h
  needed, 16h qualified spare). Motion Design is not: 30h needed, but only
  4h spare between Riley and Jamie, a 26h gap.
- **Scenario exercise.** Add 16h of Riley on Project X for the week. Riley
  goes to 56h / 40h, utilization 1.4000, and becomes newly over-allocated.
  The scenario's aggregate covers only the people it touches, so here it is
  Riley alone (40h → 56h). Live data is unchanged.

### Local same-origin smoke test

Phase 52 ran the full topology locally:

- the backend with `ENVIRONMENT=production` on PostgreSQL 16;
- the frontend built with the exact `vercel.json` build command;
- a small HTTPS proxy reproducing the `vercel.json` routing (`/api/*` to the
  backend, static files, `index.html` fallback).

27/27 checks passed:

- the frontend and five deep links load through the fallback;
- `/api/v1/health/ready` works through the origin;
- login sets `Secure`, host-only cookies on the frontend origin;
- the seeded capacity values match the table above;
- a mutation without `X-CSRF-Token` returns 403, and with it returns 201;
- logout invalidates the session server-side.

Data survived a backend restart. To repeat it, run the same three pieces
locally; any local reverse proxy can stand in for Vercel.

### Still unverified (needs the real deployment)

- That Vercel's `routes` proxy forwards `Set-Cookie` and the
  `X-CSRF-Token` request header unchanged, and that `/api` responses come
  back uncached (check the `x-vercel-cache` response header).
- That the backend host's native Python 3.14 runtime, and
  `pip install uv==0.11.25`, behave as on the verified local build.
- That the npm-workspaces install works with Root Directory `apps/web`.
- Cold-start and sleep behaviour of free tiers, and managed-PostgreSQL
  limits. Check the current platform documentation before choosing.
- Real-browser behaviour. Nothing has been exercised in a browser yet;
  that is Phase 53's acceptance checklist.

## Security boundaries

- **AI**: server-side only, the API key never reaches `apps/web`, AI
  output cannot mutate any record (structurally — no schema field or
  service path exists for it to do so), and every source reference is
  grounded against an explicit allow-list before reaching the client (ADR
  0008).
- **Imports**: two-stage validate-then-apply (nothing is written until an
  explicit apply call re-validates the identical file), CSV
  formula-injection sanitization on export, file-size and row-count caps
  enforced before parsing.
- **Request size**: every request body is capped at
  `MAX_REQUEST_BODY_BYTES` (5 MiB by default), checked via `Content-Length`
  before any body is read.
- **Free-text fields**: every writable `description`/`notes` field has an
  explicit `max_length`.
- **Errors**: no raw stack trace, SQL error, or provider-internal message
  ever reaches a client response — the catch-all and database-error
  handlers log full detail server-side and return a fixed, generic message.
- **CORS**: explicit allowlist via `API_CORS_ORIGINS`; a wildcard is
  refused outright in `production`.
- **Authentication (Phase 10)**: httpOnly, Secure-in-production session
  cookies; passwords hashed with Argon2id; per-account lockout after 5
  failed attempts (15 minutes); login failure responses are identical
  regardless of whether the email exists, the password is wrong, or the
  account is locked (enumeration resistance). See
  [docs/adr/0010-authentication-rbac-audit.md](adr/0010-authentication-rbac-audit.md).
- **Authorization (Phase 10)**: every route requires an authenticated
  session; every mutating route additionally requires a specific
  permission via one centralized `require_permission` dependency — never a
  scattered `if user.role == ...` check. 401 (no/invalid session) is
  always distinguished from 403 (authenticated, insufficient role).
- **CSRF (Phase 10)**: double-submit token (`X-CSRF-Token` header, checked
  against a non-httpOnly cookie) required on every mutating route, as
  defense-in-depth alongside SameSite=Lax and the CORS allowlist.
- **Audit (Phase 10)**: every mutation, login event, and permission denial
  is recorded to an append-only `audit_events` table (`GET /api/v1/audit`,
  Admin/Owner only) — never a raw request body, uploaded file, AI prompt,
  password, or token.

## Operational troubleshooting

**"The app won't start and logs `ProductionConfigError`."** Read the
logged `problem` field(s) — each names exactly what's unsafe (SQLite URL,
mock AI provider, or CORS) and why. Fix the named setting, or unset
`ENVIRONMENT` (defaults to `development`, which skips this check) if this
really is a development/staging deployment.

**"Readiness returns 503."** The database is unreachable. Check
`DATABASE_URL` and that the database process/file is actually reachable
from where the API is running; liveness (`/api/v1/health`) will still
return 200 in this state — the process itself is fine, only its database
dependency is down.

**"AI panels show 'AI is not configured for this deployment.'"** Expected,
first-class state when `AI_PROVIDER=none` (the default) or `AI_PROVIDER=
anthropic` with no `ANTHROPIC_API_KEY` set. Every deterministic feature is
unaffected. Check `GET /api/v1/ai/status` for the current provider/model.

**"I need to find every log line for one failing request."** Grep the
structured logs for that request's `request_id` — obtainable from the
`X-Request-ID` response header the client received.

## Production readiness checklist

### Application
- [x] backend starts cleanly
- [x] frontend builds
- [x] health endpoint works
- [x] readiness endpoint works
- [x] configuration validation works
- [x] structured logging works
- [x] request IDs work
- [x] errors follow a consistent contract

### Security
- [x] secrets are not exposed to frontend
- [x] sensitive data is not logged
- [x] imports remain protected
- [x] AI remains server-side
- [x] AI cannot mutate data
- [x] CORS is explicit
- [x] error responses do not leak internals

### Database
- [x] migrations work from clean state
- [x] migrations work from current state
- [x] no unintended schema drift
- [x] production database expectations documented

### CI
- [x] API CI passes
- [x] frontend CI passes
- [x] uv installation succeeds
- [x] tests pass
- [x] type checks pass
- [x] linting passes
- [x] production build passes

### Existing product
- [x] Capacity works
- [x] Scenarios work
- [x] Insights work
- [x] Skills work
- [x] Import/export works
- [x] AI-disabled mode works
- [x] AI mock mode works

### Authentication, authorization & audit (Phase 10)
- [x] login/logout works
- [x] session expiry works
- [x] account lockout works
- [x] RBAC enforced on every mutating route
- [x] 401 vs 403 correctly distinguished
- [x] CSRF protection works
- [x] audit events recorded for mutations, logins, and permission denials
- [x] audit log never contains secrets or file content
- [x] first-Owner bootstrap script works
- [x] last-Owner protections work (cannot demote/disable)
