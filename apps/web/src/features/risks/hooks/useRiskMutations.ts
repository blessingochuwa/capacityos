import { useMutation, useQueryClient } from '@tanstack/react-query'
import { risksApi } from '../api/risksApi'
import type { RiskCreateInput, RiskUpdateInput } from '../api/risksApi'

export function useCreateRisk(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: RiskCreateInput) => risksApi.create(projectId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'risks'] })
    },
  })
}

export function useUpdateRisk(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ riskId, data }: { riskId: string; data: RiskUpdateInput }) =>
      risksApi.update(projectId, riskId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'risks'] })
    },
  })
}

export function useDeleteRisk(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (riskId: string) => risksApi.remove(projectId, riskId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'risks'] })
    },
  })
}
