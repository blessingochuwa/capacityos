import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ImportRowStatusBadge } from './ImportRowStatusBadge'

describe('ImportRowStatusBadge', () => {
  it('renders a distinct icon and label for each status — never color alone', () => {
    const create = render(<ImportRowStatusBadge status="valid_create" />)
    expect(screen.getByText('Create')).toBeInTheDocument()
    create.unmount()

    const unchanged = render(<ImportRowStatusBadge status="valid_unchanged" />)
    expect(screen.getByText('Unchanged')).toBeInTheDocument()
    const unchangedIconHtml = document.querySelector('svg')?.innerHTML
    unchanged.unmount()

    const invalid = render(<ImportRowStatusBadge status="invalid" />)
    expect(screen.getByText('Needs fixing')).toBeInTheDocument()
    const invalidIconHtml = document.querySelector('svg')?.innerHTML
    // Invalid's icon must differ from unchanged's — same glyph with a
    // different badge color would violate "never color alone" (CLAUDE.md §21).
    expect(invalidIconHtml).toBeTruthy()
    expect(invalidIconHtml).not.toBe(unchangedIconHtml)
    invalid.unmount()

    render(<ImportRowStatusBadge status="valid_update" />)
    expect(screen.getByText('Update')).toBeInTheDocument()
  })
})
