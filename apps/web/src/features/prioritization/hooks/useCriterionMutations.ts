import { useMutation, useQueryClient } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'
import type { CriterionInput, CriterionUpdateInput } from '../api/prioritizationApi'

export function useAddCriterion(frameworkId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CriterionInput) => prioritizationApi.addCriterion(frameworkId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['prioritization', 'frameworks'] })
    },
  })
}

export function useUpdateCriterion(frameworkId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      criterionId,
      data,
    }: {
      criterionId: string
      data: CriterionUpdateInput
    }) => prioritizationApi.updateCriterion(frameworkId, criterionId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['prioritization', 'frameworks'] })
    },
  })
}

export function useRemoveCriterion(frameworkId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (criterionId: string) =>
      prioritizationApi.removeCriterion(frameworkId, criterionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['prioritization', 'frameworks'] })
    },
  })
}
