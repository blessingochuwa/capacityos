import { useQuery } from '@tanstack/react-query'
import { insightsApi, type DateRangeParams } from '../api/insightsApi'

export function useTeamSummary(
  teamId: string | undefined,
  range: DateRangeParams,
  options: { projectId?: string; scenarioId?: string } = {},
) {
  return useQuery({
    queryKey: [
      'insights',
      'team',
      teamId,
      'summary',
      range.start_date,
      range.end_date,
      options.projectId,
      options.scenarioId,
    ],
    queryFn: () => {
      if (!teamId) throw new Error('useTeamSummary called without a teamId')
      return insightsApi.getTeamSummary(teamId, {
        ...range,
        project_id: options.projectId,
        scenario_id: options.scenarioId,
      })
    },
    enabled: teamId !== undefined,
  })
}
