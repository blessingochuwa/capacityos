import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { useCreateFramework } from '../hooks/useFrameworkMutations'
import type { PrioritizationFrameworkType } from '../types/prioritization'

interface WeightedCriterionDraft {
  name: string
  weight: string
}

const FRAMEWORK_TYPE_OPTIONS: { value: PrioritizationFrameworkType; label: string }[] = [
  { value: 'rice', label: 'RICE (Reach, Impact, Confidence, Effort)' },
  { value: 'weighted', label: 'Weighted scoring (your own criteria)' },
]

/** Owner/Admin only — gated by the caller (PrioritizationOverviewPage) via
 * can('prioritization.manage'), matching every other admin-only form in
 * this codebase (FrameworkBuilder does not re-check permissions itself,
 * same as every other feature form — the backend is what actually
 * enforces this regardless, CLAUDE.md §21). RICE needs no criteria input
 * at all — its four criteria are fixed server-side (see
 * app/domain/prioritization.py::RICE_CRITERION_KEYS) and are seeded
 * automatically once the framework is created. */
export function FrameworkForm({ onDone }: { onDone?: () => void }) {
  const [name, setName] = useState('')
  const [frameworkType, setFrameworkType] = useState<PrioritizationFrameworkType>('rice')
  const [criteria, setCriteria] = useState<WeightedCriterionDraft[]>([
    { name: '', weight: '1' },
  ])
  const createFramework = useCreateFramework()

  function updateCriterion(index: number, patch: Partial<WeightedCriterionDraft>) {
    setCriteria((prev) => prev.map((c, i) => (i === index ? { ...c, ...patch } : c)))
  }

  function addCriterion() {
    setCriteria((prev) => [...prev, { name: '', weight: '1' }])
  }

  function removeCriterion(index: number) {
    setCriteria((prev) => prev.filter((_, i) => i !== index))
  }

  const trimmedCriteria = criteria
    .map((c) => ({ name: c.name.trim(), weight: c.weight.trim() }))
    .filter((c) => c.name !== '')
  const isWeighted = frameworkType === 'weighted'
  const canSubmit = name.trim() !== '' && (!isWeighted || trimmedCriteria.length > 0)

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!canSubmit) return

    createFramework.mutate(
      {
        name: name.trim(),
        framework_type: frameworkType,
        criteria: isWeighted ? trimmedCriteria : [],
      },
      {
        onSuccess: () => {
          setName('')
          setFrameworkType('rice')
          setCriteria([{ name: '', weight: '1' }])
          onDone?.()
        },
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor="framework-name" className="text-xs font-medium text-slate-400">
            Framework name
          </label>
          <input
            id="framework-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Feature RICE, Platform Weighted"
            className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
          />
        </div>
        <Select
          label="Framework type"
          value={frameworkType}
          options={FRAMEWORK_TYPE_OPTIONS}
          onChange={(event) =>
            setFrameworkType(event.target.value as PrioritizationFrameworkType)
          }
        />
      </div>

      {isWeighted ? (
        <div className="space-y-2">
          <span className="text-xs font-medium text-slate-400">Criteria and weights</span>
          {criteria.map((criterion, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                value={criterion.name}
                onChange={(event) => updateCriterion(index, { name: event.target.value })}
                placeholder="Criterion name (e.g. Business Value)"
                className="flex-1 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
              />
              <input
                value={criterion.weight}
                onChange={(event) => updateCriterion(index, { weight: event.target.value })}
                placeholder="Weight"
                className="w-24 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
              />
              <Button
                type="button"
                variant="ghost"
                onClick={() => removeCriterion(index)}
                disabled={criteria.length === 1}
              >
                Remove
              </Button>
            </div>
          ))}
          <Button type="button" variant="ghost" onClick={addCriterion}>
            Add criterion
          </Button>
        </div>
      ) : (
        <p className="text-xs text-slate-400">
          RICE's four criteria (Reach, Impact, Confidence, Effort) are fixed and will be
          created automatically.
        </p>
      )}

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" disabled={!canSubmit || createFramework.isPending}>
          {createFramework.isPending ? 'Creating…' : 'Create framework'}
        </Button>
        {createFramework.isError ? (
          <p role="alert" className="text-xs text-rose-300">
            {createFramework.error.message}
          </p>
        ) : null}
      </div>
    </form>
  )
}
