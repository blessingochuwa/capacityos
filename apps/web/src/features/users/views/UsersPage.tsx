import { useMemo } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { usePeopleLookup } from '@/hooks/usePeople'
import { CreateUserForm } from '../components/CreateUserForm'
import { UsersTable } from '../components/UsersTable'
import { useCreateUser, useSetUserStatus, useUserAccounts } from '../hooks/useUserAccounts'

/**
 * "Who has a login, and is it active?" — account lifecycle management
 * (create / disable / re-enable) for the Phase 10/12/15 `User` identity,
 * the companion to Phase 28's membership UI (features/members/).
 *
 * `User` management is GLOBAL and permission-gated, not organization-
 * scoped: `GET /api/v1/users` is a cross-organization account directory
 * (ADR 0012 Decision 8) and `PATCH /users/{id}` resolves the account
 * globally. The only organization-scoped element is the optional `Person`
 * link, which apps/api validates against the acting organization. This
 * page is gated by `can('user.write')` for UX only — `USER_READ`/
 * `USER_WRITE` share the same grant set (Admin/Owner), and the backend
 * (including the Phase 15 last-Owner invariant on disable) is the real
 * boundary and re-checks every request (CLAUDE.md §21). The page
 * surfaces the backend's own 403/404/409/422 message inline and
 * re-derives none of it. Mirrors features/members/views/MembersPage.
 */
export function UsersPage() {
  const { can } = useAuth()

  if (!can('user.write')) {
    return (
      <div className="space-y-6">
        <PageHeader title="Accounts" />
        <ViewOnlyNotice message="Your role doesn't include permission to manage user accounts." />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accounts"
        description="Every CapacityOS login identity across all organizations. An account has no role on its own — grant one from the Members page. Creating an account here does not send an email; share the initial password directly."
      />

      <Card>
        <CardHeader
          title="User accounts"
          description="Create an account, disable one to block sign-in, or re-enable a disabled one. An account cannot be disabled if it is the last active Owner of any organization."
        />
        <CardBody className="space-y-4">
          <UsersManager />
        </CardBody>
      </Card>
    </div>
  )
}

function UsersManager() {
  const usersQuery = useUserAccounts()
  const peopleLookup = usePeopleLookup()
  const createUser = useCreateUser()
  const setStatus = useSetUserStatus()

  const personLabels = useMemo(() => {
    const labels = new Map<string, string>()
    for (const [id, person] of peopleLookup) {
      labels.set(id, person.display_name)
    }
    return labels
  }, [peopleLookup])

  const linkedPersonIds = useMemo(() => {
    const ids = new Set<string>()
    for (const user of usersQuery.data?.items ?? []) {
      if (user.person_id) ids.add(user.person_id)
    }
    return ids
  }, [usersQuery.data])

  const eligiblePeople = useMemo(
    () =>
      [...peopleLookup.values()]
        .filter((person) => !linkedPersonIds.has(person.id))
        .map((person) => ({ id: person.id, display_name: person.display_name }))
        .sort((a, b) => a.display_name.localeCompare(b.display_name)),
    [peopleLookup, linkedPersonIds],
  )

  const pendingUserId = setStatus.isPending ? setStatus.variables?.userId : undefined
  const actionError =
    setStatus.isError && setStatus.variables
      ? { userId: setStatus.variables.userId, message: setStatus.error.message }
      : undefined

  return (
    <div className="space-y-4">
      <CreateUserForm
        eligiblePeople={eligiblePeople}
        onSubmit={(data) => createUser.mutateAsync(data)}
        isPending={createUser.isPending}
        error={createUser.isError ? createUser.error.message : undefined}
      />
      <QueryBoundary query={usersQuery} loadingLabel="Loading accounts…">
        {(page) => (
          <UsersTable
            users={page.items}
            personLabels={personLabels}
            onEnable={(userId) => setStatus.mutate({ userId, status: 'active' })}
            onDisable={(userId) => setStatus.mutate({ userId, status: 'disabled' })}
            pendingUserId={pendingUserId}
            actionError={actionError}
          />
        )}
      </QueryBoundary>
    </div>
  )
}
