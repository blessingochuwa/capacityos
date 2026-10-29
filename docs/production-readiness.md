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

Status, as of Phase 52 (amended in Phases 53A.1 and 53A.2): **ready for
deployment, not deployed.** Everything
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
| Python | 3.14, fully qualified: `PYTHON_VERSION=3.14.8` on Render |
| Build command | `pip install uv==0.11.25 && uv sync --frozen --no-dev` |
| Start command | `.venv/bin/python -m alembic upgrade head && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/api/v1/health` (liveness only, no database query) |

- Render requires `PYTHON_VERSION` to be a fully qualified version: `3.14`
  alone is not accepted. 3.14.8 is Render's default for services created
  from 2026-10-12 (render.com/docs/python-version, checked 2026-10-29). It
  is a patch release of the 3.14 line the repo requires; the local suite
  runs on 3.14.6. Render's documentation describes a `.python-version`
  file at the repository root and says nothing about how that interacts
  with a service Root Directory such as `apps/api`, where this repo's
  file is. That interaction hasn't been verified, so set `PYTHON_VERSION`
  explicitly. It takes precedence over `.python-version` either way.
- Use `/api/v1/health` for the host's health check. It returns
  `{"status": "ok"}` without touching the database. `/api/v1/health/ready`
  runs `SELECT 1` on PostgreSQL, so pointing a periodic probe at it would
  keep a scale-to-zero database awake. Use `/ready` by hand, through the
  frontend origin, to check that the database is reachable.

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
| `DATABASE_URL` | `postgresql+psycopg://<DB_USER>:<DB_PASSWORD>@<DB_HOST>/<DB_NAME>?sslmode=require&channel_binding=require` (synchronous psycopg 3; `psycopg[binary]` is a dependency). See "Database" for the Neon details. |
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

#### Neon connection string (Phase 53A.2)

```text
postgresql+psycopg://<DB_USER>:<DB_PASSWORD>@<DB_HOST>/<DB_NAME>?sslmode=require&channel_binding=require
```

- **Scheme `postgresql+psycopg://`, not the `postgresql://` that Neon
  shows.** It selects SQLAlchemy's psycopg 3 dialect, which this app
  depends on. A plain `postgresql://` URL would select psycopg2, which
  isn't installed. Change only the scheme; keep the rest of Neon's string.
- **TLS parameters.** SQLAlchemy passes the URL's query parameters to
  psycopg, and psycopg passes them to libpq. Checked against the locked
  versions (SQLAlchemy 2.0.51, psycopg 3.3.6 binary, bundled libpq 18):
  `sslmode=require` and `channel_binding=require` both reach libpq's own
  option parser and are accepted, while an unknown option is rejected.
  Neon refuses unencrypted connections in any case. Neon recommends the
  stricter `sslmode=verify-full`; that needs a root-certificate setting
  this runbook hasn't verified, so it isn't used here.
- **Use the direct (unpooled) connection string**: the host without
  `-pooler`, with **Connection pooling** turned off in Neon's Connect
  dialog. Migrations and `pg_dump` need a direct connection, and the API
  already pools connections itself.
- **Postgres major version: choose 16** when creating the Neon project.
  The migrations, seed, backup and restore have only been verified on
  16.2. Neon also offers 14, 15, 17 and 18, which are untested here.
- **Special characters in the password** (`@ : / ? # %`) must be
  percent-encoded in the URL; for example `@` becomes `%40`. SQLAlchemy
  decodes them (checked).
- The placeholders `<DB_USER>`, `<DB_PASSWORD>`, `<DB_HOST>` and
  `<DB_NAME>` stand for the values in Neon's dashboard. Enter the real
  value only in Render's environment settings or in a local shell (see
  below). Never put it in a file in this repository, a ticket or a chat.

### Free-tier operation and stop conditions (Phase 53A.1, 53A.2)

The prototype targets Vercel Hobby, Render Free and Neon Free. The
expected infrastructure cost is **$0 per month: a target, not a
guarantee**. It holds only while no payment method is on file and usage
stays within each free quota.

Stop conditions. If any of these can't be met without a card or a
payment, the deployment is **NO-GO** until a new decision is made:

- **Stop if a provider asks for a payment card**, payment details, a paid
  trial or an upgrade. Don't sign up just to find out whether one is
  required.
- **Don't enable billing, buy a domain, or accept a paid add-on.** Use the
  provider-supplied `*.vercel.app` and `*.onrender.com` URLs.
- **Set `CAPACITYOS_API_ORIGIN` for the Production environment only.** A
  Preview deployment then has no `/api` target, so it can't reach the
  production backend or database. Never give a Preview deployment the
  production backend origin or `DATABASE_URL`.
- **Health check:** `/api/v1/health` (liveness, no database query) for the
  platform. Use `/api/v1/health/ready` only for manual database checks.
- **Zero cost is not permanent.** Provider terms, quotas and free plans
  change. Re-check each provider's free-plan page before Phase 53B and
  whenever a provider announces changes.

- **Do not add a keep-warm pinger.** Render Free sleeps after 15 idle
  minutes and takes about a minute to wake. Neon Free suspends after 5
  idle minutes. Scaling to zero is what keeps both inside their free
  quotas. A pinger, especially one hitting `/api/v1/health/ready`, would
  spend those quotas.
- **The backend can be up while the database is still asleep.** The first
  database request after an idle period waits for Neon to wake. If the
  wake-up or the network fails, it returns 503 ("The database is
  temporarily unavailable"). Retry once.
- **Stale connections.** Neon drops every open connection when it
  suspends. The engine is created with `pool_pre_ping=True`
  (`apps/api/app/core/database.py`): each pooled connection is checked
  before use, and a dead one is replaced, so a request no longer fails just
  because the pool held a dropped connection. This was verified against
  local PostgreSQL 16 by terminating the backend connection. It does not
  remove cold starts, retry a query that fails mid-request, or prevent
  other transient network errors. Re-check it on Neon after deployment:
  sign in, wait more than 5 minutes, then load a data page. It should
  succeed with no 503.

### First Owner and demo data

From an operator machine, with the production `DATABASE_URL` set (no
public demo account exists, and none should be added). Enter the URL
without echoing it and without saving it to shell history (bash), and
clear it afterwards:

```bash
cd apps/api
IFS= read -rs DATABASE_URL && export DATABASE_URL   # paste the URL, press Enter
uv run python ../../scripts/create_first_owner.py      # prompts; password never echoed
uv run python ../../scripts/seed_demo_data.py --organization-slug default
unset DATABASE_URL
```

Share the Owner credentials out of band. Additional (e.g. Viewer) accounts
are created in the app under Accounts/Members.

### Backups (Phase 53A.2)

Neon Free's 6-hour restore window and single manual snapshot are not a
backup. Take a full `pg_dump` from your own computer **after the first
seed, and then weekly**. It needs no paid feature.

**This is not the app's export feature.** `GET /api/v1/exports/{type}`
(Import/Export page) exports CSV or JSON for one entity type at a time, in
one organization: people, teams, team memberships, projects, allocations,
working schedules, availability exceptions, skills, person skills, skill
requirements, risks, stakeholders, priority scores and dependencies. It
leaves out user accounts, memberships, sessions, the audit log, scenarios,
prioritization frameworks and snapshots. It is useful for moving data, not
for recovering the database. Only `pg_dump` captures everything.

**Requirements.** PostgreSQL client tools (`pg_dump`, `pg_restore`) whose
major version is the same as the Neon project's (16) or newer, installed on
your computer. On Windows, the PostgreSQL installer can install only the
"Command Line Tools". Run the commands in bash (Git Bash on Windows).

**Procedure.** Copy the four non-secret values from Neon's Connect dialog,
using the direct, unpooled host. Type the password when prompted: it isn't
echoed, isn't saved to shell history, and never appears on a command line.

```bash
BACKUP_DIR="$HOME/capacityos-backups"          # outside the repository
mkdir -p "$BACKUP_DIR" && chmod 700 "$BACKUP_DIR"   # restricts access on Linux/macOS only (see Limitations)

export PGHOST='<DB_HOST>' PGDATABASE='<DB_NAME>' PGUSER='<DB_USER>'
export PGSSLMODE=require PGCHANNELBINDING=require
IFS= read -rs -p 'Neon password: ' PGPASSWORD && export PGPASSWORD && echo

FILE="$BACKUP_DIR/capacityos-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump --format=custom --no-owner --no-privileges --file="$FILE"
DUMP_EXIT=$?                                   # capture immediately, before any other command
unset PGPASSWORD
echo "pg_dump exit code: $DUMP_EXIT"
```

`pg_dump` takes the connection from these standard libpq environment
variables. It doesn't use `DATABASE_URL`, whose `postgresql+psycopg://`
scheme only SQLAlchemy understands.

**Confirm the dump.** All three must hold:

```bash
test "$DUMP_EXIT" -eq 0 && echo "pg_dump succeeded" # the code captured right after pg_dump
test -s "$FILE" && ls -l "$FILE"                # file exists and is non-empty
pg_restore --list "$FILE" | grep -c "TABLE DATA" # archive is readable; lists the tables
```

Run these in the same shell session as the procedure, so `$DUMP_EXIT` and
`$FILE` still hold their values. A bare `echo $?` at this point would only
report the most recent command, not `pg_dump`.

`pg_restore --list` only reads the file and connects to no database.

**Verified locally** (PostgreSQL 16.2, Phase 53A.2, without TLS):
- dumped a freshly migrated and seeded database with these exact commands
  (exit 0, a 112,755-byte archive, 30 table-data entries);
- restored it into a separate empty local database with
  `pg_restore --no-owner --no-privileges --exit-on-error --dbname=<empty local db> "$FILE"`
  (exit 0);
- row counts (people, allocations, teams) and the Alembic revision matched
  the source.

Not yet verified against Neon itself: TLS, channel binding, and a dump of
the hosted database. **No restore into Neon has been tested.**

**Limitations.**
- A backup only counts once a restore has worked. After the first real
  dump, restore it into a local scratch database (never into Neon) to
  prove it.
- A dump holds every account's password hash, every session token hash,
  and all organization data. Keep `$BACKUP_DIR` private: outside the
  repository, out of synced or shared folders unless they're encrypted, and
  on an encrypted disk.
- **On Windows, `chmod 700` is not an access control.** In Git Bash on
  NTFS it doesn't reliably restrict who can read the folder. Instead:
  - Keep the folder outside any OneDrive-synced location. This
    repository is itself under OneDrive, so check that `$HOME` is not
    synced.
  - Keep it under your own Windows user profile, on a drive encrypted
    with BitLocker or device encryption.
  - Where other accounts use the same computer, restrict it with Windows
    permissions. For example, from Command Prompt:
    `icacls "%USERPROFILE%\capacityos-backups" /inheritance:r /grant:r "%USERNAME%:(OI)(CI)F"`
    removes inherited access and grants only your account.
- A dump is a point in time. Anything written after it is lost if you have
  to restore. Delete old dumps you no longer need.
- The dump transfers data out of Neon, which counts toward Free's 5 GB a
  month. The demo database is about 0.1 MB, so this is negligible.

### Public backend exposure (Phase 53A.2)

The browser only talks to the Vercel origin, but **the Render service's
own `https://<service>.onrender.com` URL is public**. Anyone who finds it
can call the API directly, bypassing Vercel. Not linking to it is not a
protection. Everything reachable there:

- every `/api/v1/*` route, including `POST /api/v1/auth/login`;
- `GET /api/v1/health` and `GET /api/v1/health/ready`;
- FastAPI's default `/docs`, `/redoc` and `/openapi.json`, which aren't
  disabled in `app/main.py`. They show the API's shape, which is already
  public in this repository, but no data.

What the application itself enforces on direct calls:

- **Authentication:** of the 144 API routes, 140 need a valid server-side
  session (enumerated from the app's routers in Phase 53A.2). The other
  four are `GET /health`, `GET /health/ready`, `POST /auth/login` and
  `POST /auth/logout`. Logout only invalidates the session whose cookie is
  sent with it. The docs pages also need no session.
- **Authorization:** role-based permissions on every route.
- **Organization isolation:** another organization's data is
  indistinguishable from data that doesn't exist (404).
- **CSRF:** every route that changes data requires `X-CSRF-Token`. Nine
  authenticated `POST` routes deliberately don't, because they write
  nothing: scenario `calculate`, import `validate`, and the seven
  `/api/v1/ai/*` routes. The AI routes are inert here because
  `AI_PROVIDER=none`.
- **Cookies:** session cookies are host-only to the Vercel domain, so a
  browser never sends them to the Render URL.
- **Passwords:** Argon2id hashing, with a generic, timing-equalized login
  failure response (no account enumeration).
- **Lockout:** an account locks for 15 minutes after 5 failed logins
  (ADR 0010).
- **Request size, partial:** `MaxBodySizeMiddleware` rejects a request
  whose declared `Content-Length` header exceeds 5 MiB, before reading
  the body. It checks only that declared header. A request sent without
  one (for example, chunked) bypasses this check. Its own docstring says
  it is not a hardened denial-of-service defence, and it shouldn't be
  relied on as one.
- **Errors:** a generic 500 message, with no stack traces.

Remaining risks for a private prototype, none mitigated in code yet:

- **There is no IP-based rate limiting.** ADR 0010 already records this as
  a known limitation.
- **Lockout as a denial of service:** anyone who knows or guesses the
  Owner's email can lock that account for 15 minutes at a time. Use an
  Owner email that isn't public, and a long, unique password.
- **CPU exhaustion:** every login attempt runs a full Argon2 verification,
  even for unknown emails. On Render Free's 0.1 CPU, a flood of attempts
  could make the API unresponsive.
- **Free quotas:** direct traffic wakes Render and Neon and spends their
  free hours. When a quota runs out the service suspends (no charge), but
  it is unavailable until the next month.
- **Possible hardening, needing separate approval:** Vercel adds a
  shared-secret header to proxied requests and the backend rejects
  requests without it; and/or disable `/docs`, `/redoc` and
  `/openapi.json` in production. Neither is implemented. Both are code
  changes for a separate, approved phase.

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
- Cold-start and sleep behaviour on the real free tiers, including what
  Vercel's proxy receives while Render is waking up, and stale-connection
  recovery against Neon (see "Free-tier operation and stop conditions").
- That the Neon TLS parameters (`sslmode=require&channel_binding=require`)
  connect, and that the backup procedure works against Neon. Both were
  checked only locally.
- Whether any provider asks for a payment card at signup. Stop if one does.
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
- **Request size (partial)**: `MaxBodySizeMiddleware` rejects a request
  whose declared `Content-Length` exceeds `MAX_REQUEST_BODY_BYTES` (5 MiB
  by default) before any body is read. A request without that header is
  not covered by this check (see "Public backend exposure").
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
