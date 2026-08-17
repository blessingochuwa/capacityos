import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { ErrorState } from '@/components/ui/ErrorState'
import { Skeleton } from '@/components/ui/Skeleton'
import { AiConfidenceBadge } from './AiConfidenceBadge'
import type { AIClaim, AIRecommendation, AIResponseEnvelope } from '../types/ai'

function ClaimList({ claims, tone }: { claims: AIClaim[]; tone: 'default' | 'danger' }) {
  if (claims.length === 0) return null
  return (
    <ul className="space-y-2">
      {claims.map((claim, index) => (
        <li
          key={index}
          className={`text-sm ${tone === 'danger' ? 'text-rose-200' : 'text-slate-200'}`}
        >
          <p>{claim.text}</p>
          {claim.source_references.length > 0 ? (
            <p className="mt-0.5 text-xs text-slate-500">
              Based on: {claim.source_references.map((ref) => ref.description).join('; ')}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

function RecommendationList({ recommendations }: { recommendations: AIRecommendation[] }) {
  if (recommendations.length === 0) return null
  return (
    <ul className="space-y-3">
      {recommendations.map((rec, index) => (
        <li key={index} className="rounded-md bg-indigo-950/30 px-3 py-2 text-sm">
          <p className="text-slate-100">{rec.recommendation}</p>
          <p className="mt-1 text-xs text-slate-400">{rec.rationale}</p>
          {rec.assumptions.length > 0 ? (
            <p className="mt-1 text-xs text-slate-500">
              Assumes: {rec.assumptions.join('; ')}
            </p>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

interface AiResultPanelProps {
  title: string
  envelope: AIResponseEnvelope | undefined
  isPending: boolean
  isError: boolean
  error: unknown
  onRetry: () => void
}

/**
 * The one place an AIInsightResponse gets rendered — every AI-triggering
 * button (SummarizeButton, ExplainSignalButton, ExplainScenarioButton) shows
 * its result through this panel so the visual language never drifts between
 * capabilities. Deliberately distinct from a deterministic Card: the "AI
 * explanation" label and confidence badge in the header, and the "AI-
 * generated" disclaimer in the body, keep this from ever being mistaken for
 * a system-computed signal (CLAUDE.md §21 — recommendations must never look
 * like a deterministic warning). Branches on three independent failure
 * modes: `isError` (a real HTTP/transport failure — ErrorState, matching
 * every other feature), and `envelope.status` `unavailable` (no provider
 * configured) / `error` (provider configured but the request failed) —
 * both expected, first-class states carried in the response body, not
 * exceptions.
 */
export function AiResultPanel({
  title,
  envelope,
  isPending,
  isError,
  error,
  onRetry,
}: AiResultPanelProps) {
  if (isPending) {
    return (
      <Card>
        <CardHeader title={title} />
        <CardBody>
          <Skeleton className="h-4 w-1/3" />
          <div className="mt-3 space-y-2">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        </CardBody>
      </Card>
    )
  }

  if (isError) {
    return (
      <Card>
        <CardHeader title={title} />
        <ErrorState error={error} onRetry={onRetry} title="AI explanation failed." />
      </Card>
    )
  }

  if (!envelope) {
    return null
  }

  if (envelope.status === 'unavailable') {
    return (
      <Card>
        <CardHeader title={title} />
        <CardBody>
          <p className="text-sm text-slate-400">
            {envelope.message ?? 'AI is not configured for this deployment.'}
          </p>
        </CardBody>
      </Card>
    )
  }

  if (envelope.status === 'error' || !envelope.response) {
    return (
      <Card>
        <CardHeader title={title} />
        <CardBody className="space-y-3">
          <p className="text-sm text-rose-300">
            {envelope.message ?? 'The AI provider could not complete this request.'}
          </p>
          <Button variant="secondary" onClick={onRetry}>
            Try again
          </Button>
        </CardBody>
      </Card>
    )
  }

  const response = envelope.response

  return (
    <Card>
      <CardHeader
        title={title}
        description="AI-generated interpretation of the data above — verify against it, not the other way around."
        action={<AiConfidenceBadge confidence={response.confidence} />}
      />
      <CardBody className="space-y-4">
        <p className="text-sm text-slate-100">{response.summary}</p>

        {response.key_findings.length > 0 ? (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Key findings
            </h3>
            <ClaimList claims={response.key_findings} tone="default" />
          </div>
        ) : null}

        {response.risks.length > 0 ? (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Risks
            </h3>
            <ClaimList claims={response.risks} tone="danger" />
          </div>
        ) : null}

        {response.recommendations.length > 0 ? (
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
              Worth considering
            </h3>
            <RecommendationList recommendations={response.recommendations} />
          </div>
        ) : null}

        <p className="border-t border-slate-800 pt-3 text-xs text-slate-500">
          Generated {new Date(response.generated_at).toLocaleString()} · {response.provider} ·{' '}
          {response.model}
        </p>
      </CardBody>
    </Card>
  )
}
