import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ApiError } from '@/api/client'
import { usePeople } from '@/hooks/usePeople'
import { useProjects } from '@/hooks/useProjects'
import { useTeams } from '@/hooks/useTeams'
import {
  makeImportApplyResult,
  makeImportValidationReport,
  makePerson,
} from '@/test/fixtures'
import { mockQuerySuccess } from '@/test/mockQueryResult'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ImportExportPage } from './ImportExportPage'
import { useApplyImport } from '../hooks/useApplyImport'
import { useDownloadTemplate } from '../hooks/useDownloadTemplate'
import { useExportEntities } from '../hooks/useExportEntities'
import { useValidateImport } from '../hooks/useValidateImport'

vi.mock('../hooks/useDownloadTemplate')
vi.mock('../hooks/useValidateImport')
vi.mock('../hooks/useApplyImport')
vi.mock('../hooks/useExportEntities')
vi.mock('@/hooks/usePeople')
vi.mock('@/hooks/useProjects')
vi.mock('@/hooks/useTeams')
// Owner-equivalent permissions by default — see ScenarioListPage.test.tsx's
// identical comment for why.
vi.mock('@/features/auth/context/AuthContext', () => ({
  useAuth: vi.fn(),
}))

const mockedUseDownloadTemplate = vi.mocked(useDownloadTemplate)
const mockedUseValidateImport = vi.mocked(useValidateImport)
const mockedUseApplyImport = vi.mocked(useApplyImport)
const mockedUseExportEntities = vi.mocked(useExportEntities)
const mockedUsePeople = vi.mocked(usePeople)
const mockedUseProjects = vi.mocked(useProjects)
const mockedUseTeams = vi.mocked(useTeams)
const mockedUseAuth = vi.mocked(useAuth)

function mockCommonHooks() {
  mockedUseAuth.mockReturnValue({
    user: null,
    status: 'authenticated',
    can: () => true,
    canManageResource: () => true,
    login: vi.fn(),
    logout: vi.fn(),
  })
  mockedUseDownloadTemplate.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof useDownloadTemplate>)
  mockedUseExportEntities.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
  } as unknown as ReturnType<typeof useExportEntities>)
  mockedUsePeople.mockReturnValue(
    mockQuerySuccess({ items: [makePerson()], total: 1 }),
  )
  mockedUseProjects.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
  mockedUseTeams.mockReturnValue(mockQuerySuccess({ items: [], total: 0 }))
}

describe('ImportExportPage', () => {
  it('disables Validate until a file is selected, then submits entity/mode/file', async () => {
    mockCommonHooks()
    const validateMutate = vi.fn()
    mockedUseValidateImport.mockReturnValue({
      mutate: validateMutate,
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: undefined,
    } as unknown as ReturnType<typeof useValidateImport>)
    mockedUseApplyImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: undefined,
    } as unknown as ReturnType<typeof useApplyImport>)

    const user = userEvent.setup()
    render(<ImportExportPage />)

    const validateButton = screen.getByRole('button', { name: 'Validate' })
    expect(validateButton).toBeDisabled()

    const file = new File(['email,first_name,last_name'], 'people.csv', {
      type: 'text/csv',
    })
    const fileInput = screen.getByLabelText('File')
    await user.upload(fileInput, file)

    expect(validateButton).toBeEnabled()
    await user.click(validateButton)

    expect(validateMutate).toHaveBeenCalledWith({
      entityType: 'person',
      file,
      mode: 'upsert',
    })
  })

  it('shows the validation report and row results once validated', () => {
    mockCommonHooks()
    mockedUseValidateImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: makeImportValidationReport({
        total_rows: 1,
        valid_create_count: 1,
        rows: [
          {
            row_number: 1,
            status: 'valid_create',
            identity: 'email=jane.doe@example.com',
            matched_id: null,
            errors: [],
          },
        ],
      }),
    } as unknown as ReturnType<typeof useValidateImport>)
    mockedUseApplyImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: undefined,
    } as unknown as ReturnType<typeof useApplyImport>)

    render(<ImportExportPage />)

    expect(screen.getByText('Ready to apply.')).toBeInTheDocument()
    expect(screen.getByText('email=jane.doe@example.com')).toBeInTheDocument()
  })

  it('requires explicit confirmation before applying', async () => {
    mockCommonHooks()
    mockedUseValidateImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: makeImportValidationReport({ ready_to_apply: true }),
    } as unknown as ReturnType<typeof useValidateImport>)
    const applyMutate = vi.fn()
    mockedUseApplyImport.mockReturnValue({
      mutate: applyMutate,
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: undefined,
    } as unknown as ReturnType<typeof useApplyImport>)

    const user = userEvent.setup()
    render(<ImportExportPage />)

    const file = new File(['email,first_name,last_name'], 'people.csv', {
      type: 'text/csv',
    })
    await user.upload(screen.getByLabelText('File'), file)

    await user.click(screen.getByRole('button', { name: 'Apply' }))
    expect(applyMutate).not.toHaveBeenCalled()

    expect(
      screen.getByRole('button', { name: 'Confirm apply' }),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Confirm apply' }))
    expect(applyMutate).toHaveBeenCalled()
  })

  it('shows the apply result after a successful apply, and hides the Apply button', () => {
    mockCommonHooks()
    mockedUseValidateImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: makeImportValidationReport({ ready_to_apply: true }),
    } as unknown as ReturnType<typeof useValidateImport>)
    mockedUseApplyImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: makeImportApplyResult({
        applied: true,
        created_count: 2,
        updated_count: 1,
        unchanged_count: 0,
      }),
    } as unknown as ReturnType<typeof useApplyImport>)

    render(<ImportExportPage />)

    expect(
      screen.getByText('Applied: 2 created, 1 updated, 0 unchanged.'),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: 'Apply' }),
    ).not.toBeInTheDocument()
  })

  it('surfaces an apply error without claiming anything was written', () => {
    mockCommonHooks()
    mockedUseValidateImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: makeImportValidationReport({ ready_to_apply: true }),
    } as unknown as ReturnType<typeof useValidateImport>)
    mockedUseApplyImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: true,
      error: new ApiError(500, 'Something went wrong.'),
      data: undefined,
    } as unknown as ReturnType<typeof useApplyImport>)

    render(<ImportExportPage />)

    expect(screen.getByText('Something went wrong.')).toBeInTheDocument()
  })

  it('hides import and export controls for a role without those permissions (Phase 10)', () => {
    mockCommonHooks()
    mockedUseAuth.mockReturnValue({
      user: null,
      status: 'authenticated',
      can: () => false,
      canManageResource: () => false,
      login: vi.fn(),
      logout: vi.fn(),
    })
    mockedUseValidateImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: undefined,
    } as unknown as ReturnType<typeof useValidateImport>)
    mockedUseApplyImport.mockReturnValue({
      mutate: vi.fn(),
      reset: vi.fn(),
      isPending: false,
      isError: false,
      data: undefined,
    } as unknown as ReturnType<typeof useApplyImport>)

    render(<ImportExportPage />)

    expect(
      screen.queryByRole('button', { name: 'Validate' }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByText(/can view operational data but not import it/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/doesn't include permission to export/i),
    ).toBeInTheDocument()
  })
})
