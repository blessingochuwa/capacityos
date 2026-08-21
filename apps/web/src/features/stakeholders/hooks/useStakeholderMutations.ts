import { useMutation, useQueryClient } from '@tanstack/react-query'
import { stakeholdersApi } from '../api/stakeholdersApi'
import type { StakeholderCreateInput, StakeholderUpdateInput } from '../api/stakeholdersApi'

export function useCreateStakeholder(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: StakeholderCreateInput) => stakeholdersApi.create(projectId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'stakeholders'] })
    },
  })
}

export function useUpdateStakeholder(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      stakeholderId,
      data,
    }: {
      stakeholderId: string
      data: StakeholderUpdateInput
    }) => stakeholdersApi.update(projectId, stakeholderId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'stakeholders'] })
    },
  })
}

export function useDeleteStakeholder(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (stakeholderId: string) => stakeholdersApi.remove(projectId, stakeholderId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'stakeholders'] })
    },
  })
}
