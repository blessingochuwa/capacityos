import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { ProjectFilterPicker } from '@/features/insights/components/ProjectFilterPicker'
import { useFrameworks } from '@/features/prioritization/hooks/useFrameworks'
import type { MoscowCategory } from '@/features/prioritization/types/prioritization'
import { useSetScenarioPriorityOverride } from '../hooks/useScenarioPriorityOverrideMutations'

const MOSCOW_OPTIONS: { value: MoscowCategory; label: string }[] = [
  { value: 'must', label: 'Must have' },
  { value: 'should', label: 'Should have' },
  { value: 'could', label: 'Could have' },
  { value: 'wont', label: "Won't have (this time)" },
]

/** "What if this project's priority inputs were different?" — a
 * scenario-scoped, hypothetical override (Phase 20). Never touches the
 * project's real, persisted score: creating/replacing an override here
 * only ever affects this one Scenario's own comparison. */
export function PriorityOverrideForm({
  scenarioId,
  onDone,
}: {
  scenarioId: string
  onDone?: () => void
}) {
  const frameworksQuery = useFrameworks(true)
  const [projectId, setProjectId] = useState<string | undefined>(undefined)
  const [frameworkId, setFrameworkId] = useState('')
  const [values, setValues] = useState<Record<string, string>>({})
  const [category, setCategory] = useState<MoscowCategory | ''>('')
  const setOverride = useSetScenarioPriorityOverride(scenarioId)

  const framework = frameworksQuery.data?.items.find((f) => f.id === frameworkId)
  const isMoscow = framework?.framework_type === 'moscow'

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!projectId || !framework) return
    const submittedValues = Object.entries(values)
      .filter(([, value]) => value.trim() !== '')
      .map(([criterion_key, value]) => ({ criterion_key, value: value.trim() }))

    setOverride.mutate(
      {
        project_id: projectId,
        framework_id: framework.id,
        values: isMoscow ? [] : submittedValues,
        category: isMoscow ? category || null : null,
      },
      {
        onSuccess: () => {
          setValues({})
          setCategory('')
          onDone?.()
        },
      },
    )
  }

  const canSubmit =
    projectId !== undefined &&
    framework !== undefined &&
    (isMoscow ? category !== '' : Object.values(values).some((v) => v.trim() !== ''))

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ProjectFilterPicker value={projectId} onChange={setProjectId} />
        <Select
          label="Override framework"
          value={frameworkId}
          placeholder="Select a framework"
          options={(frameworksQuery.data?.items ?? []).map((f) => ({
            value: f.id,
            label: `${f.name} (${f.framework_type.toUpperCase()})`,
          }))}
          onChange={(event) => {
            setFrameworkId(event.target.value)
            setValues({})
            setCategory('')
          }}
        />
      </div>

      {!framework ? null : isMoscow ? (
        <div className="w-64">
          <Select
            label="Hypothetical category"
            value={category}
            placeholder="Select a category"
            options={MOSCOW_OPTIONS}
            onChange={(event) => setCategory(event.target.value as MoscowCategory)}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {framework.criteria.map((criterion) => (
            <div key={criterion.id} className="flex flex-col gap-1">
              <label
                htmlFor={`override-criterion-${criterion.key}`}
                className="text-xs font-medium text-slate-400"
              >
                {criterion.name}
              </label>
              <input
                id={`override-criterion-${criterion.key}`}
                inputMode="decimal"
                value={values[criterion.key] ?? ''}
                onChange={(event) =>
                  setValues((prev) => ({ ...prev, [criterion.key]: event.target.value }))
                }
                placeholder="Leave blank to keep the baseline value"
                className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
              />
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3">
        <Button type="submit" variant="secondary" disabled={!canSubmit || setOverride.isPending}>
          {setOverride.isPending ? 'Saving…' : 'Save hypothetical values'}
        </Button>
        {setOverride.isError ? (
          <p role="alert" className="text-xs text-rose-300">
            {setOverride.error.message}
          </p>
        ) : null}
      </div>
    </form>
  )
}
