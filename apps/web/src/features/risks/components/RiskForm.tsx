import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { PersonPicker } from '@/features/skills/components/PersonPicker'
import { useCreateRisk } from '../hooks/useRiskMutations'
import { RISK_IMPACT_LEVELS, RISK_PROBABILITY_LEVELS } from '../types/risks'
import type { RiskImpact, RiskProbability } from '../types/risks'

const LEVEL_LABEL: Record<RiskProbability, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
}

interface RiskFormProps {
  projectId: string
}

export function RiskForm({ projectId }: RiskFormProps) {
  const [description, setDescription] = useState('')
  const [cause, setCause] = useState('')
  const [potentialEffect, setPotentialEffect] = useState('')
  const [probability, setProbability] = useState<RiskProbability>('medium')
  const [impact, setImpact] = useState<RiskImpact>('medium')
  const [response, setResponse] = useState('')
  const [ownerPersonId, setOwnerPersonId] = useState<string | undefined>(undefined)
  const [reviewDate, setReviewDate] = useState('')
  const createRisk = useCreateRisk(projectId)

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!description.trim()) return
    createRisk.mutate(
      {
        description: description.trim(),
        cause: cause.trim() || undefined,
        potential_effect: potentialEffect.trim() || undefined,
        probability,
        impact,
        response: response.trim() || undefined,
        owner_person_id: ownerPersonId,
        review_date: reviewDate || undefined,
      },
      {
        onSuccess: () => {
          setDescription('')
          setCause('')
          setPotentialEffect('')
          setProbability('medium')
          setImpact('medium')
          setResponse('')
          setOwnerPersonId(undefined)
          setReviewDate('')
        },
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="risk-description" className="text-xs font-medium text-slate-400">
          Description
        </label>
        <input
          id="risk-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          placeholder="What is the risk?"
          className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
        />
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor="risk-cause" className="text-xs font-medium text-slate-400">
            Cause
          </label>
          <input
            id="risk-cause"
            value={cause}
            onChange={(event) => setCause(event.target.value)}
            placeholder="Why might this happen?"
            className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="risk-effect" className="text-xs font-medium text-slate-400">
            Potential effect
          </label>
          <input
            id="risk-effect"
            value={potentialEffect}
            onChange={(event) => setPotentialEffect(event.target.value)}
            placeholder="What happens if it does?"
            className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-32">
          <Select
            label="Probability"
            value={probability}
            options={RISK_PROBABILITY_LEVELS.map((level) => ({
              value: level,
              label: LEVEL_LABEL[level],
            }))}
            onChange={(event) => setProbability(event.target.value as RiskProbability)}
          />
        </div>
        <div className="w-32">
          <Select
            label="Impact"
            value={impact}
            options={RISK_IMPACT_LEVELS.map((level) => ({
              value: level,
              label: LEVEL_LABEL[level],
            }))}
            onChange={(event) => setImpact(event.target.value as RiskImpact)}
          />
        </div>
        <div className="w-56">
          <PersonPicker value={ownerPersonId} onChange={setOwnerPersonId} />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="risk-review-date" className="text-xs font-medium text-slate-400">
            Review date
          </label>
          <input
            id="risk-review-date"
            type="date"
            value={reviewDate}
            onChange={(event) => setReviewDate(event.target.value)}
            className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
          />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="risk-response" className="text-xs font-medium text-slate-400">
          Planned response
        </label>
        <input
          id="risk-response"
          value={response}
          onChange={(event) => setResponse(event.target.value)}
          placeholder="What will be done about it?"
          className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
        />
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" disabled={!description.trim() || createRisk.isPending}>
          {createRisk.isPending ? 'Adding…' : 'Add risk'}
        </Button>
        {createRisk.isError ? (
          <p role="alert" className="text-xs text-rose-300">
            {createRisk.error.message}
          </p>
        ) : null}
      </div>
    </form>
  )
}
