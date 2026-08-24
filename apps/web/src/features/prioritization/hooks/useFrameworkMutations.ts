import { useMutation, useQueryClient } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'
import type { FrameworkCreateInput, FrameworkUpdateInput } from '../api/prioritizationApi'

export function useCreateFramework() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: FrameworkCreateInput) => prioritizationApi.createFramework(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['prioritization', 'frameworks'] })
    },
  })
}

export function useUpdateFramework() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      frameworkId,
      data,
    }: {
      frameworkId: string
      data: FrameworkUpdateInput
    }) => prioritizationApi.updateFramework(frameworkId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['prioritization', 'frameworks'] })
    },
  })
}

export function useDeactivateFramework() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (frameworkId: string) => prioritizationApi.deactivateFramework(frameworkId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['prioritization', 'frameworks'] })
    },
  })
}
