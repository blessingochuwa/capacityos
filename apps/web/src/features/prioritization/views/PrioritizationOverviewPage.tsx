import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { EmptyState } from '@/components/ui/EmptyState'
import { QueryBoundary } from '@/components/ui/QueryBoundary'
import { Select } from '@/components/ui/Select'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { ProjectFilterPicker } from '@/features/insights/components/ProjectFilterPicker'
import { ExplainPriorityButton } from '@/features/ai/components/ExplainPriorityButton'
import { ExplainSnapshotComparisonButton } from '@/features/ai/components/ExplainSnapshotComparisonButton'
import { DependencyGraphTable } from '../components/DependencyGraphTable'
import { DependencyManager } from '../components/DependencyManager'
import { FrameworkCriteriaEditor } from '../components/FrameworkCriteriaEditor'
import { FrameworkForm } from '../components/FrameworkForm'
import { PortfolioSnapshotComparisonTable } from '../components/PortfolioSnapshotComparisonTable'
import { PortfolioSnapshotList } from '../components/PortfolioSnapshotList'
import { PortfolioTable } from '../components/PortfolioTable'
import { ScoreForm } from '../components/ScoreForm'
import { useDependencyGraph } from '../hooks/useDependencyGraph'
import { useFrameworks } from '../hooks/useFrameworks'
import { usePortfolio } from '../hooks/usePortfolio'
import { usePortfolioSnapshots } from '../hooks/usePortfolioSnapshots'
import { useProjectPriorityScores } from '../hooks/useProjectPriorityScores'
import { useSnapshotComparison } from '../hooks/useSnapshotComparison'
import { useCreateSnapshot } from '../hooks/useSnapshotMutations'

/**
 * "Given limited people, time and capacity, what should this organization
 * work on first?" (CLAUDE.md §18/§38) — a portfolio ranked by an
 * organization-chosen framework, never a framework CapacityOS prescribes.
 * Phase 18 completes the framework set (RICE, ICE, WSJF, MoSCoW, Weighted
 * Scoring), lets a Weighted Scoring framework's criteria be edited after
 * creation, and adds the project dependency graph. Phase 19 adds an AI
 * explanation for an existing score (ExplainPriorityButton), reusing the
 * Phase 8 AI infrastructure verbatim. Phase 20 adds scenario-vs-baseline
 * comparison (see features/scenarios/views/ScenarioWorkspacePage.tsx, not
 * this page — the comparison lives inside the Scenario workspace it
 * extends). Phase 21 adds portfolio snapshots — an explicit, immutable,
 * point-in-time saved ranking for trend/history, distinct from the
 * always-fresh live board above. Phase 22 adds snapshot-vs-snapshot
 * comparison — entered/left/changed/unchanged, computed fresh from two
 * already-frozen snapshots, never persisted. The five remaining Recharts
 * visualizations and an AI explanation of the Phase 20 comparison remain
 * deferred (see docs/PRD-phase-17-prioritization.md, docs/adr/0019,
 * docs/adr/0020, docs/adr/0021, and docs/adr/0022). Phase 23 adds an AI
 * explanation of the Phase 22 snapshot comparison above
 * (ExplainSnapshotComparisonButton) — reusing the Phase 8 AI
 * infrastructure verbatim, exactly like ExplainPriorityButton (Phase 19).
 */
export function PrioritizationOverviewPage() {
  const { can } = useAuth()
  const canManageFrameworks = can('prioritization.manage')
  const canScore = can('prioritization.score')

  const [searchParams, setSearchParams] = useSearchParams()
  const frameworkId = searchParams.get('framework') ?? undefined
  const [showFrameworkForm, setShowFrameworkForm] = useState(false)
  const [scoringProjectId, setScoringProjectId] = useState<string | undefined>(undefined)
  const [dependencyProjectId, setDependencyProjectId] = useState<string | undefined>(undefined)
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | undefined>(undefined)
  const [compareFromId, setCompareFromId] = useState<string | undefined>(undefined)
  const [compareToId, setCompareToId] = useState<string | undefined>(undefined)

  const frameworksQuery = useFrameworks(true)
  const portfolioQuery = usePortfolio(frameworkId)
  const scoresQuery = useProjectPriorityScores(scoringProjectId)
  const dependencyGraphQuery = useDependencyGraph()
  const snapshotsQuery = usePortfolioSnapshots(frameworkId)
  const createSnapshot = useCreateSnapshot()
  const comparisonQuery = useSnapshotComparison(compareFromId, compareToId)
  const selectedFramework = frameworksQuery.data?.items.find((f) => f.id === frameworkId)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Prioritization"
        description="Rank the portfolio against an organization-chosen framework — CapacityOS never picks one for you."
      />

      <Card>
        <CardHeader
          title="Frameworks"
          description="Every active prioritization framework this organization has defined."
          action={
            canManageFrameworks ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => setShowFrameworkForm((prev) => !prev)}
              >
                {showFrameworkForm ? 'Close' : 'New framework'}
              </Button>
            ) : null
          }
        />
        <CardBody className="space-y-4">
          {canManageFrameworks && showFrameworkForm ? (
            <FrameworkForm onDone={() => setShowFrameworkForm(false)} />
          ) : null}

          <QueryBoundary query={frameworksQuery} loadingLabel="Loading frameworks…">
            {(frameworks) =>
              frameworks.items.length === 0 ? (
                <EmptyState
                  title="No prioritization frameworks yet."
                  description={
                    canManageFrameworks
                      ? 'Create a framework to start ranking the portfolio.'
                      : 'An Owner or Admin needs to create one first.'
                  }
                />
              ) : (
                <div className="w-72">
                  <Select
                    label="Framework"
                    value={frameworkId ?? ''}
                    placeholder="Select a framework"
                    options={frameworks.items.map((framework) => ({
                      value: framework.id,
                      label: `${framework.name} (${framework.framework_type.toUpperCase()})`,
                    }))}
                    onChange={(event) => {
                      const next = new URLSearchParams(searchParams)
                      if (event.target.value) next.set('framework', event.target.value)
                      else next.delete('framework')
                      setSearchParams(next, { replace: true })
                    }}
                  />
                </div>
              )
            }
          </QueryBoundary>

          {canManageFrameworks && selectedFramework?.framework_type === 'weighted' ? (
            <FrameworkCriteriaEditor framework={selectedFramework} />
          ) : null}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Portfolio priority board"
          description="Projects scored under the selected framework, ranked highest first."
        />
        <CardBody className="space-y-4">
          {!frameworkId ? (
            <EmptyState title="Select a framework above to see the portfolio ranking." />
          ) : (
            <QueryBoundary query={portfolioQuery} loadingLabel="Loading portfolio…">
              {(portfolio) =>
                portfolio.items.length === 0 ? (
                  <EmptyState
                    title="No projects have been scored under this framework yet."
                    description="Pick a project below to add its first score."
                  />
                ) : (
                  <PortfolioTable
                    items={portfolio.items}
                    onSelectProject={canScore ? setScoringProjectId : undefined}
                  />
                )
              }
            </QueryBoundary>
          )}
        </CardBody>
      </Card>

      {frameworkId ? (
        <Card>
          <CardHeader
            title="Portfolio snapshots"
            description="An explicit, point-in-time saved ranking — for trend/history, distinct from the always-fresh board above."
            action={
              canManageFrameworks ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => createSnapshot.mutate(frameworkId)}
                  disabled={createSnapshot.isPending}
                >
                  {createSnapshot.isPending ? 'Taking snapshot…' : 'Take snapshot'}
                </Button>
              ) : null
            }
          />
          <CardBody className="space-y-4">
            <QueryBoundary query={snapshotsQuery} loadingLabel="Loading snapshots…">
              {(snapshots) =>
                snapshots.items.length === 0 ? (
                  <EmptyState
                    title="No snapshots taken yet."
                    description={
                      canManageFrameworks
                        ? 'Take a snapshot to save this framework’s current ranking for later comparison.'
                        : 'An Owner or Admin can take one to save this ranking for later comparison.'
                    }
                  />
                ) : (
                  <div className="space-y-6">
                    <PortfolioSnapshotList
                      snapshots={snapshots.items}
                      selectedId={selectedSnapshotId}
                      onSelect={setSelectedSnapshotId}
                    />
                    {(() => {
                      const selected = snapshots.items.find((s) => s.id === selectedSnapshotId)
                      return selected ? <PortfolioTable items={selected.entries} /> : null
                    })()}

                    {snapshots.items.length < 2 ? null : (
                      <div className="space-y-4 border-t border-slate-800 pt-4">
                        <h3 className="text-sm font-medium text-slate-200">
                          Compare two snapshots
                        </h3>
                        <div className="flex flex-wrap gap-4">
                          <div className="w-64">
                            <Select
                              label="From"
                              value={compareFromId ?? ''}
                              placeholder="Select a snapshot"
                              options={snapshots.items.map((snapshot) => ({
                                value: snapshot.id,
                                label: new Date(snapshot.taken_at).toLocaleString(),
                              }))}
                              onChange={(event) =>
                                setCompareFromId(event.target.value || undefined)
                              }
                            />
                          </div>
                          <div className="w-64">
                            <Select
                              label="To"
                              value={compareToId ?? ''}
                              placeholder="Select a snapshot"
                              options={snapshots.items.map((snapshot) => ({
                                value: snapshot.id,
                                label: new Date(snapshot.taken_at).toLocaleString(),
                              }))}
                              onChange={(event) =>
                                setCompareToId(event.target.value || undefined)
                              }
                            />
                          </div>
                        </div>

                        {compareFromId && compareToId ? (
                          <QueryBoundary
                            query={comparisonQuery}
                            loadingLabel="Comparing snapshots…"
                            errorTitle="Could not compare these snapshots"
                          >
                            {(comparison) => (
                              <div className="space-y-4">
                                <PortfolioSnapshotComparisonTable items={comparison.items} />
                                <ExplainSnapshotComparisonButton
                                  fromSnapshotId={compareFromId}
                                  toSnapshotId={compareToId}
                                />
                              </div>
                            )}
                          </QueryBoundary>
                        ) : null}
                      </div>
                    )}
                  </div>
                )
              }
            </QueryBoundary>
          </CardBody>
        </Card>
      ) : null}

      {frameworkId ? (
        <Card>
          <CardHeader
            title="Score a project"
            description="Record or update one project's criterion values for the selected framework."
          />
          <CardBody className="space-y-4">
            <div className="w-64">
              <ProjectFilterPicker value={scoringProjectId} onChange={setScoringProjectId} />
            </div>

            {!scoringProjectId ? null : !canScore ? (
              <ViewOnlyNotice message="Your role can view scores but not create or edit them — ask a Manager with access to this project." />
            ) : (
              <QueryBoundary query={scoresQuery} loadingLabel="Loading this project's scores…">
                {(scores) => {
                  const existing = scores.find((s) => s.framework_id === frameworkId)
                  const frameworks = frameworksQuery.data?.items ?? []
                  const framework = frameworks.find((f) => f.id === frameworkId)
                  if (!framework) return null
                  return (
                    <div className="space-y-4">
                      <ScoreForm
                        key={existing?.id ?? 'create'}
                        projectId={scoringProjectId}
                        framework={framework}
                        score={existing}
                        onDone={() => setScoringProjectId(undefined)}
                        onCancel={() => setScoringProjectId(undefined)}
                      />
                      {existing ? (
                        <ExplainPriorityButton
                          projectId={scoringProjectId}
                          scoreId={existing.id}
                        />
                      ) : null}
                    </div>
                  )
                }}
              </QueryBoundary>
            )}
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="Project dependencies"
          description="Record which projects block, relate to, or enable each other."
        />
        <CardBody>
          <DependencyManager
            canManage={canScore}
            fromProjectId={dependencyProjectId}
            onFromProjectChange={setDependencyProjectId}
          />
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Dependency graph"
          description="Every project dependency recorded across the organization."
        />
        <CardBody>
          <QueryBoundary query={dependencyGraphQuery} loadingLabel="Loading dependency graph…">
            {(graph) => <DependencyGraphTable graph={graph} />}
          </QueryBoundary>
        </CardBody>
      </Card>
    </div>
  )
}
