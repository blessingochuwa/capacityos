import { useQuery } from '@tanstack/react-query'
import { capacityApi, type DateRangeParams } from '../api/capacityApi'

export function useTeamCapacity(
  teamId: string | undefined,
  range: DateRangeParams,
) {
  return useQuery({
    queryKey: ['capacity', 'team', teamId, range.start_date, range.end_date],
    queryFn: () => {
      if (!teamId) throw new Error('useTeamCapacity called without a teamId')
      return capacityApi.getTeamCapacity(teamId, range)
    },
    enabled: teamId !== undefined,
  })
}
