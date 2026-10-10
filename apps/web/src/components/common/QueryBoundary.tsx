import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ErrorState } from './ErrorState'
import { LoadingState } from './LoadingState'

/** Shows a loading skeleton, then either the data or a Retry state. Every screen that loads data uses this, so none can show a blank page. */
export function QueryBoundary<T>({
  query,
  rows,
  children,
}: {
  query: UseQueryResult<T>
  rows?: number
  children: (data: T) => ReactNode
}) {
  if (query.isPending) return <LoadingState rows={rows} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  return <>{children(query.data)}</>
}
