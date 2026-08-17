import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { skillsApi } from '../api/skillsApi'
import type { PersonSkillInput } from '../api/skillsApi'
import type { SkillProficiency } from '../types/skills'

export function usePersonSkills(personId: string | undefined) {
  return useQuery({
    queryKey: ['people', personId, 'skills'],
    queryFn: () => skillsApi.listPersonSkills(personId as string),
    enabled: personId !== undefined,
  })
}

export function useAddPersonSkill(personId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: PersonSkillInput) =>
      skillsApi.addPersonSkill(personId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['people', personId, 'skills'],
      })
      void queryClient.invalidateQueries({ queryKey: ['skills', 'list'] })
    },
  })
}

export function useUpdatePersonSkill(personId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      personSkillId,
      proficiency,
      notes,
    }: {
      personSkillId: string
      proficiency?: SkillProficiency
      notes?: string
    }) =>
      skillsApi.updatePersonSkill(personId, personSkillId, {
        proficiency,
        notes,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['people', personId, 'skills'],
      })
    },
  })
}

export function useRemovePersonSkill(personId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (personSkillId: string) =>
      skillsApi.removePersonSkill(personId, personSkillId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['people', personId, 'skills'],
      })
      void queryClient.invalidateQueries({ queryKey: ['skills', 'list'] })
    },
  })
}
