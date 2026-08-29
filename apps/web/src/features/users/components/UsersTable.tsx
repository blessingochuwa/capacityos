import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { STATUS_BADGE } from '../constants'
import type { UserAccount } from '../types/users'

interface UsersTableProps {
  users: UserAccount[]
  /** `person_id` -> display name, for People in the ACTIVE organization
   * only. A `person_id` that isn't in this map belongs to a Person in
   * another organization (see UsersPage) — the row says so without
   * revealing that Person's name or id. */
  personLabels: Map<string, string>
  onEnable: (userId: string) => void
  onDisable: (userId: string) => void
  /** The one row whose status mutation is in flight — its controls are
   * disabled until it settles. */
  pendingUserId?: string
  /** The most recent failed status change, keyed to the account it was
   * for, so the backend's own message (e.g. the Phase 15 last-Owner 422)
   * is shown on the exact row it applies to, verbatim. */
  actionError?: { userId: string; message: string }
  /** True when a search term or status filter is currently applied — an
   * empty result then means "no match", not "no accounts exist", so the
   * empty state (Phase 34) says so instead of suggesting account
   * creation. */
  isFiltered?: boolean
}

function personCell(user: UserAccount, personLabels: Map<string, string>) {
  if (!user.person_id) return <span className="text-slate-500">—</span>
  const label = personLabels.get(user.person_id)
  if (label) return label
  return (
    <span className="text-slate-400">Linked to a person in another organization</span>
  )
}

export function UsersTable({
  users,
  personLabels,
  onEnable,
  onDisable,
  pendingUserId,
  actionError,
  isFiltered = false,
}: UsersTableProps) {
  const [confirmingId, setConfirmingId] = useState<string | null>(null)

  if (users.length === 0) {
    return isFiltered ? (
      <EmptyState
        title="No accounts match your search."
        description="Try a different name, email, or status filter."
      />
    ) : (
      <EmptyState
        title="No accounts yet."
        description="Create one above. An account is a login identity — give it a role in an organization from the Members page."
      />
    )
  }

  return (
    <Table caption="All CapacityOS accounts, their status, and any linked person">
      <thead>
        <tr>
          <Th scope="col">Account</Th>
          <Th scope="col">Status</Th>
          <Th scope="col">Linked person</Th>
          <Th scope="col">Last login</Th>
          <Th scope="col">
            <span className="sr-only">Actions</span>
          </Th>
        </tr>
      </thead>
      <tbody>
        {users.map((user) => {
          const isPending = pendingUserId === user.id
          const rowError = actionError?.userId === user.id ? actionError.message : null
          const badge = STATUS_BADGE[user.status]
          return (
            <tr key={user.id}>
              <Td className="font-medium text-slate-100">
                {user.display_name}
                <span className="block text-xs font-normal text-slate-400">
                  {user.email}
                </span>
                {rowError ? (
                  <span role="alert" className="mt-1 block text-xs text-rose-300">
                    {rowError}
                  </span>
                ) : null}
              </Td>
              <Td>
                <Badge variant={badge.variant}>{badge.label}</Badge>
              </Td>
              <Td>{personCell(user, personLabels)}</Td>
              <Td>
                {user.last_login_at
                  ? new Date(user.last_login_at).toLocaleString()
                  : 'Never'}
              </Td>
              <Td>
                {user.status === 'active' ? (
                  confirmingId === user.id ? (
                    <span className="flex items-center gap-2">
                      <span className="text-xs text-slate-400">
                        Disable this account?
                      </span>
                      <Button
                        variant="secondary"
                        onClick={() => onDisable(user.id)}
                        disabled={isPending}
                      >
                        {isPending ? 'Disabling…' : 'Confirm disable'}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => setConfirmingId(null)}
                        disabled={isPending}
                      >
                        Cancel
                      </Button>
                    </span>
                  ) : (
                    <Button variant="ghost" onClick={() => setConfirmingId(user.id)}>
                      Disable
                    </Button>
                  )
                ) : (
                  <Button
                    variant="ghost"
                    onClick={() => onEnable(user.id)}
                    disabled={isPending}
                  >
                    {isPending ? 'Enabling…' : 'Enable'}
                  </Button>
                )}
              </Td>
            </tr>
          )
        })}
      </tbody>
    </Table>
  )
}
