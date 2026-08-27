import { useAiExplainSnapshotComparison } from '../hooks/useAiExplainSnapshotComparison'
import { AiTriggerButton } from './AiTriggerButton'

/** "Explain this comparison" — Prioritization overview, next to an existing
 * Phase 22 snapshot comparison (Phase 23). */
export function ExplainSnapshotComparisonButton({
  fromSnapshotId,
  toSnapshotId,
}: {
  fromSnapshotId: string
  toSnapshotId: string
}) {
  const explain = useAiExplainSnapshotComparison()

  return (
    <AiTriggerButton
      panelTitle="AI snapshot comparison explanation"
      buttonLabel="Explain this comparison"
      pendingLabel="Explaining…"
      envelope={explain.data}
      isPending={explain.isPending}
      isError={explain.isError}
      error={explain.error}
      onTrigger={() => explain.mutate({ fromSnapshotId, toSnapshotId })}
    />
  )
}
