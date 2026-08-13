import { useMemo, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { DateField } from '@/components/ui/DateField'
import { Select } from '@/components/ui/Select'
import { usePersonAllocations } from '@/features/capacity/hooks/usePersonAllocations'
import {
  formatDateRange,
  formatHours,
} from '@/features/capacity/utils/presentation'
import type { Person, Project } from '@/types/entities'
import { useCreateScenarioOperation } from '../hooks/useScenarioOperationMutations'
import type {
  ScenarioOperation,
  ScenarioOperationPayload,
  ScenarioOperationType,
} from '../types/scenario'

const OPERATION_LABELS: Record<ScenarioOperationType, string> = {
  add_allocation: 'Add hours to someone',
  adjust_allocation: 'Change an existing allocation',
  remove_allocation: 'Remove an allocation',
  move_allocation: 'Move hours between people',
  shift_project: 'Shift a project earlier or later',
  availability_override: 'Make someone unavailable / partially available',
  availability_clear: 'Restore someone to their normal schedule',
  add_hypothetical_resource: 'Add a hypothetical person',
}

interface AddChangeFormProps {
  scenarioId: string
  people: Person[]
  projects: Project[]
  operations: ScenarioOperation[]
  defaultStartDate: string
  defaultEndDate: string
}

interface HypotheticalOption {
  id: string
  label: string
}

/** One form for all 8 operation types (prompt §11: scenarios are
 * composable, multiple change types in one scenario) — fields shown depend
 * on the selected kind of change. Submits directly to
 * POST /scenarios/{id}/operations; the backend is the sole validator
 * (person/project/allocation existence, hours limits — CLAUDE.md §32). */
export function AddChangeForm({
  scenarioId,
  people,
  projects,
  operations,
  defaultStartDate,
  defaultEndDate,
}: AddChangeFormProps) {
  const [operationType, setOperationType] =
    useState<ScenarioOperationType>('add_allocation')
  const [personId, setPersonId] = useState('')
  const [projectId, setProjectId] = useState('')
  const [allocationId, setAllocationId] = useState('')
  const [toPersonId, setToPersonId] = useState('')
  const [hours, setHours] = useState('')
  const [startDate, setStartDate] = useState(defaultStartDate)
  const [endDate, setEndDate] = useState(defaultEndDate)
  const [dayOffset, setDayOffset] = useState('')
  const [label, setLabel] = useState('')
  const [hoursPerWeek, setHoursPerWeek] = useState('40')
  const [error, setError] = useState<string | null>(null)

  const create = useCreateScenarioOperation(scenarioId)

  const hypotheticalResources: HypotheticalOption[] = useMemo(
    () =>
      operations
        .filter(
          (op) => op.payload.operation_type === 'add_hypothetical_resource',
        )
        .map((op) => ({
          id: op.id,
          label:
            op.payload.operation_type === 'add_hypothetical_resource'
              ? op.payload.label
              : '',
        })),
    [operations],
  )

  const personOptions = [
    ...people.map((person) => ({
      value: person.id,
      label: person.display_name,
    })),
    ...hypotheticalResources.map((resource) => ({
      value: resource.id,
      label: `${resource.label} (hypothetical)`,
    })),
  ]
  const projectOptions = projects.map((project) => ({
    value: project.id,
    label: project.name,
  }))

  const allocationsQuery = usePersonAllocations(personId || undefined)
  const allocationOptions = (allocationsQuery.data?.items ?? []).map(
    (allocation) => ({
      value: allocation.id,
      label: `${formatHours(allocation.allocation_hours)} on ${
        projects.find((p) => p.id === allocation.project_id)?.name ??
        'a project'
      } (${formatDateRange(allocation.start_date, allocation.end_date)})`,
    }),
  )

  function reset() {
    setPersonId('')
    setProjectId('')
    setAllocationId('')
    setToPersonId('')
    setHours('')
    setDayOffset('')
    setLabel('')
    setHoursPerWeek('40')
    setStartDate(defaultStartDate)
    setEndDate(defaultEndDate)
  }

  function buildPayload(): ScenarioOperationPayload | null {
    switch (operationType) {
      case 'add_allocation':
        if (!personId || !projectId || !hours) return null
        return {
          operation_type: 'add_allocation',
          person_id: personId,
          project_id: projectId,
          hours,
          start_date: startDate,
          end_date: endDate,
        }
      case 'adjust_allocation':
        // This quick-add form only exposes an hours change for
        // adjust_allocation; date changes on an existing allocation are
        // available via the API (start_date/end_date on the payload) but
        // not yet surfaced here — see AddChangeForm's scope note above.
        if (!allocationId || !hours) return null
        return {
          operation_type: 'adjust_allocation',
          allocation_id: allocationId,
          hours,
          start_date: null,
          end_date: null,
        }
      case 'remove_allocation':
        if (!allocationId) return null
        return {
          operation_type: 'remove_allocation',
          allocation_id: allocationId,
        }
      case 'move_allocation':
        if (!allocationId || !toPersonId) return null
        return {
          operation_type: 'move_allocation',
          allocation_id: allocationId,
          to_person_id: toPersonId,
          hours: hours || null,
        }
      case 'shift_project':
        if (!projectId || !dayOffset) return null
        return {
          operation_type: 'shift_project',
          project_id: projectId,
          day_offset: Number(dayOffset),
        }
      case 'availability_override':
        if (!personId || !startDate || !endDate) return null
        return {
          operation_type: 'availability_override',
          person_id: personId,
          start_date: startDate,
          end_date: endDate,
          hours: hours || null,
        }
      case 'availability_clear':
        if (!personId || !startDate || !endDate) return null
        return {
          operation_type: 'availability_clear',
          person_id: personId,
          start_date: startDate,
          end_date: endDate,
        }
      case 'add_hypothetical_resource':
        if (!label || !hoursPerWeek || !startDate || !endDate) return null
        return {
          operation_type: 'add_hypothetical_resource',
          label,
          hours_per_week: hoursPerWeek,
          start_date: startDate,
          end_date: endDate,
        }
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const payload = buildPayload()
    if (!payload) {
      setError('Fill in the required fields for this change.')
      return
    }
    setError(null)
    create.mutate(payload, {
      onSuccess: () => reset(),
      onError: (mutationError) => setError(mutationError.message),
    })
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <Select
        label="What kind of change?"
        value={operationType}
        onChange={(event) => {
          setOperationType(event.target.value as ScenarioOperationType)
          setError(null)
        }}
        options={Object.entries(OPERATION_LABELS).map(([value, opLabel]) => ({
          value,
          label: opLabel,
        }))}
      />

      {(operationType === 'add_allocation' ||
        operationType === 'availability_override' ||
        operationType === 'availability_clear') && (
        <Select
          label="Person"
          value={personId}
          onChange={(event) => setPersonId(event.target.value)}
          options={personOptions}
          placeholder="Select a person"
        />
      )}

      {(operationType === 'adjust_allocation' ||
        operationType === 'remove_allocation' ||
        operationType === 'move_allocation') && (
        <>
          <Select
            label="Whose allocation?"
            value={personId}
            onChange={(event) => {
              setPersonId(event.target.value)
              setAllocationId('')
            }}
            options={people.map((person) => ({
              value: person.id,
              label: person.display_name,
            }))}
            placeholder="Select a person"
          />
          <Select
            label="Which allocation?"
            value={allocationId}
            onChange={(event) => setAllocationId(event.target.value)}
            options={allocationOptions}
            placeholder={
              personId ? 'Select an allocation' : 'Select a person first'
            }
            disabled={!personId}
          />
        </>
      )}

      {operationType === 'move_allocation' && (
        <Select
          label="Move to"
          value={toPersonId}
          onChange={(event) => setToPersonId(event.target.value)}
          options={personOptions}
          placeholder="Select a person"
        />
      )}

      {(operationType === 'add_allocation' ||
        operationType === 'shift_project') && (
        <Select
          label="Project"
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
          options={projectOptions}
          placeholder="Select a project"
        />
      )}

      {(operationType === 'add_allocation' ||
        operationType === 'adjust_allocation' ||
        operationType === 'move_allocation' ||
        operationType === 'availability_override') && (
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-slate-400">
            {operationType === 'availability_override'
              ? 'Hours available per day'
              : 'Hours'}
          </span>
          <input
            type="number"
            min="0"
            step="0.25"
            value={hours}
            onChange={(event) => setHours(event.target.value)}
            placeholder={
              operationType === 'availability_override'
                ? 'Blank = fully unavailable'
                : ''
            }
            className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100"
          />
        </label>
      )}

      {operationType === 'shift_project' && (
        <label className="flex flex-col gap-1">
          <span className="text-xs font-medium text-slate-400">
            Days earlier (negative) or later (positive)
          </span>
          <input
            type="number"
            step="1"
            value={dayOffset}
            onChange={(event) => setDayOffset(event.target.value)}
            className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100"
          />
        </label>
      )}

      {operationType === 'add_hypothetical_resource' && (
        <>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-400">Label</span>
            <input
              type="text"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="e.g. Senior Designer"
              className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-slate-400">
              Hours per week
            </span>
            <input
              type="number"
              min="0"
              max="168"
              step="0.5"
              value={hoursPerWeek}
              onChange={(event) => setHoursPerWeek(event.target.value)}
              className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100"
            />
          </label>
        </>
      )}

      {(operationType === 'add_allocation' ||
        operationType === 'availability_override' ||
        operationType === 'availability_clear' ||
        operationType === 'add_hypothetical_resource') && (
        <div className="grid grid-cols-2 gap-3">
          <DateField
            label="Start date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
          <DateField
            label="End date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </div>
      )}

      {error ? <p className="text-xs text-rose-300">{error}</p> : null}

      <Button type="submit" variant="primary" disabled={create.isPending}>
        {create.isPending ? 'Adding…' : 'Add change'}
      </Button>
    </form>
  )
}
