import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  scenariosApi,
  type ScenarioCreateInput,
  type ScenarioUpdateInput,
} from '../api/scenariosApi'

/** Scenario CRUD mutations. Every mutation here touches ONLY the scenario
 * itself (or, via cascade, its own operations) — never Person/Project/
 * Allocation/AvailabilityException/WorkingSchedule (CLAUDE.md §19, prompt §29).
 *
 * Invalidation is scoped narrowly on purpose. react-query's `invalidateQueries`
 * matches by KEY PREFIX, so a bare `['scenarios']` invalidation also matches
 * `['scenarios', id]`, `['scenarios', id, 'operations']`,
 * `['scenarios', id, 'comparison']`, etc. — every query for every scenario.
 * Caught by manually driving the app in a browser (not by the unit tests,
 * which mock these hooks): deleting a scenario while its workspace page was
 * still mid-unmount invalidated that same scenario's own detail/comparison/
 * operations queries, which were still mounted for another instant, causing
 * them to refetch a row that had just been deleted — three benign-looking
 * but noisy 404s logged to the console. Fixed below: only the list query is
 * invalidated by key prefix; delete removes the specific scenario's cache
 * entries outright (`removeQueries`, not `invalidateQueries` — there is
 * nothing left to refetch) instead of matching by prefix. */

export function useCreateScenario() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ScenarioCreateInput) => scenariosApi.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scenarios', 'list'] })
    },
  })
}

export function useUpdateScenario(scenarioId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ScenarioUpdateInput) =>
      scenariosApi.update(scenarioId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scenarios', 'list'] })
      // exact: true — refreshes only the ScenarioRead metadata (name/
      // status/dates), not this scenario's operations/results/comparison
      // sub-queries, which a name/status edit doesn't affect and which
      // must never silently refetch (prompt §13).
      void queryClient.invalidateQueries({
        queryKey: ['scenarios', scenarioId],
        exact: true,
      })
    },
  })
}

export function useDeleteScenario() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (scenarioId: string) => scenariosApi.remove(scenarioId),
    onSuccess: (_data, scenarioId) => {
      void queryClient.invalidateQueries({ queryKey: ['scenarios', 'list'] })
      queryClient.removeQueries({ queryKey: ['scenarios', scenarioId] })
    },
  })
}
