# ADR 0001: Phase 0 repository and architecture bootstrap

- **Status:** Accepted
- **Date:** 2026-08-10

## Context

CLAUDE.md defines CapacityOS's governing product, architecture, and technology direction but the repository contained only that file. Phase 0 (CLAUDE.md §39) calls for bootstrapping the monorepo skeleton before any product feature work begins. Several implementation choices were not pinned down by CLAUDE.md and needed a decision.

## Decisions

**License: MIT.** CapacityOS is described as "open-source-first" (CLAUDE.md §1). MIT is the most permissive, lowest-friction option for a portfolio-grade open-source dev tool, and was the explicit choice made when bootstrapping.

**JS/TS package manager: npm workspaces.** Node 24 / npm 11 were already available in the target environment; pnpm and yarn were not installed. npm workspaces are sufficient for the current two-package JS surface (`apps/web`, `packages/contracts`) without adding a new global tool.

**Python tooling: uv, not pip/poetry/pipenv.** No system Python was installed; `uv` was already present and can provision the Python interpreter itself (3.14.6), plus manage the virtual environment, dependency resolution, and lockfile in one tool. This directly satisfies CLAUDE.md §7's Python/FastAPI direction without adding extra tooling surface.

**Backend static type checking: pyright, not mypy.** CLAUDE.md §7 calls for "appropriate static/type checking" without naming a specific tool. mypy was tried first but its compiled (mypyc) DLL was blocked by a Windows Application Control policy in the bootstrap environment. Pyright (a mature, actively maintained, widely-used alternative with first-class FastAPI/Pydantic support) was substituted; strict mode is enabled for `app/`, with a relaxed execution environment for `tests/` where third-party test-client (`httpx`/`starlette`) typing is incomplete.

**Frontend linting: oxlint (from the official Vite scaffold), not ESLint.** The current `npm create vite` React+TS template ships oxlint by default — a fast, actively maintained linter. Per CLAUDE.md §34 (prefer minimal, justified dependencies), the scaffold default was kept rather than layering ESLint on top for the same job. Prettier was added separately for formatting, since oxlint is lint-only.

**Frontend styling: Tailwind CSS v4** via `@tailwindcss/vite`, per CLAUDE.md §7's named technology direction.

**Frontend testing: Vitest + React Testing Library.** Vite-native, minimal setup, avoids a second bundler/config for tests.

**End-to-end testing (Playwright): deferred.** CLAUDE.md §7 names Playwright as the eventual e2e tool "when needed" — there is no UI flow yet to test end-to-end, so `tests/` is a placeholder only.

**Backend health check.** A single thin `GET /api/v1/health` route was added as the only route — pure infrastructure verification, not a product feature, and consistent with CLAUDE.md §26 (no fake functionality) since it does exactly what it claims and nothing more.

**No domain models yet.** SQLAlchemy/Alembic are wired (engine, session, migration environment) but `app/models` is empty and no migrations exist. Person/Team/Project/Allocation/Availability/WorkingSchedule are explicitly Phase 1 (CLAUDE.md §9, §39).

**Git.** The repository was initialized at the root only. `uv init` initially created a nested `.git` inside `apps/api`; it was removed to avoid a nested-repository/submodule situation — there is exactly one git repository, rooted at the project root.

## Consequences

- Contributors need Node 24+/npm 11+ and `uv` (which manages Python itself — no separate Python install required).
- Type-checking commands in docs/CI reference `pyright`, not `mypy`; if a future environment doesn't hit the same Application Control restriction, switching back to mypy is a config-only change (swap the dev dependency and `[tool.mypy]`/`[tool.pyright]` section).
- `packages/contracts` remains an empty placeholder package until Phase 1 domain types exist to share.
