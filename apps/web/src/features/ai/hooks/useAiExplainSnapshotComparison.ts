import { useMutation } from '@tanstack/react-query'
import { aiApi } from '../api/aiApi'

/** The explicit "Explain this comparison" action (Phase 23). */
export function useAiExplainSnapshotComparison() {
  return useMutation({
    mutationFn: ({ fromSnapshotId, toSnapshotId }: { fromSnapshotId: string; toSnapshotId: string }) =>
      aiApi.explainSnapshotComparison({
        from_snapshot_id: fromSnapshotId,
        to_snapshot_id: toSnapshotId,
      }),
  })
}
