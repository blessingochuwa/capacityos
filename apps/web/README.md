# @capacityos/web

React + TypeScript + Vite + Tailwind CSS frontend for CapacityOS. See the [repository root README](../../README.md) for setup and the [project CLAUDE.md](../../CLAUDE.md) for architectural rules.

## Scripts

- `npm run dev` — start the Vite dev server
- `npm run build` — type-check and build for production
- `npm run typecheck` — type-check only
- `npm run lint` — lint with oxlint
- `npm run format` / `npm run format:write` — check/apply Prettier formatting
- `npm run test` — run the Vitest suite
- `npm run storybook` — start the Storybook dev server (port 6006) for `src/components/ui/*.stories.tsx`
- `npm run build-storybook` — static Storybook build (`storybook-static/`), for CI/deploy or a shareable component reference

## Storybook

`.storybook/main.ts`/`preview.tsx` mirror `vite.config.ts`'s own plugins (Tailwind v4, the `@` → `src` alias) so a component looks identical in Storybook and in the real app. Stories live next to the component they document (`Component.stories.tsx`), starting with the `components/ui/` design-system primitives (`Button`, `Badge`, `EmptyState`, `ErrorState`, `MetricTile`) — add a story alongside any new reusable component rather than only the feature that first needed it.

**Known environment limitation**: Storybook (both `dev` and `build`) depends on `oxc-resolver`, a native (napi-rs) module with no pure-JS/WASM fallback in this version. On a machine with an Application Control / WDAC-style policy that blocks unsigned native binaries from `node_modules`, both commands fail at startup with `Cannot find native binding` — this is unrelated to the project's own code (confirmed: `tsc`, `oxlint`, and `vitest` all pass cleanly against `.storybook/` and every `*.stories.tsx` file). If you hit this, it's a local machine policy, not a Storybook/CapacityOS config bug — try a machine/CI runner without that restriction, or an allow-list entry for `node_modules/@oxc-resolver/**/*.node`.
