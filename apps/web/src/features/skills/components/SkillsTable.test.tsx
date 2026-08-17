import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SkillsTable } from './SkillsTable'
import { makeSkill } from '@/test/fixtures'

describe('SkillsTable', () => {
  it('renders an empty state when no skills are defined', () => {
    render(<SkillsTable skills={[]} onDeactivate={() => {}} />)
    expect(screen.getByText('No skills defined yet.')).toBeInTheDocument()
  })

  it('renders each skill with its category and person count', () => {
    const skill = makeSkill({
      name: 'Backend Development',
      category: 'Engineering',
      person_count: 3,
    })
    render(<SkillsTable skills={[skill]} onDeactivate={() => {}} />)
    expect(screen.getByText('Backend Development')).toBeInTheDocument()
    expect(screen.getByText('Engineering')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('shows an inactive badge and no deactivate button for inactive skills', () => {
    const skill = makeSkill({ is_active: false })
    render(<SkillsTable skills={[skill]} onDeactivate={() => {}} />)
    expect(screen.getByText('Inactive')).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /deactivate/i }),
    ).not.toBeInTheDocument()
  })

  it('calls onDeactivate with the skill id when clicked', async () => {
    const user = userEvent.setup()
    const skill = makeSkill()
    const onDeactivate = vi.fn()
    render(<SkillsTable skills={[skill]} onDeactivate={onDeactivate} />)

    await user.click(screen.getByRole('button', { name: /deactivate/i }))
    expect(onDeactivate).toHaveBeenCalledWith(skill.id)
  })
})
