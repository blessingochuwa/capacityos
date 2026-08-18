# scripts

Deterministic operational utilities: seed generation, imports/exports, maintenance, development utilities (CLAUDE.md §6).

Reusable business logic must not live only here — extract it into `apps/api/app/domain` or `apps/api/app/services` and have scripts call into that, not the other way around.

- `seed_demo_data.py` — reproducible DEMO DATA for local development (Phase 3). Never run against production.
- `create_first_owner.py` — operator-run, one-time bootstrap of the first Owner account (Phase 10). Refuses to run if an Owner already exists; every subsequent user is created via `POST /api/v1/users`. See [docs/adr/0010-authentication-rbac-audit.md](../docs/adr/0010-authentication-rbac-audit.md).
