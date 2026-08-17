import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { skillsApi } from '../api/skillsApi'
import type { ProjectSkillRequirementInput } from '../api/skillsApi'

export function useProjectSkillRequirements(projectId: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectId, 'skill-requirements'],
    queryFn: () => skillsApi.listProjectSkillRequirements(projectId as string),
    enabled: projectId !== undefined,
  })
}

export function useAddProjectSkillRequirement(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ProjectSkillRequirementInput) =>
      skillsApi.addProjectSkillRequirement(projectId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'skill-requirements'],
      })
      void queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'skill-coverage'],
      })
    },
  })
}

export function useUpdateProjectSkillRequirement(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      requirementId,
      data,
    }: {
      requirementId: string
      data: Partial<ProjectSkillRequirementInput>
    }) => skillsApi.updateProjectSkillRequirement(projectId, requirementId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'skill-requirements'],
      })
      void queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'skill-coverage'],
      })
    },
  })
}

export function useRemoveProjectSkillRequirement(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (requirementId: string) =>
      skillsApi.removeProjectSkillRequirement(projectId, requirementId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'skill-requirements'],
      })
      void queryClient.invalidateQueries({
        queryKey: ['projects', projectId, 'skill-coverage'],
      })
    },
  })
}
