import { Select } from '@/components/ui/Select'
import { STATUS_BADGE } from '../constants'
import type { UserStatus } from '../types/users'

interface UsersFilterBarProps {
  /** The raw, not-yet-debounced search text — kept as a controlled input
   * value distinct from the (debounced) value actually sent to the API,
   * so typing never feels laggy even though the request itself is
   * debounced (see UsersPage). */
  searchValue: string
  onSearchChange: (value: string) => void
  statusValue: UserStatus | ''
  onStatusChange: (value: UserStatus | '') => void
}

const INPUT_CLASS =
  'rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400'

const STATUS_OPTIONS: { value: UserStatus; label: string }[] = (
  Object.keys(STATUS_BADGE) as UserStatus[]
).map((status) => ({ value: status, label: STATUS_BADGE[status].label }))

/** The account-directory search/filter controls (Phase 34) — search by
 * email or display name, filter by account status. Both apply through the
 * existing GET /api/v1/users contract server-side; this component holds no
 * filtering logic of its own. */
export function UsersFilterBar({
  searchValue,
  onSearchChange,
  statusValue,
  onStatusChange,
}: UsersFilterBarProps) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="users-search" className="text-xs font-medium text-slate-400">
          Search
        </label>
        <input
          id="users-search"
          type="search"
          value={searchValue}
          onChange={(event) => onSearchChange(event.target.value)}
          className={`${INPUT_CLASS} w-64`}
          placeholder="Search by name or email"
        />
      </div>
      <div className="w-44">
        <Select
          label="Status"
          value={statusValue}
          placeholder="All statuses"
          options={STATUS_OPTIONS}
          onChange={(event) => onStatusChange(event.target.value as UserStatus | '')}
        />
      </div>
    </div>
  )
}
