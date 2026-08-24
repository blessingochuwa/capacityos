import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Select } from '@/components/ui/Select'
import { Table, Td, Th } from '@/components/ui/Table'
import { useProjects } from '@/hooks/useProjects'
import { useCreateDependency, useDeleteDependency } from '../hooks/useDependencyMutations'
import { useProjectDependencies } from '../hooks/useProjectDependencies'
import type { ProjectDependencyType } from '../types/prioritization'

const DEPENDENCY_TYPE_OPTIONS: { value: ProjectDependencyType; label: string }[] = [
  { value: 'blocks', label: 'Blocks' },
  { value: 'related', label: 'Related to' },
  { value: 'enables', label: 'Enables' },
]

/** Create and remove ProjectDependency edges for one "from" project at a
 * time (Phase 18) — a dependency is only ever created/deleted through
 * its from_project's URL (see ProjectDependencyCreate's docstring), so
 * this component always operates against the currently selected
 * fromProjectId, matching require_project_access's own project_id path
 * parameter. */
export function DependencyManager({
  canManage,
  fromProjectId,
  onFromProjectChange,
}: {
  canManage: boolean
  fromProjectId: string | undefined
  onFromProjectChange: (projectId: string | undefined) => void
}) {
  const { data: projects } = useProjects()
  const [toProjectId, setToProjectId] = useState('')
  const [dependencyType, setDependencyType] = useState<ProjectDependencyType>('blocks')

  const dependenciesQuery = useProjectDependencies(fromProjectId)
  const createDependency = useCreateDependency(fromProjectId ?? '')
  const deleteDependency = useDeleteDependency(fromProjectId ?? '')

  const projectOptions = (projects?.items ?? []).map((project) => ({
    value: project.id,
    label: project.name,
  }))

  function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!fromProjectId || !toProjectId) return
    createDependency.mutate(
      { to_project_id: toProjectId, dependency_type: dependencyType },
      { onSuccess: () => setToProjectId('') },
    )
  }

  return (
    <div className="space-y-4">
      <div className="w-64">
        <Select
          label="Project"
          value={fromProjectId ?? ''}
          placeholder="Select a project"
          options={projectOptions}
          onChange={(event) => onFromProjectChange(event.target.value || undefined)}
        />
      </div>

      {!fromProjectId ? null : (
        <>
          {canManage ? (
            <form onSubmit={handleCreate} className="flex flex-wrap items-end gap-3">
              <div className="w-56">
                <Select
                  label="Depends on / relates to"
                  value={toProjectId}
                  placeholder="Select a project"
                  options={projectOptions.filter((option) => option.value !== fromProjectId)}
                  onChange={(event) => setToProjectId(event.target.value)}
                />
              </div>
              <div className="w-40">
                <Select
                  label="Relationship"
                  value={dependencyType}
                  options={DEPENDENCY_TYPE_OPTIONS}
                  onChange={(event) =>
                    setDependencyType(event.target.value as ProjectDependencyType)
                  }
                />
              </div>
              <Button type="submit" variant="secondary" disabled={createDependency.isPending}>
                Add dependency
              </Button>
              {createDependency.isError ? (
                <p role="alert" className="text-xs text-rose-300">
                  {createDependency.error.message}
                </p>
              ) : null}
            </form>
          ) : null}

          {dependenciesQuery.isPending ? (
            <p className="text-sm text-slate-400">Loading dependencies…</p>
          ) : dependenciesQuery.isError ? (
            <p className="text-sm text-rose-300">{dependenciesQuery.error.message}</p>
          ) : dependenciesQuery.data.length === 0 ? (
            <EmptyState title="This project has no recorded dependencies." />
          ) : (
            <Table caption="Project dependencies">
              <thead>
                <tr>
                  <Th scope="col">From</Th>
                  <Th scope="col">Relationship</Th>
                  <Th scope="col">To</Th>
                  {canManage ? <Th scope="col">Actions</Th> : null}
                </tr>
              </thead>
              <tbody>
                {dependenciesQuery.data.map((dependency) => (
                  <tr key={dependency.id}>
                    <Td>{dependency.from_project_name}</Td>
                    <Td>
                      <Badge variant="neutral">{dependency.dependency_type}</Badge>
                    </Td>
                    <Td>{dependency.to_project_name}</Td>
                    {canManage ? (
                      <Td>
                        {dependency.from_project_id === fromProjectId ? (
                          <Button
                            type="button"
                            variant="ghost"
                            onClick={() => deleteDependency.mutate(dependency.id)}
                            disabled={deleteDependency.isPending}
                          >
                            Remove
                          </Button>
                        ) : null}
                      </Td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </>
      )}
    </div>
  )
}
