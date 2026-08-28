import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import type { UserRole } from '@/features/auth/types/auth'
import { ROLE_OPTIONS } from '../constants'

interface AddMemberFormProps {
  /** Resolves on success (the form then clears the email field) and
   * rejects on failure (the field is kept so the value can be corrected).
   * The parent renders `error` from the same mutation. */
  onSubmit: (email: string, role: UserRole) => Promise<unknown>
  isPending: boolean
  error?: string
}

const INPUT_CLASS =
  'rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400'

export function AddMemberForm({ onSubmit, isPending, error }: AddMemberFormProps) {
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<UserRole>('viewer')

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = email.trim()
    if (!trimmed) return
    onSubmit(trimmed, role)
      .then(() => setEmail(''))
      .catch(() => {
        // Error is surfaced via the `error` prop; keep the field as-is.
      })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="add-member-email" className="text-xs font-medium text-slate-400">
          Email of an existing account
        </label>
        <input
          id="add-member-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className={INPUT_CLASS}
          placeholder="person@example.com"
          autoComplete="off"
        />
      </div>
      <div className="w-40">
        <Select
          label="Initial role"
          value={role}
          options={ROLE_OPTIONS.map((option) => ({ ...option }))}
          onChange={(event) => setRole(event.target.value as UserRole)}
        />
      </div>
      <Button type="submit" variant="primary" disabled={!email.trim() || isPending}>
        {isPending ? 'Adding…' : 'Add member'}
      </Button>
      {error ? (
        <p role="alert" className="text-xs text-rose-300">
          {error}
        </p>
      ) : null}
    </form>
  )
}
