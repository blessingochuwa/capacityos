import { useQuery } from '@tanstack/react-query'
import { insightsApi, type DateRangeParams } from '../api/insightsApi'

export function useTeamSignals(
  teamId: string | undefined,
  range: DateRangeParams,
) {
  return useQuery({
    queryKey: ['insights', 'team', teamId, range.start_date, range.end_date],
    queryFn: () => {
      if (!teamId) throw new Error('useTeamSignals called without a teamId')
      return insightsApi.getTeamSignals(teamId, range)
    },
    enabled: teamId !== undefined,
  })
}
