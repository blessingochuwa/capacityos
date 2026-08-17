import { useQuery } from '@tanstack/react-query'
import { skillsApi } from '../api/skillsApi'

export function useSkills(isActive?: boolean) {
  return useQuery({
    queryKey: ['skills', 'list', isActive ?? 'all'],
    queryFn: () => skillsApi.list(isActive),
  })
}

export function useSkill(skillId: string | undefined) {
  return useQuery({
    queryKey: ['skills', skillId],
    queryFn: () => skillsApi.get(skillId as string),
    enabled: skillId !== undefined,
  })
}
