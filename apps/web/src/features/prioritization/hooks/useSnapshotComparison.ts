import { useQuery } from '@tanstack/react-query'
import { prioritizationApi } from '../api/prioritizationApi'

export function useSnapshotComparison(
  fromSnapshotId: string | undefined,
  toSnapshotId: string | undefined,
) {
  return useQuery({
    queryKey: ['prioritization', 'snapshot-comparison', fromSnapshotId, toSnapshotId],
    queryFn: () => prioritizationApi.compareSnapshots(fromSnapshotId as string, toSnapshotId as string),
    enabled: fromSnapshotId !== undefined && toSnapshotId !== undefined,
  })
}
