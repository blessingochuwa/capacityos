import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { DateField } from '@/components/ui/DateField'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Table, Td, Th } from '@/components/ui/Table'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { formatDateRange } from '@/features/capacity/utils/presentation'
import { thisWeek } from '@/features/capacity/utils/dateRange'
import { useCreateScenario } from '../hooks/useScenarioMutations'
import { useScenarios } from '../hooks/useScenarios'
import { ScenarioStatusBadge } from '../components/ScenarioStatusBadge'

const DEFAULT_RANGE = thisWeek()

/** "What if we accept this work?" (CLAUDE.md §38) — the entry point into
 * scenario planning. Every scenario listed here is a saved what-if
 * exercise; none of them are live plans (see ScenarioBanner in the
 * workspace for the same distinction made explicit there too). */
export function ScenarioListPage() {
  const navigate = useNavigate()
  const { can } = useAuth()
  const canCreate = can('scenario.write')
  const scenariosQuery = useScenarios()
  const createScenario = useCreateScenario()

  const [name, setName] = useState('')
  const [start, setStart] = useState(DEFAULT_RANGE.start)
  const [end, setEnd] = useState(DEFAULT_RANGE.end)
  const [formError, setFormError] = useState<string | null>(null)

  function handleCreate(event: React.FormEvent) {
    event.preventDefault()
    if (!name.trim()) {
      setFormError('Give the scenario a name.')
      return
    }
    setFormError(null)
    createScenario.mutate(
      { name: name.trim(), baseline_start_date: start, baseline_end_date: end },
      {
        onSuccess: (scenario) => navigate(`/scenarios/${scenario.id}`),
        onError: (error) => setFormError(error.message),
      },
    )
  }

  return (
    <div>
      <PageHeader
        title="Scenario Planning"
        description="What happens if we accept this work? Model it here without changing your current plan."
      />

      <Card className="mb-6">
        <CardHeader
          title="New scenario"
          description="Give it a name and a baseline period to plan against."
        />
        <CardBody>
          {canCreate ? (
            <>
              <form
                onSubmit={handleCreate}
                className="flex flex-wrap items-end gap-3"
              >
                <label className="flex min-w-48 flex-1 flex-col gap-1">
                  <span className="text-xs font-medium text-slate-400">
                    Name
                  </span>
                  <input
                    type="text"
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="e.g. Launch campaign earlier"
                    className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100"
                  />
                </label>
                <DateField
                  label="Baseline start"
                  value={start}
                  onChange={(event) => setStart(event.target.value)}
                />
                <DateField
                  label="Baseline end"
                  value={end}
                  onChange={(event) => setEnd(event.target.value)}
                />
                <Button
                  type="submit"
                  variant="primary"
                  disabled={createScenario.isPending}
                >
                  {createScenario.isPending ? 'Creating…' : 'Create scenario'}
                </Button>
              </form>
              {formError ? (
                <p className="mt-2 text-xs text-rose-300">{formError}</p>
              ) : null}
            </>
          ) : (
            <ViewOnlyNotice message="Your role can view scenarios but not create new ones." />
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Scenarios"
          description="Every what-if exercise saved so far."
        />
        <CardBody>
          <QueryBoundary
            query={scenariosQuery}
            loadingLabel="Loading scenarios…"
          >
            {(page) =>
              page.items.length === 0 ? (
                <EmptyState
                  title="No scenarios yet."
                  description="Create one above to start exploring a what-if question."
                />
              ) : (
                <Table caption="Saved scenarios">
                  <thead>
                    <tr>
                      <Th scope="col">Name</Th>
                      <Th scope="col">Status</Th>
                      <Th scope="col">Baseline period</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {page.items.map((scenario) => (
                      <tr key={scenario.id}>
                        <Td>
                          <Link
                            to={`/scenarios/${scenario.id}`}
                            className="font-medium text-indigo-300 hover:text-indigo-200"
                          >
                            {scenario.name}
                          </Link>
                        </Td>
                        <Td>
                          <ScenarioStatusBadge status={scenario.status} />
                        </Td>
                        <Td>
                          {formatDateRange(
                            scenario.baseline_start_date,
                            scenario.baseline_end_date,
                          )}
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )
            }
          </QueryBoundary>
        </CardBody>
      </Card>
    </div>
  )
}
