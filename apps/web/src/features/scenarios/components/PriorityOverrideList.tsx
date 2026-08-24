import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { useDeleteScenarioPriorityOverride } from '../hooks/useScenarioPriorityOverrideMutations'
import type { ScenarioPriorityOverride } from '../types/scenarioPriority'

export function PriorityOverrideList({
  scenarioId,
  overrides,
}: {
  scenarioId: string
  overrides: ScenarioPriorityOverride[]
}) {
  const deleteOverride = useDeleteScenarioPriorityOverride(scenarioId)

  if (overrides.length === 0) {
    return (
      <EmptyState
        title="No hypothetical prioritization values recorded for this scenario yet."
        description="Add one above to see it reflected in the comparison below."
      />
    )
  }

  return (
    <Table caption="This scenario's hypothetical prioritization overrides">
      <thead>
        <tr>
          <Th scope="col">Project</Th>
          <Th scope="col">Framework</Th>
          <Th scope="col">Hypothetical values</Th>
          <Th scope="col">Actions</Th>
        </tr>
      </thead>
      <tbody>
        {overrides.map((override) => (
          <tr key={override.id}>
            <Td>{override.project_name}</Td>
            <Td>{override.framework_name}</Td>
            <Td>
              {override.category !== null
                ? `Category: ${override.category}`
                : Object.entries(override.values)
                    .map(([key, value]) => `${key}=${value}`)
                    .join(', ')}
            </Td>
            <Td>
              <Button
                type="button"
                variant="ghost"
                onClick={() => deleteOverride.mutate(override.id)}
                disabled={deleteOverride.isPending}
              >
                Remove
              </Button>
            </Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
