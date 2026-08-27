import { useAiExplainScenarioPriorityComparison } from '../hooks/useAiExplainScenarioPriorityComparison'
import { AiTriggerButton } from './AiTriggerButton'

/** "Explain this comparison" — Scenario workspace, next to an existing
 * Phase 20 baseline-vs-scenario priority comparison (Phase 26). */
export function ExplainScenarioPriorityComparisonButton({
  scenarioId,
  frameworkId,
}: {
  scenarioId: string
  frameworkId: string
}) {
  const explain = useAiExplainScenarioPriorityComparison()

  return (
    <AiTriggerButton
      panelTitle="AI prioritization comparison explanation"
      buttonLabel="Explain this comparison"
      pendingLabel="Explaining…"
      envelope={explain.data}
      isPending={explain.isPending}
      isError={explain.isError}
      error={explain.error}
      onTrigger={() => explain.mutate({ scenarioId, frameworkId })}
    />
  )
}
