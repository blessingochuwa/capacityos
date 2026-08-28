import type { BadgeVariant } from '@/components/ui/Badge'
import type { UserStatus } from './types/users'

/** Account status is never conveyed by colour alone (CLAUDE.md §29) — the
 * badge always carries its text label too. */
export const STATUS_BADGE: Record<UserStatus, { variant: BadgeVariant; label: string }> = {
  active: { variant: 'success', label: 'Active' },
  invited: { variant: 'warning', label: 'Invited' },
  disabled: { variant: 'danger', label: 'Disabled' },
}

/** apps/api/app/schemas/user.py::UserCreate — `password` is
 * `Field(min_length=10, max_length=128)`. The form enforces exactly this
 * and nothing more: no strength meter, no confirmation field, no invite/
 * onboarding step (CLAUDE.md §26 — the backend defines none). */
export const PASSWORD_MIN_LENGTH = 10
export const PASSWORD_MAX_LENGTH = 128
