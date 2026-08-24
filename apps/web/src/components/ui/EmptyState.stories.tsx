import type { Meta, StoryObj } from '@storybook/react-vite'

import { Button } from './Button'
import { EmptyState } from './EmptyState'

const meta = {
  title: 'UI/EmptyState',
  component: EmptyState,
} satisfies Meta<typeof EmptyState>

export default meta
type Story = StoryObj<typeof meta>

export const Basic: Story = {
  args: {
    title: 'No projects yet',
  },
}

export const WithDescription: Story = {
  args: {
    title: 'No allocations yet',
    description: 'Allocate people to this project to start tracking capacity.',
  },
}

export const WithAction: Story = {
  args: {
    title: 'No scenarios yet',
    description:
      'Create a scenario to model hypothetical changes without touching live data.',
    action: <Button variant="primary">New scenario</Button>,
  },
}
