import { useMutation, useQueryClient } from '@tanstack/react-query'
import { skillsApi } from '../api/skillsApi'
import type { SkillCreateInput, SkillUpdateInput } from '../api/skillsApi'

export function useCreateSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: SkillCreateInput) => skillsApi.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['skills', 'list'] })
    },
  })
}

export function useUpdateSkill(skillId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: SkillUpdateInput) => skillsApi.update(skillId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['skills', 'list'] })
      void queryClient.invalidateQueries({
        queryKey: ['skills', skillId],
        exact: true,
      })
    },
  })
}

export function useDeactivateSkill() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (skillId: string) => skillsApi.deactivate(skillId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['skills', 'list'] })
    },
  })
}
