import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { usePeople } from '@/hooks/usePeople'
import { useProjects } from '@/hooks/useProjects'
import { useTeams } from '@/hooks/useTeams'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import { ExportPanel } from './ExportPanel'
import { useExportEntities } from '../hooks/useExportEntities'

vi.mock('@/hooks/usePeople', () => ({ usePeople: vi.fn() }))
vi.mock('@/hooks/useProjects', () => ({ useProjects: vi.fn() }))
vi.mock('@/hooks/useTeams', () => ({ useTeams: vi.fn() }))
vi.mock('../hooks/useExportEntities')

const mockedUsePeople = vi.mocked(usePeople)
const mockedUseProjects = vi.mocked(useProjects)
const mockedUseTeams = vi.mocked(useTeams)
const mockedUseExportEntities = vi.mocked(useExportEntities)

function setUpQueries() {
  mockedUsePeople.mockReturnValue(
    mockQuerySuccess({ items: [], total: 0 }) as unknown as ReturnType<typeof usePeople>,
  )
  mockedUseProjects.mockReturnValue(
    mockQuerySuccess({ items: [], total: 0 }) as unknown as ReturnType<typeof useProjects>,
  )
  mockedUseTeams.mockReturnValue(
    mockQuerySuccess({ items: [], total: 0 }) as unknown as ReturnType<typeof useTeams>,
  )
  mockedUseExportEntities.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof useExportEntities>)
}

/** Phase 36/37: Risk, Stakeholder, ProjectPriorityScore, and
 * ProjectDependency export are all project-scoped, exactly like
 * ProjectSkillRequirement — this locks in ExportPanel's scopeFieldFor
 * mapping (mirrors
 * apps/api/app/services/export_service.py::ExportService._collect_rows). */
describe('ExportPanel scope field for Phase 36/37 entities', () => {
  it.each(['risk', 'stakeholder', 'project_priority_score', 'project_dependency'])(
    'shows a Project filter, not Person or Team, for %s',
    async (entityType) => {
      setUpQueries()
      const user = userEvent.setup()
      render(<ExportPanel />)

      await user.selectOptions(screen.getByLabelText('Entity'), entityType)

      expect(screen.getByLabelText('Project')).toBeInTheDocument()
      expect(screen.queryByLabelText('Person')).not.toBeInTheDocument()
      expect(screen.queryByLabelText('Team')).not.toBeInTheDocument()
    },
  )
})
