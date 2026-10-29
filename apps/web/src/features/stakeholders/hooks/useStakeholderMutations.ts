import { useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { stakeholdersApi } from '../api/stakeholdersApi'
import type { StakeholderCreateInput, StakeholderUpdateInput } from '../api/stakeholdersApi'

/** Refreshes the edited project's own register AND the org-wide register
 * (Phase 48, `['org-stakeholders', filters]` — every filter/page variant)
 * — both render on the same StakeholdersOverviewPage, so an edit in one
 * must never leave the other showing stale rows. */
function invalidateStakeholderQueries(queryClient: QueryClient, projectId: string) {
  void queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'stakeholders'] })
  void queryClient.invalidateQueries({ queryKey: ['org-stakeholders'] })
}

export function useCreateStakeholder(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: StakeholderCreateInput) => stakeholdersApi.create(projectId, data),
    onSuccess: () => invalidateStakeholderQueries(queryClient, projectId),
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
    onSuccess: () => invalidateStakeholderQueries(queryClient, projectId),
  })
}

export function useDeleteStakeholder(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (stakeholderId: string) => stakeholdersApi.remove(projectId, stakeholderId),
    onSuccess: () => invalidateStakeholderQueries(queryClient, projectId),
  })
}
