import { useMutation, useQueryClient } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'

export function useCreateSnapshot() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (frameworkId: string) => prioritizationApi.createSnapshot(frameworkId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['prioritization', 'snapshots'] })
    },
  })
}
