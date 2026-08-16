import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { RouteErrorBoundary } from '@/components/layout/RouteErrorBoundary'
import { CapacityOverviewPage } from '@/features/capacity/views/CapacityOverviewPage'
import { PersonCapacityPage } from '@/features/capacity/views/PersonCapacityPage'
import { ProjectCapacityPage } from '@/features/capacity/views/ProjectCapacityPage'
import { InsightsOverviewPage } from '@/features/insights/views/InsightsOverviewPage'
import { ScenarioListPage } from '@/features/scenarios/views/ScenarioListPage'
import { ScenarioWorkspacePage } from '@/features/scenarios/views/ScenarioWorkspacePage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    errorElement: <RouteErrorBoundary />,
    children: [
      { index: true, element: <Navigate to="/capacity" replace /> },
      { path: 'capacity', element: <CapacityOverviewPage /> },
      { path: 'capacity/people/:personId', element: <PersonCapacityPage /> },
      {
        path: 'capacity/projects/:projectId',
        element: <ProjectCapacityPage />,
      },
      { path: 'scenarios', element: <ScenarioListPage /> },
      { path: 'scenarios/:scenarioId', element: <ScenarioWorkspacePage /> },
      { path: 'insights', element: <InsightsOverviewPage /> },
    ],
  },
])
