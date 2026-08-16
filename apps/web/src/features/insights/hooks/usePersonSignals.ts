import { useQuery } from '@tanstack/react-query'
import { insightsApi, type DateRangeParams } from '../api/insightsApi'

export function usePersonSignals(
  personId: string | undefined,
  range: DateRangeParams,
) {
  return useQuery({
    queryKey: [
      'insights',
      'person',
      personId,
      range.start_date,
      range.end_date,
    ],
    queryFn: () => {
      if (!personId)
        throw new Error('usePersonSignals called without a personId')
      return insightsApi.getPersonSignals(personId, range)
    },
    enabled: personId !== undefined,
  })
}
