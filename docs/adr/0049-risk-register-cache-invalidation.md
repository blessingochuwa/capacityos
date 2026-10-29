# ADR 0049: Phase 49 — Risk Register cache invalidation after risk mutations

- **Status:** Accepted
- **Date:** 2026-10-29

## Context

ADR 0048 listed a known limitation: on `/risks`, editing a risk could
leave the org-wide Risk Register (Phase 47) showing stale data. Phase 49
confirms the cause from source and fixes it with the smallest correct
change.

### Repository state at the start

`HEAD` was `7265ec1` (Phase 48), identical to `origin/main`. The working
tree was **not** clean. It held uncommitted output from a repository-wide
bug check run after Phase 48. That output included a change to
`useRiskMutations.ts` aimed at this exact defect, plus two unrelated
fixes (duplicate select ids on `/stakeholders`, and Audit Log ordering).
The two unrelated fixes are recorded in ADR 0048's follow-up section. All
of it was preserved, so this phase confirmed the defect against **`HEAD`
source**, not the working tree.

## The defect

### Data flow (from source)

| Piece | Query key / behavior |
|---|---|
| Org-wide register (`useOrgRisks`) | `['org-risks', filters]`. `filters` holds `project_id`, `status`, `exposure`, `offset`, so every filter combination and page is its own cache entry. |
| Per-project table (`useRisks`) | `['projects', projectId, 'risks']`, a separate query |
| Create | `RiskForm` → `useCreateRisk` |
| Status edit | `RisksOverviewPage` → `useUpdateRisk` |
| Delete | `RisksOverviewPage` → `useDeleteRisk` |
| QueryClient defaults (`lib/queryClient.ts`) | `staleTime: 30_000` |

### Root cause

At `HEAD`, all three mutation hooks invalidated **only**
`['projects', projectId, 'risks']`. Nothing invalidated any
`['org-risks', …]` entry. Both registers render on the same page, so the
org-wide register stays mounted while the user edits in the per-project
table. Its cached entry was neither marked invalid nor refetched, so it
kept showing the pre-edit rows (old status, deleted risks still listed,
new risks missing). That lasted as long as the page stayed open. Once the
30-second `staleTime` passed, a refetch still needed a separate trigger
such as window focus or a remount. Create and delete had the same gap as
edit.

## Decision

All three mutations call one shared helper, `invalidateRiskQueries`,
from `onSuccess`:

```ts
void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'risks'] })
void queryClient.invalidateQueries({ queryKey: ['org-risks'] })
```

- **Prefix match.** React Query matches `['org-risks']` against every
  `['org-risks', filters]` entry. Every filtered and paginated variant is
  invalidated. The mounted one refetches immediately, and the rest
  refetch when next viewed. Filter and page state live in component
  state and are untouched.
- **Success only.** No optimistic updates are used. A failed mutation
  changed nothing on the server, so it triggers no refetch, and its error
  surfaces exactly as before.
- **Scope.** Only the risk register and the edited project's own list.
  Other projects' risk lists, stakeholder queries, and every other
  feature's queries are left alone. (Insights and the Risk-vs-Value
  quadrant were not changed by this phase. The quadrant already shares
  the `['projects', id, 'risks']` key.)
- **Multi-tenancy.** The `['org-risks']` prefix cannot reach another
  organization's data. An organization switch already removes every
  non-session query (`AuthContext.tsx`), so the cache only ever holds the
  active organization's entries. The server scopes every request to the
  session's organization regardless. No organization id was added to any
  key.
- **No new abstraction.** No cache layer, duplicated state, or one-off
  page-level refresh logic was added. This is the same shape
  `useStakeholderMutations` adopted in Phase 48.

## Verification

The tests live in the existing
`apps/web/src/features/risks/hooks/useRiskMutations.test.tsx`. That file
was created, uncommitted, by the post-Phase-48 check, and Phase 49
rewrote it. Its earlier version only spied on `invalidateQueries`. The
tests now assert on query cache state and on what the mounted register
renders, using production's 30-second `staleTime`:

1. **Observable refresh.** A mounted `useOrgRisks` shows `open`. After a
   successful edit it refetches and shows `closed` (2 fetches).
2. **Create, update, and delete** (3 tests). Each one marks three
   seeded register variants as invalidated (unfiltered page 1, a
   status-filtered page 2, and a project + exposure filtered page),
   along with `['projects','p1','risks']`. It leaves
   `['projects','p2','risks']`, `['org-stakeholders', …]`, and
   `['projects','p1','stakeholders']` alone.
3. **Failed edit.** The update rejects. Nothing is invalidated, the
   register is not refetched, it still shows `open`, and the mutation
   reports `isError`.

**Each test was run against both versions of `useRiskMutations.ts`.**
With `HEAD`'s file swapped in, tests 1 and 2 (4 tests) fail and test 3
passes. Test 3 guards behavior that was already correct. With the fix,
all 5 pass. (The first rewrite had two test bugs, which were fixed
before these results. One test read seeded placeholder data instead of
fetching. Queued once-only mock values leaked between tests;
`vi.resetAllMocks()` now drains them.)

| Gate | Result |
|---|---|
| Focused: `src/features/risks` | 34 passed |
| Full frontend suite | **492 passed** (87 files) |
| `tsc -b --noEmit` | exit 0 |
| `oxlint` | exit 0 (2 pre-existing warnings in the untouched `AuthContext.tsx`) |
| `vite build` | exit 0 |
| Prettier (the two Phase 49 files) | clean |
| Backend | not re-run. No backend file is touched by this phase. |
| Live / browser | **Not performed.** No browser automation tool was available. The refresh is demonstrated at the hook level with a real `QueryClient`, not in a rendered page. |

Test totals: the full suite was 483 at `HEAD`, and 490 in the working
tree at the start of this phase. Of those 490, the post-Phase-48 check
contributed 3 risk-hook, 3 stakeholder-hook, and 1 stakeholder-page
test. After this phase the suite is 492. The risk-hook file went from 3
spy-based tests to 5 behavioral tests (+2 net).

## Consequences

- No backend, API, OpenAPI, permission, schema, or migration change.
  `docs/openapi.json` was not regenerated.
- One production file changed: `useRiskMutations.ts`.

### Known limitations

- `['org-risks']` invalidation also marks register pages the user is not
  currently viewing as stale. They refetch on next view. That is the
  intended behavior, and it costs at most one extra request per revisited
  page.
- Rows can still shift between `OFFSET` pages after a concurrent change by
  *another* user, because invalidation is per browser. This was already
  accepted in ADR 0047.
- No page-level or browser test renders `RisksOverviewPage` with a real
  `QueryClient`. The page tests mock the hooks, so the integration is
  proven at the hook level only.
