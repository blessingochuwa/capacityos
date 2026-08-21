import { useQuery } from '@tanstack/react-query'
import { stakeholdersApi } from '../api/stakeholdersApi'

export function useStakeholders(projectId: string | undefined) {
  return useQuery({
    queryKey: ['projects', projectId, 'stakeholders'],
    queryFn: () => stakeholdersApi.listForProject(projectId as string),
    enabled: projectId !== undefined,
  })
}
