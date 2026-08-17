import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { AiResultPanel } from './AiResultPanel'
import type { AIResponseEnvelope } from '../types/ai'

interface AiTriggerButtonProps {
  panelTitle: string
  buttonLabel: string
  pendingLabel: string
  envelope: AIResponseEnvelope | undefined
  isPending: boolean
  isError: boolean
  error: unknown
  onTrigger: () => void
}

/**
 * Shared button + result-panel shell for every AI capability
 * (SummarizeButton/ExplainSignalButton/ExplainScenarioButton) — one place
 * for "track whether the user has triggered this yet, render AiResultPanel
 * below once they have" so it can't drift between call sites. Always
 * clickable regardless of whether a provider is configured: the resulting
 * AiResultPanel shows the backend's own clear "AI is not configured for
 * this deployment" message rather than a pre-emptively disabled button —
 * that message is a real, informative UI state the spec calls out
 * explicitly, not something to hide behind a disabled control.
 */
export function AiTriggerButton({
  panelTitle,
  buttonLabel,
  pendingLabel,
  envelope,
  isPending,
  isError,
  error,
  onTrigger,
}: AiTriggerButtonProps) {
  const [triggered, setTriggered] = useState(false)

  function handleClick() {
    setTriggered(true)
    onTrigger()
  }

  return (
    <div className="space-y-4">
      <Button variant="secondary" onClick={handleClick} disabled={isPending}>
        {isPending ? pendingLabel : buttonLabel}
      </Button>
      {triggered ? (
        <AiResultPanel
          title={panelTitle}
          envelope={envelope}
          isPending={isPending}
          isError={isError}
          error={error}
          onRetry={handleClick}
        />
      ) : null}
    </div>
  )
}
