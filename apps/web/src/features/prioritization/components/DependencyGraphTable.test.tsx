import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DependencyGraphTable } from './DependencyGraphTable'
import { makeDependencyGraph, makeProjectDependency } from '@/test/fixtures'

describe('DependencyGraphTable', () => {
  it('shows an empty state when there are no edges', () => {
    render(<DependencyGraphTable graph={{ nodes: [], edges: [] }} />)
    expect(screen.getByText('No project dependencies recorded yet.')).toBeInTheDocument()
  })

  it('renders one row per edge with both project names and the relationship', () => {
    const graph = makeDependencyGraph({
      edges: [
        makeProjectDependency({
          from_project_name: 'Website Redesign',
          to_project_name: 'Mobile App',
          dependency_type: 'blocks',
        }),
      ],
    })
    render(<DependencyGraphTable graph={graph} />)
    expect(screen.getByText('Website Redesign')).toBeInTheDocument()
    expect(screen.getByText('Mobile App')).toBeInTheDocument()
    expect(screen.getByText('blocks')).toBeInTheDocument()
  })
})
