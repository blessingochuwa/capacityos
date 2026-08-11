import { useQuery } from '@tanstack/react-query'
import { allocationsApi, availabilityExceptionsApi } from '@/api/entities'

export function usePersonAllocations(personId: string | undefined) {
  return useQuery({
    queryKey: ['allocations', 'person', personId],
    queryFn: () => {
      if (!personId)
        throw new Error('usePersonAllocations called without a personId')
      return allocationsApi.listForPerson(personId)
    },
    enabled: personId !== undefined,
  })
}

export function usePersonAvailabilityExceptions(personId: string | undefined) {
  return useQuery({
    queryKey: ['availability-exceptions', 'person', personId],
    queryFn: () => {
      if (!personId) {
        throw new Error(
          'usePersonAvailabilityExceptions called without a personId',
        )
      }
      return availabilityExceptionsApi.listForPerson(personId)
    },
    enabled: personId !== undefined,
  })
}
