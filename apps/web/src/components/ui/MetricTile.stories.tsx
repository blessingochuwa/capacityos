import type { Meta, StoryObj } from '@storybook/react-vite'

import { MetricTile } from './MetricTile'

const meta = {
  title: 'UI/MetricTile',
  component: MetricTile,
  args: {
    label: 'Remaining capacity',
    value: '12.5h',
  },
} satisfies Meta<typeof MetricTile>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {}

export const Danger: Story = {
  args: { label: 'Over-allocation', value: '-6.0h', tone: 'danger' },
}

export const Success: Story = {
  args: { label: 'Utilization', value: '78%', tone: 'success' },
}
