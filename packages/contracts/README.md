# @capacityos/contracts

Shared TypeScript types/contracts used across `apps/web` and (where relevant) generated from `apps/api`'s schemas.

This package is intentionally empty in Phase 0 — no source files, just this README and a `package.json` so the workspace recognizes it. Per [CLAUDE.md](../../CLAUDE.md) §6, shared contracts belong here "only where genuinely useful across applications," and there is no domain data to share until Phase 1 introduces the People/Teams/Projects/Allocations models.

**Decision (see [ADR 0001](../../docs/adr/0001-phase-0-bootstrap.md)):** kept as an empty placeholder rather than omitted, because CLAUDE.md §5 explicitly names `packages/contracts` in the initial target architecture. Once Phase 1 models exist, revisit whether hand-written shared types here are worth the duplication risk versus generating TypeScript types from the FastAPI/Pydantic OpenAPI schema — the latter is often the better source of truth and would make this package thin (generated output + re-exports) rather than hand-maintained. Do not duplicate business logic here either way — this package holds types/contracts only.
