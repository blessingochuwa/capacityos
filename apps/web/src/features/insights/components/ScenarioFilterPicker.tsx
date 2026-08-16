import { useScenarios } from '@/features/scenarios/hooks/useScenarios'
import { Select } from '@/components/ui/Select'

interface ScenarioFilterPickerProps {
  value: string | undefined
  onChange: (scenarioId: string | undefined) => void
}

/** An optional filter — no scenario selected means "baseline only," never a
 * blocking requirement (CLAUDE.md §19: a scenario is hypothetical). */
export function ScenarioFilterPicker({
  value,
  onChange,
}: ScenarioFilterPickerProps) {
  const { data, isPending, isError } = useScenarios()

  if (isPending || isError || !data) {
    return (
      <Select
        label="Scenario"
        options={[]}
        placeholder="Baseline only"
        disabled
        value=""
        onChange={() => {}}
      />
    )
  }

  return (
    <Select
      label="Scenario"
      value={value ?? ''}
      placeholder="Baseline only"
      options={data.items.map((scenario) => ({
        value: scenario.id,
        label: scenario.name,
      }))}
      onChange={(event) => onChange(event.target.value || undefined)}
    />
  )
}
