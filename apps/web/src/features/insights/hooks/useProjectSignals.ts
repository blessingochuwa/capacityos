import { useQuery } from '@tanstack/react-query'
import { insightsApi, type DateRangeParams } from '../api/insightsApi'

export function useProjectSignals(
  projectId: string | undefined,
  range: DateRangeParams,
) {
  return useQuery({
    queryKey: [
      'insights',
      'project',
      projectId,
      range.start_date,
      range.end_date,
    ],
    queryFn: () => {
      if (!projectId)
        throw new Error('useProjectSignals called without a projectId')
      return insightsApi.getProjectSignals(projectId, range)
    },
    enabled: projectId !== undefined,
  })
}
