import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/Button'

interface RenameOrganizationFormProps {
  currentName: string
  /** Resolves on success, rejects on failure (the field keeps the typed
   * value so it can be corrected). The parent renders `error`. */
  onSubmit: (name: string) => Promise<unknown>
  isPending: boolean
  error?: string
}

/** apps/api/app/schemas/organization.py::OrganizationUpdate —
 * `name: Field(min_length=1, max_length=200)`. The form enforces exactly
 * this and nothing more. */
const NAME_MAX_LENGTH = 200

const INPUT_CLASS =
  'w-72 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400'

export function RenameOrganizationForm({
  currentName,
  onSubmit,
  isPending,
  error,
}: RenameOrganizationFormProps) {
  const [name, setName] = useState(currentName)

  const trimmed = name.trim()
  const canSubmit =
    trimmed.length > 0 && trimmed.length <= NAME_MAX_LENGTH && trimmed !== currentName

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!canSubmit) return
    onSubmit(trimmed).catch(() => {
      // Surfaced via the `error` prop; keep the field for correction.
    })
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="organization-name" className="text-xs font-medium text-slate-400">
          Organization name
        </label>
        <input
          id="organization-name"
          type="text"
          value={name}
          onChange={(event) => setName(event.target.value)}
          className={INPUT_CLASS}
          maxLength={NAME_MAX_LENGTH}
        />
      </div>
      <Button type="submit" variant="primary" disabled={!canSubmit || isPending}>
        {isPending ? 'Saving…' : 'Save name'}
      </Button>
      {error ? (
        <p role="alert" className="w-full text-xs text-rose-300">
          {error}
        </p>
      ) : null}
    </form>
  )
}
