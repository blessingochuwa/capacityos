import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Select } from '@/components/ui/Select'
import { Skeleton } from '@/components/ui/Skeleton'
import { usePeople, usePeopleLookup } from '@/hooks/usePeople'
import { useProjects, useProjectsLookup } from '@/hooks/useProjects'
import { formatDateRange } from '@/features/capacity/utils/presentation'
import { SignalList } from '@/features/insights/components/SignalList'
import { useScenarioSignals } from '@/features/insights/hooks/useScenarioSignals'
import { AddChangeForm } from '../components/AddChangeForm'
import { ChangeList } from '../components/ChangeList'
import { ComparisonTable } from '../components/ComparisonTable'
import { ImpactSummary } from '../components/ImpactSummary'
import { PeopleComparisonTable } from '../components/PeopleComparisonTable'
import { RiskList } from '../components/RiskList'
import { ScenarioBanner } from '../components/ScenarioBanner'
import { ScenarioStatusBadge } from '../components/ScenarioStatusBadge'
import { useCalculateScenario } from '../hooks/useCalculateScenario'
import { useScenario } from '../hooks/useScenario'
import { useScenarioComparison } from '../hooks/useScenarioComparison'
import {
  useDeleteScenario,
  useUpdateScenario,
} from '../hooks/useScenarioMutations'
import { useDeleteScenarioOperation } from '../hooks/useScenarioOperationMutations'
import { useScenarioOperations } from '../hooks/useScenarioOperations'
import type { ScenarioStatus } from '../types/scenario'

const STATUS_OPTIONS: { value: ScenarioStatus; label: string }[] = [
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'archived', label: 'Archived' },
]

export function ScenarioWorkspacePage() {
  const { scenarioId } = useParams<{ scenarioId: string }>()
  // key={scenarioId} forces a full remount (resetting confirmingDelete/
  // hasCalculatedOnce/calculatedAt/autoCalculateTriggered) when navigating
  // directly between two different scenarios' workspaces — React Router
  // reuses the component instance for the same route pattern, so without
  // this, local state from the previous scenario would leak into the next.
  if (!scenarioId) return null
  return <ScenarioWorkspaceContent key={scenarioId} scenarioId={scenarioId} />
}

function ScenarioWorkspaceContent({ scenarioId }: { scenarioId: string }) {
  const navigate = useNavigate()

  const peopleLookup = usePeopleLookup()
  const projectsLookup = useProjectsLookup()
  const peopleQuery = usePeople()
  const projectsQuery = useProjects()

  const deleteOperation = useDeleteScenarioOperation(scenarioId)
  const updateScenario = useUpdateScenario(scenarioId)
  const deleteScenario = useDeleteScenario()
  const calculate = useCalculateScenario(scenarioId)

  // A STICKY flag, not derived from deleteScenario.isPending — isPending is
  // transient and flips back to false the moment the DELETE response
  // arrives, which can happen before this component has actually unmounted
  // (navigate() runs in the mutation's onSuccess, one render later). A
  // pageActive derived from isPending briefly flips back to true in that
  // window, re-enabling these queries just as their cache was cleared
  // (useDeleteScenario's onSuccess), which fires a real fetch against a
  // scenario that no longer exists and logs a 404. Setting this the instant
  // "Confirm delete" is clicked, and never clearing it, closes that window
  // entirely. Caught by driving the app in a real browser and watching
  // actual network timing, not by the (mocked-hooks) unit tests.
  const [deletionInitiated, setDeletionInitiated] = useState(false)
  const pageActive = !deletionInitiated

  const scenarioQuery = useScenario(scenarioId, pageActive)
  const operationsQuery = useScenarioOperations(scenarioId, pageActive)

  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const [hasCalculatedOnce, setHasCalculatedOnce] = useState(false)
  const [calculatedAt, setCalculatedAt] = useState<number | null>(null)

  const comparisonQuery = useScenarioComparison(
    scenarioId,
    hasCalculatedOnce && pageActive,
  )
  const scenarioSignalsQuery = useScenarioSignals(
    scenarioId,
    hasCalculatedOnce && pageActive,
  )

  // Tracks hasCalculatedOnce/calculatedAt off calculate.isSuccess itself
  // (a reactive value read fresh every render) rather than the `onSuccess`
  // callback passed to a specific `.mutate()` call. The callback form is
  // one-shot and closure-captured at call time — React 18/19 StrictMode
  // double-invokes the auto-calculate effect below in development, and
  // the callback attached to the mutate() call from the discarded first
  // invocation never fired once React settled on the second, so
  // hasCalculatedOnce silently never flipped even though the network
  // request itself succeeded (visible in the Network tab, invisible in
  // the UI — "Calculating…" forever). Caught by driving the app in a real
  // browser and watching both the network log and a debug trace, not by
  // the (mocked-hooks) unit tests.
  useEffect(() => {
    if (calculate.isSuccess) {
      setHasCalculatedOnce(true)
      setCalculatedAt(Date.now())
    }
  }, [calculate.isSuccess])

  // Auto-calculate once when a scenario that already has changes is opened
  // (e.g. returning to it later) — never on subsequent edits, which only
  // mark the view stale until the user explicitly clicks Calculate again
  // (prompt §13). autoCalculateTriggered is a ref, set SYNCHRONOUSLY inside
  // the effect body so StrictMode's double-invocation (state/refs persist
  // across it, only the effect body runs twice) can't fire a second,
  // redundant POST /calculate.
  //
  // KNOWN LIMITATION (development only): with React StrictMode active,
  // reopening a scenario that already has changes can occasionally leave
  // this stuck on the "Calculating…" skeleton — the POST /calculate
  // request itself succeeds (visible in the Network tab), but this
  // component doesn't observe the mutation's success on that particular
  // remount. Root-caused to StrictMode's synthetic double-invocation of
  // this effect interacting with TanStack Query's mutation observer
  // lifecycle, not to app state logic — confirmed by running the exact
  // same flow with StrictMode removed, where it completes correctly every
  // time with zero console errors. Clicking "Calculate" again (a click
  // handler, never double-invoked by StrictMode) always recovers it. Not
  // reproducible in a production build, where StrictMode's double-invoke
  // behavior doesn't exist. Left as a documented gap rather than worked
  // around, to avoid masking a real TanStack Query/StrictMode interaction
  // with something that only hides the symptom.
  const autoCalculateTriggered = useRef(false)
  useEffect(() => {
    if (
      !autoCalculateTriggered.current &&
      !hasCalculatedOnce &&
      operationsQuery.data &&
      operationsQuery.data.total > 0
    ) {
      autoCalculateTriggered.current = true
      calculate.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [operationsQuery.data, hasCalculatedOnce])

  const isStale =
    hasCalculatedOnce &&
    calculatedAt !== null &&
    operationsQuery.dataUpdatedAt > calculatedAt

  function handleCalculate() {
    calculate.mutate()
  }

  function handleDeleteScenario() {
    setDeletionInitiated(true)
    deleteScenario.mutate(scenarioId, {
      onSuccess: () => navigate('/scenarios'),
    })
  }

  return (
    <div>
      <p className="mb-2 text-sm">
        <Link to="/scenarios" className="text-slate-400 hover:text-slate-200">
          ← Back to Scenarios
        </Link>
      </p>

      <QueryBoundary query={scenarioQuery} loadingLabel="Loading scenario…">
        {(scenario) => (
          <>
            <PageHeader
              title={scenario.name}
              description={scenario.description ?? undefined}
              action={
                <div className="flex items-center gap-2">
                  <Select
                    label="Status"
                    value={scenario.status}
                    onChange={(event) =>
                      updateScenario.mutate({
                        status: event.target.value as ScenarioStatus,
                      })
                    }
                    options={STATUS_OPTIONS}
                    className="w-32"
                  />
                  {confirmingDelete ? (
                    <>
                      <span className="text-xs text-slate-400">
                        Delete this scenario?
                      </span>
                      <Button
                        variant="secondary"
                        onClick={handleDeleteScenario}
                        disabled={deleteScenario.isPending}
                      >
                        Confirm delete
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => setConfirmingDelete(false)}
                      >
                        Cancel
                      </Button>
                    </>
                  ) : (
                    <Button
                      variant="ghost"
                      onClick={() => setConfirmingDelete(true)}
                    >
                      Delete scenario
                    </Button>
                  )}
                </div>
              }
            />

            <div className="mb-6 flex flex-wrap items-center gap-3">
              <ScenarioBanner />
              <ScenarioStatusBadge status={scenario.status} />
              <span className="text-xs text-slate-400">
                Baseline:{' '}
                {formatDateRange(
                  scenario.baseline_start_date,
                  scenario.baseline_end_date,
                )}
              </span>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader
                  title="Changes"
                  description="What's different from your current plan, in this scenario only."
                />
                <CardBody className="space-y-4">
                  <QueryBoundary
                    query={operationsQuery}
                    loadingLabel="Loading changes…"
                  >
                    {(operationsPage) => (
                      <ChangeList
                        operations={operationsPage.items}
                        peopleLookup={peopleLookup}
                        projectsLookup={projectsLookup}
                        onDelete={(operationId) =>
                          deleteOperation.mutate(operationId)
                        }
                        deletingOperationId={
                          deleteOperation.isPending
                            ? deleteOperation.variables
                            : undefined
                        }
                      />
                    )}
                  </QueryBoundary>

                  <div className="border-t border-slate-800 pt-4">
                    <QueryBoundary query={peopleQuery} loadingLabel="Loading…">
                      {(peoplePage) => (
                        <QueryBoundary
                          query={projectsQuery}
                          loadingLabel="Loading…"
                        >
                          {(projectsPage) => (
                            <AddChangeForm
                              scenarioId={scenarioId}
                              people={peoplePage.items}
                              projects={projectsPage.items}
                              operations={operationsQuery.data?.items ?? []}
                              defaultStartDate={scenario.baseline_start_date}
                              defaultEndDate={scenario.baseline_end_date}
                            />
                          )}
                        </QueryBoundary>
                      )}
                    </QueryBoundary>
                  </div>
                </CardBody>
              </Card>

              <Card>
                <CardHeader
                  title="Baseline vs scenario"
                  description="Calculate to see the effect of every change above."
                  action={
                    <Button
                      variant="primary"
                      onClick={handleCalculate}
                      disabled={calculate.isPending}
                    >
                      {calculate.isPending ? 'Calculating…' : 'Calculate'}
                    </Button>
                  }
                />
                <CardBody className="space-y-4">
                  {isStale ? (
                    <p className="rounded-md bg-amber-950/40 px-3 py-2 text-xs text-amber-200">
                      Changes since the last calculation aren't reflected below
                      yet — click Calculate to refresh.
                    </p>
                  ) : null}
                  {!hasCalculatedOnce ? (
                    calculate.isPending ? (
                      <Skeleton className="h-40 w-full" />
                    ) : (
                      <p className="text-sm text-slate-400">
                        Add a change and click Calculate to see baseline vs
                        scenario capacity.
                      </p>
                    )
                  ) : (
                    <QueryBoundary
                      query={comparisonQuery}
                      loadingLabel="Calculating…"
                    >
                      {(comparison) => (
                        <div className="space-y-6">
                          <ComparisonTable aggregate={comparison.aggregate} />
                          <div>
                            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                              Impact
                            </h3>
                            <ImpactSummary impact={comparison.impact} />
                          </div>
                          <div>
                            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                              Risks
                            </h3>
                            <RiskList risks={comparison.risks} />
                          </div>
                        </div>
                      )}
                    </QueryBoundary>
                  )}
                </CardBody>
              </Card>
            </div>

            {hasCalculatedOnce ? (
              <Card className="mt-6">
                <CardHeader
                  title="People"
                  description="Every person this scenario affects, baseline vs scenario."
                />
                <CardBody>
                  <QueryBoundary
                    query={comparisonQuery}
                    loadingLabel="Calculating…"
                  >
                    {(comparison) =>
                      comparison.people.length === 0 ? (
                        <p className="text-sm text-slate-400">
                          No people affected yet.
                        </p>
                      ) : (
                        <PeopleComparisonTable people={comparison.people} />
                      )
                    }
                  </QueryBoundary>
                </CardBody>
              </Card>
            ) : null}

            {hasCalculatedOnce ? (
              <Card className="mt-6">
                <CardHeader
                  title="Operational signals"
                  description="Severity-classified, explained versions of the risks above (CLAUDE.md §39 Phase 5)."
                />
                <CardBody>
                  <QueryBoundary
                    query={scenarioSignalsQuery}
                    loadingLabel="Loading signals…"
                  >
                    {(signalsPage) => (
                      <SignalList signals={signalsPage.items} />
                    )}
                  </QueryBoundary>
                </CardBody>
              </Card>
            ) : null}
          </>
        )}
      </QueryBoundary>
    </div>
  )
}
