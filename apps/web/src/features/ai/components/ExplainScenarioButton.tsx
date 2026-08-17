import { useAiExplainScenario } from '../hooks/useAiExplainScenario'
import { AiTriggerButton } from './AiTriggerButton'

/** "Explain scenario impact" — Scenario workspace. */
export function ExplainScenarioButton({ scenarioId }: { scenarioId: string }) {
  const explain = useAiExplainScenario()

  return (
    <AiTriggerButton
      panelTitle="AI scenario explanation"
      buttonLabel="Explain scenario impact"
      pendingLabel="Explaining…"
      envelope={explain.data}
      isPending={explain.isPending}
      isError={explain.isError}
      error={explain.error}
      onTrigger={() => explain.mutate(scenarioId)}
    />
  )
}
