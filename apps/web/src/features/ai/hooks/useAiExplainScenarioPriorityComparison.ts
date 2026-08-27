import { useMutation } from '@tanstack/react-query'
import { aiApi } from '../api/aiApi'

/** The explicit "Explain this comparison" action (Phase 26). */
export function useAiExplainScenarioPriorityComparison() {
  return useMutation({
    mutationFn: ({ scenarioId, frameworkId }: { scenarioId: string; frameworkId: string }) =>
      aiApi.explainScenarioPriorityComparison({
        scenario_id: scenarioId,
        framework_id: frameworkId,
      }),
  })
}
