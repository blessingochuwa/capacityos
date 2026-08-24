# Contributing to CapacityOS

Thanks for your interest in contributing. This repository is governed by [CLAUDE.md](./CLAUDE.md) — read it before making architectural or domain-model decisions. When in doubt, CLAUDE.md's operating philosophy and scope discipline take precedence over convenience.

Before picking up work, check [docs/roadmap.md](./docs/roadmap.md) for what's already built (Phases 0–16, each with an ADR) and what's proposed next — it's the fastest way to see whether something you want to build is already done, already decided against (and why), or genuinely open.

## Setup

1. Install [Node.js](https://nodejs.org/) 24+ and [uv](https://docs.astral.sh/uv/).
2. From the repo root: `npm install` (installs `apps/web` and `packages/contracts`).
3. From `apps/api`: `uv sync` (creates the virtual environment and installs backend dependencies).
4. Copy `.env.example` to `.env` and adjust as needed.

## Coding standards

- **Frontend**: TypeScript strict mode, no `any`. Lint with ESLint (`npm run lint --workspace apps/web`), format with Prettier.
- **Backend**: Ruff for linting and formatting (`uv run ruff check .` / `uv run ruff format .`), mypy for static typing (`uv run mypy .`).
- Business-critical capacity calculations must be deterministic and independently testable — see CLAUDE.md §4 and §10. Do not put domain logic in API route handlers, database models, or React components.
- Do not add functionality beyond the current development phase (CLAUDE.md §39, §32). Do not create fake or mocked functionality without clearly labeling it (CLAUDE.md §26).

## Testing

- Frontend: Vitest + React Testing Library (`npm run test --workspace apps/web`).
- Backend: pytest (`uv run pytest` from `apps/api`).
- Test edge cases, not only the happy path — see CLAUDE.md §30 for the minimum required scenarios for domain logic (part-time schedules, leave, holidays, over-allocation, timezone boundaries, etc.).

## Commits and branches

- Use short, descriptive branch names (e.g. `feature/allocation-model`, `fix/utilization-rounding`).
- Write commit messages that explain *why*, not just *what*.
- Keep commits scoped to a single logical change.

## Pull requests

- Describe what changed and why, and link any relevant CLAUDE.md sections or ADRs.
- Ensure lint, typecheck, and tests pass before requesting review.
- Security-sensitive changes require additional review (CLAUDE.md §27).

## Adding dependencies

Before adding a significant dependency, evaluate necessity, maintenance status, license, security, compatibility, and bundle/runtime impact (CLAUDE.md §34). Prefer mature open-source dependencies already aligned with the technology direction in CLAUDE.md §7.
