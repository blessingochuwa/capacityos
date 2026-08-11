import { useQuery } from '@tanstack/react-query'
import { teamsApi } from '@/api/entities'

export function useTeams() {
  return useQuery({
    queryKey: ['teams'],
    queryFn: teamsApi.list,
  })
}
