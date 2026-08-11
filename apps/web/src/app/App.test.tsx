import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the CapacityOS shell and primary navigation', async () => {
    render(<App />)
    expect(await screen.findByText('CapacityOS')).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: 'Primary' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Capacity' })).toBeInTheDocument()
  })
})
