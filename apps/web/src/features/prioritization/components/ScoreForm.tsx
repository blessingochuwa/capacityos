import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useCreateScore, useUpdateScore } from '../hooks/useScoreMutations'
import type { PrioritizationFramework, ProjectPriorityScore } from '../types/prioritization'

interface ScoreFormProps {
  projectId: string
  framework: PrioritizationFramework
  /** When set, edits this project's existing score under this framework
   * instead of creating a new one — same component, mirroring
   * StakeholderForm's create-vs-edit reuse pattern. */
  score?: ProjectPriorityScore
  onDone?: () => void
  onCancel?: () => void
}

/** The Project Scoring Drawer (rendered inline, not as an overlay — no
 * drawer/modal primitive exists yet in components/ui/, and adding one
 * purely for this phase would be new design-system surface beyond
 * "reuse existing," see docs/PRD-phase-17-prioritization.md). One input
 * per criterion the framework actually defines — RICE's four fixed
 * criteria for a RICE framework, or whatever an organization defined for
 * a Weighted Scoring framework. */
export function ScoreForm({ projectId, framework, score, onDone, onCancel }: ScoreFormProps) {
  const isEditing = score !== undefined
  const [values, setValues] = useState<Record<string, string>>(() => {
    const initial: Record<string, string> = {}
    if (score) {
      for (const criterion of framework.criteria) {
        const existing = score.breakdown[criterion.key]
        if (existing !== undefined) initial[criterion.key] = existing
      }
    }
    return initial
  })
  const [notes, setNotes] = useState(score?.notes ?? '')
  const createScore = useCreateScore(projectId)
  const updateScore = useUpdateScore(projectId)
  const mutation = isEditing ? updateScore : createScore

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const submittedValues = Object.entries(values)
      .filter(([, value]) => value.trim() !== '')
      .map(([criterion_key, value]) => ({ criterion_key, value: value.trim() }))

    if (isEditing) {
      updateScore.mutate(
        { scoreId: score.id, data: { values: submittedValues, notes: notes.trim() || null } },
        { onSuccess: () => onDone?.() },
      )
      return
    }

    createScore.mutate(
      { framework_id: framework.id, values: submittedValues, notes: notes.trim() || undefined },
      { onSuccess: () => onDone?.() },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <p className="text-xs text-slate-400">
        Scoring against <span className="font-medium text-slate-200">{framework.name}</span>.
        Leave a criterion blank to record it later — an incomplete score is shown as such,
        never guessed.
      </p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {framework.criteria.map((criterion) => (
          <div key={criterion.id} className="flex flex-col gap-1">
            <label
              htmlFor={`criterion-${criterion.key}`}
              className="text-xs font-medium text-slate-400"
            >
              {criterion.name}
              {criterion.weight !== null ? (
                <span className="ml-1 text-slate-500">(weight {criterion.weight})</span>
              ) : null}
            </label>
            <input
              id={`criterion-${criterion.key}`}
              inputMode="decimal"
              value={values[criterion.key] ?? ''}
              onChange={(event) =>
                setValues((prev) => ({ ...prev, [criterion.key]: event.target.value }))
              }
              className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
            />
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="score-notes" className="text-xs font-medium text-slate-400">
          Notes
        </label>
        <input
          id="score-notes"
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Context for this score (not visible in audit metadata)"
          className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
        />
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" disabled={mutation.isPending}>
          {mutation.isPending ? 'Saving…' : isEditing ? 'Save changes' : 'Save score'}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        {mutation.isError ? (
          <p role="alert" className="text-xs text-rose-300">
            {mutation.error.message}
          </p>
        ) : null}
      </div>
    </form>
  )
}
