import type { UseQueryResult } from '@tanstack/react-query'
import { vi } from 'vitest'

/**
 * Minimal fakes of react-query's UseQueryResult for testing components that
 * only ever read `.data` / `.isPending` / `.isError` / `.error` / `.refetch`
 * (always through <QueryBoundary>, never destructured further) — casting
 * rather than implementing every field of the real, large, mostly-internal
 * UseQueryResult union, since this is test-only scaffolding.
 */

export function mockQueryPending<T>(): UseQueryResult<T> {
  return {
    isPending: true,
    isError: false,
    data: undefined,
    error: null,
    refetch: vi.fn(),
  } as unknown as UseQueryResult<T>
}

export function mockQuerySuccess<T>(data: T): UseQueryResult<T> {
  return {
    isPending: false,
    isError: false,
    data,
    error: null,
    refetch: vi.fn(),
  } as unknown as UseQueryResult<T>
}

export function mockQueryError<T>(
  error: unknown = new Error('Request failed'),
): UseQueryResult<T> {
  return {
    isPending: false,
    isError: true,
    data: undefined,
    error,
    refetch: vi.fn(),
  } as unknown as UseQueryResult<T>
}
