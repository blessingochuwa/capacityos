# tests

Cross-application and end-to-end tests (CLAUDE.md §6). Application-specific unit tests live near the code they test: `apps/web/src/**/*.test.tsx` (Vitest) and `apps/api/tests/` (pytest).

No end-to-end suite exists yet. Playwright is the intended tool per CLAUDE.md §7, introduced when there is a UI flow worth testing end-to-end — not before.
