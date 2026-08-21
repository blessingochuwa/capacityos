import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Select } from '@/components/ui/Select'
import { PersonPicker } from '@/features/skills/components/PersonPicker'
import { useCreateStakeholder, useUpdateStakeholder } from '../hooks/useStakeholderMutations'
import {
  STAKEHOLDER_DECISION_AUTHORITY_LEVELS,
  STAKEHOLDER_INFLUENCE_LEVELS,
  STAKEHOLDER_INTEREST_LEVELS,
} from '../types/stakeholders'
import type {
  Stakeholder,
  StakeholderDecisionAuthority,
  StakeholderInfluence,
  StakeholderInterest,
} from '../types/stakeholders'

const INFLUENCE_LABEL: Record<StakeholderInfluence, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
}

const DECISION_AUTHORITY_LABEL: Record<StakeholderDecisionAuthority, string> = {
  decision_maker: 'Decision maker',
  advisor: 'Advisor',
  informed: 'Informed only',
}

interface StakeholderFormProps {
  projectId: string
  /** When set, the form edits this stakeholder instead of creating a new
   * one — same component, mirroring how this codebase reuses one form
   * shape rather than a separate edit component. */
  stakeholder?: Stakeholder
  onDone?: () => void
  onCancel?: () => void
}

export function StakeholderForm({
  projectId,
  stakeholder,
  onDone,
  onCancel,
}: StakeholderFormProps) {
  const isEditing = stakeholder !== undefined
  const [name, setName] = useState(stakeholder?.name ?? '')
  const [role, setRole] = useState(stakeholder?.role ?? '')
  const [influence, setInfluence] = useState<StakeholderInfluence>(
    stakeholder?.influence ?? 'medium',
  )
  const [interest, setInterest] = useState<StakeholderInterest>(
    stakeholder?.interest ?? 'medium',
  )
  const [decisionAuthority, setDecisionAuthority] = useState<StakeholderDecisionAuthority>(
    stakeholder?.decision_authority ?? 'informed',
  )
  const [personId, setPersonId] = useState<string | undefined>(
    stakeholder?.person_id ?? undefined,
  )
  const [communicationNeeds, setCommunicationNeeds] = useState(
    stakeholder?.communication_needs ?? '',
  )
  const createStakeholder = useCreateStakeholder(projectId)
  const updateStakeholder = useUpdateStakeholder(projectId)
  const mutation = isEditing ? updateStakeholder : createStakeholder

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!name.trim() || !role.trim()) return

    if (isEditing) {
      const data: Record<string, unknown> = {}
      if (name.trim() !== stakeholder.name) data.name = name.trim()
      if (role.trim() !== stakeholder.role) data.role = role.trim()
      if (influence !== stakeholder.influence) data.influence = influence
      if (interest !== stakeholder.interest) data.interest = interest
      if (decisionAuthority !== stakeholder.decision_authority) {
        data.decision_authority = decisionAuthority
      }
      if ((personId ?? null) !== stakeholder.person_id) data.person_id = personId ?? null
      const trimmedNeeds = communicationNeeds.trim() || null
      if (trimmedNeeds !== stakeholder.communication_needs) {
        data.communication_needs = trimmedNeeds
      }
      if (Object.keys(data).length === 0) {
        onDone?.()
        return
      }
      updateStakeholder.mutate(
        { stakeholderId: stakeholder.id, data },
        { onSuccess: () => onDone?.() },
      )
      return
    }

    createStakeholder.mutate(
      {
        name: name.trim(),
        role: role.trim(),
        influence,
        interest,
        decision_authority: decisionAuthority,
        person_id: personId,
        communication_needs: communicationNeeds.trim() || undefined,
      },
      {
        onSuccess: () => {
          setName('')
          setRole('')
          setInfluence('medium')
          setInterest('medium')
          setDecisionAuthority('informed')
          setPersonId(undefined)
          setCommunicationNeeds('')
          onDone?.()
        },
      },
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1">
          <label htmlFor="stakeholder-name" className="text-xs font-medium text-slate-400">
            Name
          </label>
          <input
            id="stakeholder-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Who is this stakeholder?"
            className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="stakeholder-role" className="text-xs font-medium text-slate-400">
            Role
          </label>
          <input
            id="stakeholder-role"
            value={role}
            onChange={(event) => setRole(event.target.value)}
            placeholder="e.g. Sponsor, End user, Regulator"
            className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
          />
        </div>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-32">
          <Select
            label="Influence"
            value={influence}
            options={STAKEHOLDER_INFLUENCE_LEVELS.map((level) => ({
              value: level,
              label: INFLUENCE_LABEL[level],
            }))}
            onChange={(event) => setInfluence(event.target.value as StakeholderInfluence)}
          />
        </div>
        <div className="w-32">
          <Select
            label="Interest"
            value={interest}
            options={STAKEHOLDER_INTEREST_LEVELS.map((level) => ({
              value: level,
              label: INFLUENCE_LABEL[level],
            }))}
            onChange={(event) => setInterest(event.target.value as StakeholderInterest)}
          />
        </div>
        <div className="w-44">
          <Select
            label="Decision authority"
            value={decisionAuthority}
            options={STAKEHOLDER_DECISION_AUTHORITY_LEVELS.map((level) => ({
              value: level,
              label: DECISION_AUTHORITY_LABEL[level],
            }))}
            onChange={(event) =>
              setDecisionAuthority(event.target.value as StakeholderDecisionAuthority)
            }
          />
        </div>
        <div className="w-56">
          <PersonPicker value={personId} onChange={setPersonId} />
        </div>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="stakeholder-comms" className="text-xs font-medium text-slate-400">
          Communication needs
        </label>
        <input
          id="stakeholder-comms"
          value={communicationNeeds}
          onChange={(event) => setCommunicationNeeds(event.target.value)}
          placeholder="How and how often should this person be kept in the loop?"
          className="rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
        />
      </div>

      <div className="flex items-center gap-3">
        <Button
          type="submit"
          variant="primary"
          disabled={!name.trim() || !role.trim() || mutation.isPending}
        >
          {mutation.isPending
            ? isEditing
              ? 'Saving…'
              : 'Adding…'
            : isEditing
              ? 'Save changes'
              : 'Add stakeholder'}
        </Button>
        {isEditing ? (
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
        {mutation.isError ? (
          <p role="alert" className="text-xs text-rose-300">
            {mutation.error.message}
          </p>
        ) : null}
      </div>
    </form>
  )
}
