import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { peopleApi } from '@/api/entities'
import type { Person } from '@/types/entities'

/** Bulk-fetches every person once (cached by react-query) so any view that
 * needs to join a capacity result's bare `person_id` to a display name/role
 * can do so client-side without an N+1 request per person — see the Phase 3
 * architecture audit note on capacity responses carrying no name. */
export function usePeople() {
  return useQuery({
    queryKey: ['people'],
    queryFn: peopleApi.list,
  })
}

export function usePeopleLookup(): Map<string, Person> {
  const { data } = usePeople()
  return useMemo(() => {
    const lookup = new Map<string, Person>()
    for (const person of data?.items ?? []) {
      lookup.set(person.id, person)
    }
    return lookup
  }, [data])
}
