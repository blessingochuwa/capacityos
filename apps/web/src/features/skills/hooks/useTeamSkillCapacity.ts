import { useQuery } from '@tanstack/react-query'
import { skillsApi } from '../api/skillsApi'
import type { DateRangeParams } from '../api/skillsApi'

export function useTeamSkillCapacity(
  teamId: string | undefined,
  range: DateRangeParams,
) {
  return useQuery({
    queryKey: [
      'teams',
      teamId,
      'skill-capacity',
      range.start_date,
      range.end_date,
    ],
    queryFn: () => skillsApi.getTeamSkillCapacity(teamId as string, range),
    enabled: teamId !== undefined,
  })
}
