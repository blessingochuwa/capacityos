import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChangeList } from './ChangeList'
import { makePerson, makeProject, makeScenarioOperation } from '@/test/fixtures'

describe('ChangeList', () => {
  it('renders an empty state when there are no operations', () => {
    render(
      <ChangeList
        operations={[]}
        peopleLookup={new Map()}
        projectsLookup={new Map()}
        onDelete={vi.fn()}
      />,
    )
    expect(screen.getByText('No changes yet.')).toBeInTheDocument()
  })

  it('describes each operation in plain language using looked-up names', () => {
    const operation = makeScenarioOperation()
    render(
      <ChangeList
        operations={[operation]}
        peopleLookup={
          new Map([
            ['person-1', makePerson({ id: 'person-1', display_name: 'Sarah' })],
          ])
        }
        projectsLookup={
          new Map([
            [
              'project-1',
              makeProject({ id: 'project-1', name: 'Website Redesign' }),
            ],
          ])
        }
        onDelete={vi.fn()}
      />,
    )
    expect(
      screen.getByText(/Add 20h for Sarah on Website Redesign/),
    ).toBeInTheDocument()
  })

  it('falls back to a hypothetical resource label when the person is not a real Person', () => {
    const hypothetical = makeScenarioOperation({
      id: 'hyp-1',
      operation_type: 'add_hypothetical_resource',
      payload: {
        operation_type: 'add_hypothetical_resource',
        label: 'Senior Designer',
        hours_per_week: '40',
        start_date: '2026-09-01',
        end_date: '2026-09-05',
      },
    })
    const allocation = makeScenarioOperation({
      id: 'op-2',
      sequence: 1,
      payload: {
        operation_type: 'add_allocation',
        person_id: 'hyp-1',
        project_id: 'project-1',
        hours: '20',
        start_date: '2026-09-01',
        end_date: '2026-09-05',
      },
    })

    render(
      <ChangeList
        operations={[hypothetical, allocation]}
        peopleLookup={new Map()}
        projectsLookup={
          new Map([
            [
              'project-1',
              makeProject({ id: 'project-1', name: 'Website Redesign' }),
            ],
          ])
        }
        onDelete={vi.fn()}
      />,
    )
    expect(screen.getByText(/Add 20h for Senior Designer/)).toBeInTheDocument()
  })

  it('calls onDelete with the operation id when Remove is clicked', async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()
    const operation = makeScenarioOperation({ id: 'op-1' })

    render(
      <ChangeList
        operations={[operation]}
        peopleLookup={new Map([['person-1', makePerson({ id: 'person-1' })]])}
        projectsLookup={
          new Map([['project-1', makeProject({ id: 'project-1' })]])
        }
        onDelete={onDelete}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Remove this change' }))
    expect(onDelete).toHaveBeenCalledWith('op-1')
  })
})
