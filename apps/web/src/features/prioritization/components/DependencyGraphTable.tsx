import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import type { DependencyGraph } from '../types/prioritization'

/** The organization-wide Dependency Graph view (Phase 18) — a flat
 * from/relationship/to table, not a node-link diagram: CLAUDE.md §29
 * forbids decorative charts and this codebase adds no new charting
 * library for it (see docs/PRD-phase-17-prioritization.md §7 and
 * docs/adr/0018). Every edge already names both of its projects, so a
 * table answers "what depends on what" exactly as directly as a canvas
 * drawing would, without the added complexity or a11y cost of one. */
export function DependencyGraphTable({ graph }: { graph: DependencyGraph }) {
  if (graph.edges.length === 0) {
    return (
      <EmptyState
        title="No project dependencies recorded yet."
        description="Add a dependency from a project below to see it here."
      />
    )
  }

  return (
    <Table caption="Organization-wide dependency graph">
      <thead>
        <tr>
          <Th scope="col">From project</Th>
          <Th scope="col">Relationship</Th>
          <Th scope="col">To project</Th>
        </tr>
      </thead>
      <tbody>
        {graph.edges.map((edge) => (
          <tr key={edge.id}>
            <Td className="font-medium text-slate-200">{edge.from_project_name}</Td>
            <Td>
              <Badge variant="neutral">{edge.dependency_type}</Badge>
            </Td>
            <Td className="font-medium text-slate-200">{edge.to_project_name}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
