import { useQuery } from '@tanstack/react-query'
import { capacityApi, type DateRangeParams } from '../api/capacityApi'

export function useProjectDemand(
  projectId: string | undefined,
  range: DateRangeParams,
) {
  return useQuery({
    queryKey: [
      'capacity',
      'project',
      projectId,
      range.start_date,
      range.end_date,
    ],
    queryFn: () => {
      if (!projectId)
        throw new Error('useProjectDemand called without a projectId')
      return capacityApi.getProjectDemand(projectId, range)
    },
    enabled: projectId !== undefined,
  })
}
