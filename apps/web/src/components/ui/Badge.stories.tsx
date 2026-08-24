import type { Meta, StoryObj } from '@storybook/react-vite'

import { Badge } from './Badge'

const meta = {
  title: 'UI/Badge',
  component: Badge,
} satisfies Meta<typeof Badge>

export default meta
type Story = StoryObj<typeof meta>

export const Neutral: Story = {
  args: { variant: 'neutral', children: 'Draft' },
}

export const Success: Story = {
  args: { variant: 'success', children: 'Healthy' },
}

export const Info: Story = {
  args: { variant: 'info', children: 'In progress' },
}

export const Warning: Story = {
  args: { variant: 'warning', children: 'Review overdue' },
}

export const Danger: Story = {
  args: { variant: 'danger', children: 'Over-allocated' },
}
