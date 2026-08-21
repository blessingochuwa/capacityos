import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { RequireAuth } from '@/components/layout/RequireAuth'
import { RouteErrorBoundary } from '@/components/layout/RouteErrorBoundary'
import { AccessManagementPage } from '@/features/access/views/AccessManagementPage'
import { CapacityOverviewPage } from '@/features/capacity/views/CapacityOverviewPage'
import { PersonCapacityPage } from '@/features/capacity/views/PersonCapacityPage'
import { ProjectCapacityPage } from '@/features/capacity/views/ProjectCapacityPage'
import { LoginPage } from '@/features/auth/views/LoginPage'
import { SelectOrganizationPage } from '@/features/auth/views/SelectOrganizationPage'
import { ImportExportPage } from '@/features/import-export/views/ImportExportPage'
import { InsightsOverviewPage } from '@/features/insights/views/InsightsOverviewPage'
import { RisksOverviewPage } from '@/features/risks/views/RisksOverviewPage'
import { ScenarioListPage } from '@/features/scenarios/views/ScenarioListPage'
import { ScenarioWorkspacePage } from '@/features/scenarios/views/ScenarioWorkspacePage'
import { SkillsOverviewPage } from '@/features/skills/views/SkillsOverviewPage'
import { StakeholdersOverviewPage } from '@/features/stakeholders/views/StakeholdersOverviewPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/select-organization', element: <SelectOrganizationPage /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
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
      { path: 'skills', element: <SkillsOverviewPage /> },
      { path: 'risks', element: <RisksOverviewPage /> },
      { path: 'stakeholders', element: <StakeholdersOverviewPage /> },
      { path: 'import-export', element: <ImportExportPage /> },
      { path: 'admin/access', element: <AccessManagementPage /> },
    ],
  },
])
