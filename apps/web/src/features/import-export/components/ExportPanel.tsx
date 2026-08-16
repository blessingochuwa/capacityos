import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { usePeople } from '@/hooks/usePeople'
import { useProjects } from '@/hooks/useProjects'
import { useTeams } from '@/hooks/useTeams'
import { EntityTypePicker } from './EntityTypePicker'
import { useExportEntities } from '../hooks/useExportEntities'
import type { ExportFormat, ImportEntityType } from '../types/importExport'

const FORMAT_OPTIONS: { value: ExportFormat; label: string }[] = [
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
]

/** Which entity types accept which scope filter — mirrors
 * ExportService._collect_rows exactly (apps/api/app/services/export_service.py).
 * Everything else exports unscoped (capped at Settings.export_max_rows). */
function scopeFieldFor(
  entityType: ImportEntityType,
): 'team' | 'person' | 'person_and_project' | null {
  if (entityType === 'team_membership') return 'team'
  if (entityType === 'working_schedule' || entityType === 'availability_exception') {
    return 'person'
  }
  if (entityType === 'allocation') return 'person_and_project'
  return null
}

export function ExportPanel() {
  const [entityType, setEntityType] = useState<ImportEntityType>('person')
  const [format, setFormat] = useState<ExportFormat>('csv')
  const [personId, setPersonId] = useState('')
  const [teamId, setTeamId] = useState('')
  const [projectId, setProjectId] = useState('')

  const peopleQuery = usePeople()
  const teamsQuery = useTeams()
  const projectsQuery = useProjects()
  const exportEntities = useExportEntities()

  const scopeField = scopeFieldFor(entityType)

  function handleExport() {
    exportEntities.mutate({
      entityType,
      format,
      scope: {
        person_id:
          scopeField === 'person' || scopeField === 'person_and_project'
            ? personId || undefined
            : undefined,
        team_id: scopeField === 'team' ? teamId || undefined : undefined,
        project_id:
          scopeField === 'person_and_project' ? projectId || undefined : undefined,
      },
    })
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <EntityTypePicker value={entityType} onChange={setEntityType} />
        <Select
          label="Format"
          value={format}
          onChange={(event) => setFormat(event.target.value as ExportFormat)}
          options={FORMAT_OPTIONS}
        />
      </div>

      {scopeField === 'team' ? (
        <Select
          label="Team"
          value={teamId}
          placeholder="All teams"
          onChange={(event) => setTeamId(event.target.value)}
          options={(teamsQuery.data?.items ?? []).map((team) => ({
            value: team.id,
            label: team.name,
          }))}
        />
      ) : null}

      {scopeField === 'person' || scopeField === 'person_and_project' ? (
        <Select
          label="Person"
          value={personId}
          placeholder="All people"
          onChange={(event) => setPersonId(event.target.value)}
          options={(peopleQuery.data?.items ?? []).map((person) => ({
            value: person.id,
            label: person.display_name,
          }))}
        />
      ) : null}

      {scopeField === 'person_and_project' ? (
        <Select
          label="Project"
          value={projectId}
          placeholder="All projects"
          onChange={(event) => setProjectId(event.target.value)}
          options={(projectsQuery.data?.items ?? []).map((project) => ({
            value: project.id,
            label: project.name,
          }))}
        />
      ) : null}

      <Button
        variant="primary"
        onClick={handleExport}
        disabled={exportEntities.isPending}
      >
        {exportEntities.isPending ? 'Exporting…' : 'Export'}
      </Button>

      {exportEntities.isError ? (
        <p role="alert" className="text-sm text-rose-300">
          Export failed. Try again.
        </p>
      ) : null}
      {exportEntities.isSuccess ? (
        <p className="text-sm text-emerald-300">Downloaded.</p>
      ) : null}
    </div>
  )
}
