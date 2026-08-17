import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProjectSkillCoverageTable } from './ProjectSkillCoverageTable'
import { makeSkillCoverage } from '@/test/fixtures'

describe('ProjectSkillCoverageTable', () => {
  it('renders a "not configured" empty state when there are no requirements', () => {
    render(
      <ProjectSkillCoverageTable requirements={[]} onRemove={() => {}} />,
    )
    expect(
      screen.getByText('No skill requirements configured for this project.'),
    ).toBeInTheDocument()
  })

  it('shows "Fully covered" when gap_hours is zero', () => {
    const requirement = makeSkillCoverage({ gap_hours: '0.00' })
    render(
      <ProjectSkillCoverageTable
        requirements={[requirement]}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('Fully covered')).toBeInTheDocument()
  })

  it('shows "Uncovered" when there is zero qualified available capacity', () => {
    const requirement = makeSkillCoverage({
      gap_hours: '40.00',
      qualified_available_hours: '0.00',
      qualified_people: [],
    })
    render(
      <ProjectSkillCoverageTable
        requirements={[requirement]}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('Uncovered')).toBeInTheDocument()
  })

  it('shows "Partially covered" when some but not all demand is covered', () => {
    const requirement = makeSkillCoverage({
      required_hours: '80.00',
      qualified_available_hours: '20.00',
      gap_hours: '60.00',
    })
    render(
      <ProjectSkillCoverageTable
        requirements={[requirement]}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('Partially covered')).toBeInTheDocument()
  })

  it('lists qualified people with their proficiency', () => {
    const requirement = makeSkillCoverage()
    render(
      <ProjectSkillCoverageTable
        requirements={[requirement]}
        onRemove={() => {}}
      />,
    )
    expect(screen.getByText('Jane Doe (proficient)')).toBeInTheDocument()
  })
})
