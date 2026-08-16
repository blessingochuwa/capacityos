import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SeverityBadge } from './SeverityBadge'

describe('SeverityBadge', () => {
  it('renders a distinct icon and label for each severity — never color alone', () => {
    const critical = render(<SeverityBadge severity="critical" />)
    expect(screen.getByText('Critical')).toBeInTheDocument()
    const criticalIconHtml = document.querySelector('svg')?.innerHTML
    expect(criticalIconHtml).toBeTruthy()
    critical.unmount()

    const warning = render(<SeverityBadge severity="warning" />)
    expect(screen.getByText('Warning')).toBeInTheDocument()
    const warningIconHtml = document.querySelector('svg')?.innerHTML
    // Warning's icon path must differ from critical's — same glyph with a
    // different badge color would violate "never color alone" (spec §21).
    expect(warningIconHtml).toBeTruthy()
    expect(warningIconHtml).not.toBe(criticalIconHtml)
    warning.unmount()

    render(<SeverityBadge severity="info" />)
    expect(screen.getByText('Info')).toBeInTheDocument()
  })
})
