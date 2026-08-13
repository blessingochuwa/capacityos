import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import type { Person, Project } from '@/types/entities'
import type { ScenarioOperation } from '../types/scenario'
import { describeOperation, type NameLookup } from '../utils/presentation'

interface ChangeListProps {
  operations: ScenarioOperation[]
  peopleLookup: Map<string, Person>
  projectsLookup: Map<string, Project>
  onDelete: (operationId: string) => void
  deletingOperationId?: string
}

function buildNameLookup(
  operations: ScenarioOperation[],
  peopleLookup: Map<string, Person>,
  projectsLookup: Map<string, Project>,
): NameLookup {
  const hypotheticalLabels = new Map<string, string>()
  for (const operation of operations) {
    if (operation.payload.operation_type === 'add_hypothetical_resource') {
      hypotheticalLabels.set(operation.id, operation.payload.label)
    }
  }
  return {
    personLabel: (personId) =>
      peopleLookup.get(personId)?.display_name ??
      hypotheticalLabels.get(personId) ??
      'Unknown person',
    projectLabel: (projectId) =>
      projectsLookup.get(projectId)?.name ?? 'Unknown project',
  }
}

/** The scenario's change list — each entry in plain language (prompt §16/§17),
 * editable only by removal (adding a replacement) to keep the interaction
 * simple; see docs/adr/0004-phase-4-scenario-planning.md. */
export function ChangeList({
  operations,
  peopleLookup,
  projectsLookup,
  onDelete,
  deletingOperationId,
}: ChangeListProps) {
  if (operations.length === 0) {
    return (
      <EmptyState
        title="No changes yet."
        description="Add a hypothetical change below — an allocation, a availability change, or a hypothetical resource — to see its effect on capacity."
      />
    )
  }

  const names = buildNameLookup(operations, peopleLookup, projectsLookup)

  return (
    <ul className="divide-y divide-slate-800">
      {operations.map((operation) => (
        <li
          key={operation.id}
          className="flex items-center justify-between gap-3 py-2.5 text-sm"
        >
          <span className="text-slate-200">
            {describeOperation(operation, names)}
          </span>
          <Button
            variant="ghost"
            onClick={() => onDelete(operation.id)}
            disabled={deletingOperationId === operation.id}
            aria-label="Remove this change"
          >
            Remove
          </Button>
        </li>
      ))}
    </ul>
  )
}
