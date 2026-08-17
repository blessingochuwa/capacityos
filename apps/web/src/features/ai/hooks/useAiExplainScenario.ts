import { useMutation } from '@tanstack/react-query'
import { aiApi } from '../api/aiApi'

/** The explicit "Explain scenario impact" action. */
export function useAiExplainScenario() {
  return useMutation({
    mutationFn: (scenarioId: string) =>
      aiApi.explainScenario({ scenario_id: scenarioId }),
  })
}
