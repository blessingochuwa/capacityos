import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PriorityComparisonTable } from './PriorityComparisonTable'
import { makeScenarioPriorityProjectComparison } from '@/test/fixtures'

describe('PriorityComparisonTable', () => {
  it('renders baseline and scenario rank/score for a changed project', () => {
    render(
      <PriorityComparisonTable
        items={[
          makeScenarioPriorityProjectComparison({
            project_name: 'Website Redesign',
            baseline_rank: 2,
            baseline_score: '400.00',
            scenario_rank: 1,
            scenario_score: '2000.00',
            changed: true,
          }),
        ]}
      />,
    )
    expect(screen.getByText('Website Redesign')).toBeInTheDocument()
    expect(screen.getByText('400.00')).toBeInTheDocument()
    expect(screen.getByText('2000.00')).toBeInTheDocument()
    expect(screen.getByText('Changed')).toBeInTheDocument()
  })

  it('shows "No change" for a project the scenario left untouched', () => {
    render(
      <PriorityComparisonTable
        items={[
          makeScenarioPriorityProjectComparison({
            has_override: false,
            changed: false,
            baseline_rank: 1,
            scenario_rank: 1,
          }),
        ]}
      />,
    )
    expect(screen.getByText('No change')).toBeInTheDocument()
  })

  it('shows a MoSCoW category badge instead of a numeric score', () => {
    render(
      <PriorityComparisonTable
        items={[
          makeScenarioPriorityProjectComparison({
            baseline_score: null,
            baseline_category: 'could',
            scenario_score: null,
            scenario_category: 'must',
          }),
        ]}
      />,
    )
    expect(screen.getByText('Could')).toBeInTheDocument()
    expect(screen.getByText('Must')).toBeInTheDocument()
  })

  it('shows missing-criteria status for an incomplete score', () => {
    render(
      <PriorityComparisonTable
        items={[
          makeScenarioPriorityProjectComparison({
            baseline_score: null,
            baseline_category: null,
            baseline_missing_criteria: ['reach', 'effort'],
          }),
        ]}
      />,
    )
    expect(screen.getByText('Missing reach, effort')).toBeInTheDocument()
  })
})
