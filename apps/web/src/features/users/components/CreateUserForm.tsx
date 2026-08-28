import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from '../constants'
import type { CreateUserInput } from '../api/usersApi'

interface CreateUserFormProps {
  /** People in the ACTIVE organization not already linked to an account —
   * the only People an account may be linked to (apps/api validates
   * `person_id` against the acting organization). Empty is fine: the link
   * is optional. */
  eligiblePeople: { id: string; display_name: string }[]
  /** Resolves on success (the form clears) and rejects on failure (fields
   * are kept). The parent renders `error` from the same mutation. */
  onSubmit: (data: CreateUserInput) => Promise<unknown>
  isPending: boolean
  error?: string
}

const INPUT_CLASS =
  'rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400'

export function CreateUserForm({
  eligiblePeople,
  onSubmit,
  isPending,
  error,
}: CreateUserFormProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [personId, setPersonId] = useState('')

  const canSubmit =
    email.trim().length > 0 &&
    displayName.trim().length > 0 &&
    password.length >= PASSWORD_MIN_LENGTH &&
    password.length <= PASSWORD_MAX_LENGTH

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!canSubmit) return
    onSubmit({
      email: email.trim(),
      password,
      display_name: displayName.trim(),
      person_id: personId || null,
    })
      .then(() => {
        setEmail('')
        setPassword('')
        setDisplayName('')
        setPersonId('')
      })
      .catch(() => {
        // Surfaced via the `error` prop; keep the fields for correction.
      })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="create-user-name" className="text-xs font-medium text-slate-400">
          Display name
        </label>
        <input
          id="create-user-name"
          type="text"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          className={INPUT_CLASS}
          maxLength={200}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="create-user-email" className="text-xs font-medium text-slate-400">
          Email
        </label>
        <input
          id="create-user-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className={INPUT_CLASS}
          placeholder="person@example.com"
          autoComplete="off"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label
          htmlFor="create-user-password"
          className="text-xs font-medium text-slate-400"
        >
          Initial password
        </label>
        <input
          id="create-user-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className={INPUT_CLASS}
          autoComplete="new-password"
          aria-describedby="create-user-password-hint"
        />
        <span id="create-user-password-hint" className="text-xs text-slate-500">
          At least {PASSWORD_MIN_LENGTH} characters. Share it with the account holder
          directly.
        </span>
      </div>
      <div className="w-52">
        <Select
          label="Linked person (optional)"
          value={personId}
          placeholder="No linked person"
          options={eligiblePeople.map((person) => ({
            value: person.id,
            label: person.display_name,
          }))}
          onChange={(event) => setPersonId(event.target.value)}
        />
      </div>
      <Button type="submit" variant="primary" disabled={!canSubmit || isPending}>
        {isPending ? 'Creating…' : 'Create account'}
      </Button>
      {error ? (
        <p role="alert" className="w-full text-xs text-rose-300">
          {error}
        </p>
      ) : null}
    </form>
  )
}
