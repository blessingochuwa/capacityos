import { useQuery } from '@tanstack/react-query'
import { usersApi } from '../api/accessGrantsApi'

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: usersApi.list,
  })
}
