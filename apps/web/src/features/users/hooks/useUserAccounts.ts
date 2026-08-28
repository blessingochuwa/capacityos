import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { usersApi, type CreateUserInput } from '../api/usersApi'

/** Keyed `['user-accounts']`, deliberately distinct from
 * features/access/hooks/useUsers.ts's `['users']` — that hook fetches the
 * same endpoint but for the access-grant picker's own minimal shape, and
 * keeping the caches separate avoids either feature depending on the
 * other's query lifecycle. */
export function useUserAccounts() {
  return useQuery({
    queryKey: ['user-accounts'],
    queryFn: usersApi.list,
  })
}

export function useCreateUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateUserInput) => usersApi.create(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['user-accounts'] })
    },
  })
}

export function useSetUserStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars: { userId: string; status: 'active' | 'disabled' }) =>
      usersApi.setStatus(vars.userId, vars.status),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['user-accounts'] })
    },
  })
}
