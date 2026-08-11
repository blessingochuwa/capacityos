import { isRouteErrorResponse, useRouteError } from 'react-router-dom'

/** Route-level fallback (react-router's errorElement) — a rendering/loader
 * error anywhere in the tree lands here instead of a blank white screen or
 * a raw stack trace (CLAUDE.md §19/§27). */
export function RouteErrorBoundary() {
  const error = useRouteError()
  const message = isRouteErrorResponse(error)
    ? `${error.status} ${error.statusText}`
    : 'Something went wrong loading this page.'

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-slate-950 px-6 text-center text-slate-100">
      <p className="text-sm font-medium">We couldn't load CapacityOS.</p>
      <p className="text-sm text-slate-400">{message}</p>
      <a
        href="/capacity"
        className="mt-2 text-sm text-indigo-300 underline underline-offset-2"
      >
        Go to Capacity Overview
      </a>
    </div>
  )
}
