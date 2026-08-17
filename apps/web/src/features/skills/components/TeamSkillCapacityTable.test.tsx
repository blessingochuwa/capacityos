import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { TeamSkillCapacityTable } from './TeamSkillCapacityTable'
import { makeTeamSkillCapacityEntry } from '@/test/fixtures'

describe('TeamSkillCapacityTable', () => {
  it('renders an empty state when no member holds a skill', () => {
    render(<TeamSkillCapacityTable skills={[]} />)
    expect(
      screen.getByText('No team member currently holds a recorded skill.'),
    ).toBeInTheDocument()
  })

  it('renders qualified available capacity and holders per skill', () => {
    const entry = makeTeamSkillCapacityEntry({
      skill_label: 'Backend Development',
      qualified_available_hours: '32.00',
    })
    render(<TeamSkillCapacityTable skills={[entry]} />)
    expect(screen.getByText('Backend Development')).toBeInTheDocument()
    expect(screen.getByText('32h')).toBeInTheDocument()
    expect(screen.getByText('Jane Doe (proficient)')).toBeInTheDocument()
  })
})
