interface SkeletonProps {
  className?: string
}

export function Skeleton({ className = 'h-4 w-full' }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded bg-slate-800 ${className}`}
      aria-hidden="true"
    />
  )
}

/** A labeled loading region — the visible skeleton is decorative
 * (aria-hidden), the sr-only text is what assistive tech announces. */
export function LoadingState({
  label = 'Loading capacity data…',
}: {
  label?: string
}) {
  return (
    <div role="status" className="space-y-3 p-5">
      <span className="sr-only">{label}</span>
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-4 w-2/3" />
      <Skeleton className="h-4 w-1/2" />
    </div>
  )
}
