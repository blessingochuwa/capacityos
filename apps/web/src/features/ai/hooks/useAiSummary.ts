import { useMutation } from '@tanstack/react-query'
import { aiApi } from '../api/aiApi'
import type { AISummaryRequest } from '../types/ai'

/** The explicit "Summarize" action — never auto-fetched, always a direct
 * response to a button click. Nothing to cache/invalidate afterward: an AI
 * response isn't list data another view depends on. */
export function useAiSummary() {
  return useMutation({
    mutationFn: (data: AISummaryRequest) => aiApi.summarize(data),
  })
}
