import { Button } from './Button'
import { ApiError } from '@/api/client'

interface ErrorStateProps {
  error: unknown
  onRetry?: () => void
  title?: string
}

/** Never surfaces a raw stack trace or backend internals (CLAUDE.md §19/§27)
 * — only the normalized message ApiError already extracted, or a generic
 * fallback for anything unexpected. */
export function ErrorState({
  error,
  onRetry,
  title = "We couldn't load capacity data.",
}: ErrorStateProps) {
  const message =
    error instanceof ApiError
      ? error.message
      : 'Something went wrong. Please try again.'

  return (
    <div
      role="alert"
      className="flex flex-col items-center gap-3 px-5 py-10 text-center"
    >
      <p className="text-sm font-medium text-slate-200">{title}</p>
      <p className="max-w-sm text-sm text-slate-400">{message}</p>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  )
}
