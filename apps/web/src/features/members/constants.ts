import type { UserRole } from '@/features/auth/types/auth'

/** The five roles apps/api/app/models/enums.py::UserRole defines, in
 * descending authority order (the order ROLE_PERMISSIONS in
 * app/domain/authorization.py grants them). The backend independently
 * enforces that only an Owner may grant or change an Owner/Admin role
 * (403) and that an organization always keeps at least one active Owner
 * (422) — this list is only what the role picker offers; it never
 * re-derives that authorization (CLAUDE.md §21). */
export const ROLE_OPTIONS: readonly { value: UserRole; label: string }[] = [
  { value: 'owner', label: 'Owner' },
  { value: 'admin', label: 'Admin' },
  { value: 'manager', label: 'Manager' },
  { value: 'member', label: 'Member' },
  { value: 'viewer', label: 'Viewer' },
]

export const ROLE_LABEL: Record<UserRole, string> = {
  owner: 'Owner',
  admin: 'Admin',
  manager: 'Manager',
  member: 'Member',
  viewer: 'Viewer',
}
