import { useMutation, useQueryClient } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'
import type { ScoreCreateInput, ScoreUpdateInput } from '../api/prioritizationApi'

export function useCreateScore(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ScoreCreateInput) => prioritizationApi.createScore(projectId, data),
    onSuccess: (score) => {
      void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'priority-scores'] })
      void queryClient.invalidateQueries({
        queryKey: ['prioritization', 'portfolio', score.framework_id],
      })
    },
  })
}

export function useUpdateScore(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ scoreId, data }: { scoreId: string; data: ScoreUpdateInput }) =>
      prioritizationApi.updateScore(projectId, scoreId, data),
    onSuccess: (score) => {
      void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'priority-scores'] })
      void queryClient.invalidateQueries({
        queryKey: ['prioritization', 'portfolio', score.framework_id],
      })
    },
  })
}

export function useDeleteScore(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (scoreId: string) => prioritizationApi.deleteScore(projectId, scoreId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'priority-scores'] })
      void queryClient.invalidateQueries({ queryKey: ['prioritization', 'portfolio'] })
    },
  })
}
