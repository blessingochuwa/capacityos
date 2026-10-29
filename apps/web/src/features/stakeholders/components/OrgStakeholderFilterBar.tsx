import { Select } from '@/components/ui/Select'
import { ProjectFilterPicker } from '@/features/insights/components/ProjectFilterPicker'
import { DECISION_AUTHORITY_LABEL, levelLabel } from '../constants'
import {
  STAKEHOLDER_DECISION_AUTHORITY_LEVELS,
  STAKEHOLDER_INFLUENCE_LEVELS,
  STAKEHOLDER_INTEREST_LEVELS,
} from '../types/stakeholders'
import type {
  StakeholderDecisionAuthority,
  StakeholderInfluence,
  StakeholderInterest,
} from '../types/stakeholders'

interface OrgStakeholderFilterBarProps {
  projectId: string | undefined
  onProjectChange: (value: string | undefined) => void
  influenceValue: StakeholderInfluence | ''
  onInfluenceChange: (value: StakeholderInfluence | '') => void
  interestValue: StakeholderInterest | ''
  onInterestChange: (value: StakeholderInterest | '') => void
  decisionAuthorityValue: StakeholderDecisionAuthority | ''
  onDecisionAuthorityChange: (value: StakeholderDecisionAuthority | '') => void
}

const INFLUENCE_OPTIONS = STAKEHOLDER_INFLUENCE_LEVELS.map((level) => ({
  value: level,
  label: levelLabel(level),
}))

const INTEREST_OPTIONS = STAKEHOLDER_INTEREST_LEVELS.map((level) => ({
  value: level,
  label: levelLabel(level),
}))

const DECISION_AUTHORITY_OPTIONS = STAKEHOLDER_DECISION_AUTHORITY_LEVELS.map((level) => ({
  value: level,
  label: DECISION_AUTHORITY_LABEL[level],
}))

/** The org-wide Stakeholder register's filter controls (Phase 48) —
 * project, influence, interest, and decision authority, every one applied
 * server-side by `GET /api/v1/stakeholders`; this component holds no
 * filtering logic of its own, mirroring OrgRiskFilterBar (Phase 47).
 * Every option list is the codebase's own finite, DB-CHECK-constrained
 * vocabulary — never an invented grouping such as a power/interest
 * quadrant (CLAUDE.md §16/§17: no derived stakeholder classification). */
export function OrgStakeholderFilterBar({
  projectId,
  onProjectChange,
  influenceValue,
  onInfluenceChange,
  interestValue,
  onInterestChange,
  decisionAuthorityValue,
  onDecisionAuthorityChange,
}: OrgStakeholderFilterBarProps) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="w-56">
        <ProjectFilterPicker id="org-stakeholder-project" value={projectId} onChange={onProjectChange} />
      </div>
      <div className="w-40">
        <Select
          label="Influence"
          value={influenceValue}
          placeholder="All influence levels"
          options={INFLUENCE_OPTIONS}
          onChange={(event) => onInfluenceChange(event.target.value as StakeholderInfluence | '')}
        />
      </div>
      <div className="w-40">
        <Select
          label="Interest"
          value={interestValue}
          placeholder="All interest levels"
          options={INTEREST_OPTIONS}
          onChange={(event) => onInterestChange(event.target.value as StakeholderInterest | '')}
        />
      </div>
      <div className="w-48">
        <Select
          label="Decision authority"
          value={decisionAuthorityValue}
          placeholder="All decision authority"
          options={DECISION_AUTHORITY_OPTIONS}
          onChange={(event) =>
            onDecisionAuthorityChange(event.target.value as StakeholderDecisionAuthority | '')
          }
        />
      </div>
    </div>
  )
}
