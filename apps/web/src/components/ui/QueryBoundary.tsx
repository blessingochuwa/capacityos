import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { LoadingState } from './Skeleton'
import { ErrorState } from './ErrorState'

interface QueryBoundaryProps<T> {
  query: UseQueryResult<T>
  loadingLabel?: string
  errorTitle?: string
  children: (data: T) => ReactNode
}

/** The loading/error/data branching every capacity view needs (spec §17/§19)
 * lives here once instead of being reimplemented per page. */
export function QueryBoundary<T>({
  query,
  loadingLabel,
  errorTitle,
  children,
}: QueryBoundaryProps<T>) {
  if (query.isPending) {
    return <LoadingState label={loadingLabel} />
  }
  if (query.isError) {
    return (
      <ErrorState
        error={query.error}
        onRetry={() => void query.refetch()}
        title={errorTitle}
      />
    )
  }
  return <>{children(query.data)}</>
}
