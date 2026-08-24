import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useAddCriterion, useRemoveCriterion, useUpdateCriterion } from '../hooks/useCriterionMutations'
import type { PrioritizationFramework } from '../types/prioritization'

interface FrameworkCriteriaEditorProps {
  framework: PrioritizationFramework
}

/** Add/rename/reweight/remove a Weighted Scoring framework's criteria
 * after it's been created (Phase 18) — RICE/ICE/WSJF's criteria are
 * fixed by their methodology and MoSCoW has none at all, so this editor
 * only ever renders for framework_type=weighted (see the caller). The
 * backend independently rejects any of these calls against a non-
 * editable criterion (403) regardless of what this UI shows. */
export function FrameworkCriteriaEditor({ framework }: FrameworkCriteriaEditorProps) {
  const addCriterion = useAddCriterion(framework.id)
  const updateCriterion = useUpdateCriterion(framework.id)
  const removeCriterion = useRemoveCriterion(framework.id)

  const [newName, setNewName] = useState('')
  const [newWeight, setNewWeight] = useState('1')
  const [drafts, setDrafts] = useState<Record<string, { name: string; weight: string }>>({})

  function draftFor(criterionId: string, name: string, weight: string | null) {
    return drafts[criterionId] ?? { name, weight: weight ?? '1' }
  }

  function handleAdd(event: React.FormEvent) {
    event.preventDefault()
    const name = newName.trim()
    const weight = newWeight.trim()
    if (name === '' || weight === '') return
    addCriterion.mutate(
      { name, weight },
      {
        onSuccess: () => {
          setNewName('')
          setNewWeight('1')
        },
      },
    )
  }

  function handleSave(criterionId: string) {
    const draft = drafts[criterionId]
    if (!draft) return
    updateCriterion.mutate({
      criterionId,
      data: { name: draft.name.trim(), weight: draft.weight.trim() },
    })
  }

  const canRemove = framework.criteria.length > 1

  return (
    <div className="space-y-2 rounded-md border border-slate-800 p-3">
      <span className="text-xs font-medium text-slate-400">Edit criteria</span>
      {framework.criteria.map((criterion) => {
        const draft = draftFor(criterion.id, criterion.name, criterion.weight)
        return (
          <div key={criterion.id} className="flex items-center gap-2">
            <input
              value={draft.name}
              onChange={(event) =>
                setDrafts((prev) => ({
                  ...prev,
                  [criterion.id]: { ...draft, name: event.target.value },
                }))
              }
              aria-label={`${criterion.name} name`}
              className="flex-1 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
            />
            <input
              value={draft.weight}
              onChange={(event) =>
                setDrafts((prev) => ({
                  ...prev,
                  [criterion.id]: { ...draft, weight: event.target.value },
                }))
              }
              aria-label={`${criterion.name} weight`}
              className="w-24 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
            />
            <Button
              type="button"
              variant="ghost"
              onClick={() => handleSave(criterion.id)}
              disabled={updateCriterion.isPending}
            >
              Save
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => removeCriterion.mutate(criterion.id)}
              disabled={!canRemove || removeCriterion.isPending}
            >
              Remove
            </Button>
          </div>
        )
      })}

      <form onSubmit={handleAdd} className="flex items-center gap-2 pt-1">
        <input
          value={newName}
          onChange={(event) => setNewName(event.target.value)}
          placeholder="New criterion name"
          className="flex-1 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
        />
        <input
          value={newWeight}
          onChange={(event) => setNewWeight(event.target.value)}
          placeholder="Weight"
          className="w-24 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
        />
        <Button type="submit" variant="secondary" disabled={addCriterion.isPending}>
          Add criterion
        </Button>
      </form>
      {addCriterion.isError || updateCriterion.isError || removeCriterion.isError ? (
        <p role="alert" className="text-xs text-rose-300">
          {(addCriterion.error ?? updateCriterion.error ?? removeCriterion.error)?.message}
        </p>
      ) : null}
    </div>
  )
}
