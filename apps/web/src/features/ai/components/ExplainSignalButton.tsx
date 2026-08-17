import { useAiExplainSignal } from '../hooks/useAiExplainSignal'
import { AiTriggerButton } from './AiTriggerButton'
import type { Signal } from '@/features/insights/types/insights'

/** "Explain these signals" (Insights) — also covers "Explain this
 * bottleneck" (Skills): skill_gap/single_skill_holder/skill_concentration
 * are signal types like any other, so this one button/endpoint handles
 * both without a separate bottleneck-specific capability. */
export function ExplainSignalButton({ signal }: { signal: Signal }) {
  const explain = useAiExplainSignal()

  function handleTrigger() {
    explain.mutate({
      scope: { entity_type: signal.entity_type, entity_id: signal.entity_id },
      signal_type: signal.type,
      start_date: signal.start_date,
      end_date: signal.end_date,
    })
  }

  return (
    <AiTriggerButton
      panelTitle="AI explanation"
      buttonLabel="Explain with AI"
      pendingLabel="Explaining…"
      envelope={explain.data}
      isPending={explain.isPending}
      isError={explain.isError}
      error={explain.error}
      onTrigger={handleTrigger}
    />
  )
}
