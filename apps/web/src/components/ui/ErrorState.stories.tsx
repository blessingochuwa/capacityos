import type { Meta, StoryObj } from '@storybook/react-vite'

import { ApiError } from '@/api/client'

import { ErrorState } from './ErrorState'

const meta = {
  title: 'UI/ErrorState',
  component: ErrorState,
} satisfies Meta<typeof ErrorState>

export default meta
type Story = StoryObj<typeof meta>

export const Generic: Story = {
  args: {
    error: new Error('unexpected'),
  },
}

export const ApiErrorMessage: Story = {
  args: {
    error: new ApiError(404, 'Project not found.'),
  },
}

export const WithRetry: Story = {
  args: {
    error: new ApiError(
      503,
      'The database is temporarily unavailable. Please try again.',
    ),
    onRetry: () => {},
  },
}
