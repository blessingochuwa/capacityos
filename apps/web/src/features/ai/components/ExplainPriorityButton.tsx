import { useAiExplainPriority } from '../hooks/useAiExplainPriority'
import { AiTriggerButton } from './AiTriggerButton'

/** "Explain this score" — Prioritization overview, next to an existing
 * ProjectPriorityScore (Phase 19). */
export function ExplainPriorityButton({
  projectId,
  scoreId,
}: {
  projectId: string
  scoreId: string
}) {
  const explain = useAiExplainPriority()

  return (
    <AiTriggerButton
      panelTitle="AI priority explanation"
      buttonLabel="Explain this score"
      pendingLabel="Explaining…"
      envelope={explain.data}
      isPending={explain.isPending}
      isError={explain.isError}
      error={explain.error}
      onTrigger={() => explain.mutate({ projectId, scoreId })}
    />
  )
}
