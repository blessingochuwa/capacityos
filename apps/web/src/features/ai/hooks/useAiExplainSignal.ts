import { useMutation } from '@tanstack/react-query'
import { aiApi } from '../api/aiApi'
import type { AIExplainSignalRequest } from '../types/ai'

/** The explicit "Explain this signal" action. */
export function useAiExplainSignal() {
  return useMutation({
    mutationFn: (data: AIExplainSignalRequest) => aiApi.explainSignal(data),
  })
}
