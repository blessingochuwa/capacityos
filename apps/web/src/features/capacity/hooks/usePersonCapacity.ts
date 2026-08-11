import { useQuery } from '@tanstack/react-query'
import { capacityApi, type DateRangeParams } from '../api/capacityApi'

export function usePersonCapacity(
  personId: string | undefined,
  range: DateRangeParams,
) {
  return useQuery({
    queryKey: [
      'capacity',
      'person',
      personId,
      range.start_date,
      range.end_date,
    ],
    queryFn: () => {
      if (!personId)
        throw new Error('usePersonCapacity called without a personId')
      return capacityApi.getPersonCapacity(personId, range)
    },
    enabled: personId !== undefined,
  })
}
