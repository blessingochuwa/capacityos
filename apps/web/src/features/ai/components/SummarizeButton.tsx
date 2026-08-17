import { useAiSummary } from '../hooks/useAiSummary'
import { AiTriggerButton } from './AiTriggerButton'
import type { AIScopeEntityType } from '../types/ai'

interface SummarizeButtonProps {
  entityType: AIScopeEntityType
  entityId: string
  startDate: string
  endDate: string
}

/** "Summarize capacity" — Capacity and Insights pages. */
export function SummarizeButton({
  entityType,
  entityId,
  startDate,
  endDate,
}: SummarizeButtonProps) {
  const summary = useAiSummary()

  function handleTrigger() {
    summary.mutate({
      scope: { entity_type: entityType, entity_id: entityId },
      start_date: startDate,
      end_date: endDate,
    })
  }

  return (
    <AiTriggerButton
      panelTitle="AI summary"
      buttonLabel="Summarize with AI"
      pendingLabel="Summarizing…"
      envelope={summary.data}
      isPending={summary.isPending}
      isError={summary.isError}
      error={summary.error}
      onTrigger={handleTrigger}
    />
  )
}
