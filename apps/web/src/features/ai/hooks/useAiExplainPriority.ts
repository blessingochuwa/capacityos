import { useMutation } from '@tanstack/react-query'
import { aiApi } from '../api/aiApi'

/** The explicit "Explain this score" action (Phase 19). */
export function useAiExplainPriority() {
  return useMutation({
    mutationFn: ({ projectId, scoreId }: { projectId: string; scoreId: string }) =>
      aiApi.explainPriority({ project_id: projectId, score_id: scoreId }),
  })
}
