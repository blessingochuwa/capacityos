# scripts

Deterministic operational utilities: seed generation, imports/exports, maintenance, development utilities (CLAUDE.md §6).

Reusable business logic must not live only here — extract it into `apps/api/app/domain` or `apps/api/app/services` and have scripts call into that, not the other way around.

Every script here is type-checked by strict pyright (`apps/api/pyproject.toml` includes `../../scripts`). Run them from `apps/api`, so `DATABASE_URL` and `.env` resolve exactly as they do for the API.

- `seed_demo_data.py`: fictional DEMO DATA for **one named organization**, for local development or a prototype deployment's demo organization. Never run it against an organization that holds real data.

  ```bash
  uv run python ../../scripts/seed_demo_data.py --organization-slug default [--week-of YYYY-MM-DD]
  ```

  - `--organization-slug` is required. The slug `default` is the organization the migrations create.
  - `--week-of` is optional. Any date works; the data is anchored to that date's Monday-to-Friday week. The default is the current week.
  - **Idempotent:** if the organization already has the "Product Design (Demo)" team, the script writes nothing and exits 0.
  - **Atomic:** everything goes through the service layer in one transaction. Any error rolls the whole seed back and exits 1.
  - **Bad target:** an unknown or deactivated slug exits 2 and writes nothing.

  The dataset and its expected capacity values are documented in [docs/production-readiness.md](../docs/production-readiness.md#demo-data) and asserted by `apps/api/tests/scripts/test_seed_demo_data.py`.
- `create_first_owner.py` — operator-run, one-time bootstrap of the first Owner account (Phase 10). Refuses to run if an Owner already exists; every subsequent user is created via `POST /api/v1/users`. See [docs/adr/0010-authentication-rbac-audit.md](../docs/adr/0010-authentication-rbac-audit.md).
- `export_openapi_schema.py` — regenerates `docs/openapi.json` from the live route/schema definitions (no server needs to be running). Run after any route change so the checked-in schema doesn't drift.
