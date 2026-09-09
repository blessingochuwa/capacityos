import { Select } from '@/components/ui/Select'
import { ProjectFilterPicker } from '@/features/insights/components/ProjectFilterPicker'
import { STATUS_LABEL } from '../constants'
import { RISK_EXPOSURE_LEVELS, RISK_STATUSES } from '../types/risks'
import type { RiskExposure, RiskStatus } from '../types/risks'

interface OrgRiskFilterBarProps {
  projectId: string | undefined
  onProjectChange: (value: string | undefined) => void
  statusValue: RiskStatus | ''
  onStatusChange: (value: RiskStatus | '') => void
  exposureValue: RiskExposure | ''
  onExposureChange: (value: RiskExposure | '') => void
}

const STATUS_OPTIONS = RISK_STATUSES.map((status) => ({
  value: status,
  label: STATUS_LABEL[status],
}))

const EXPOSURE_OPTIONS = RISK_EXPOSURE_LEVELS.map((exposure) => ({
  value: exposure,
  label: exposure.charAt(0).toUpperCase() + exposure.slice(1),
}))

/** The org-wide Risk register's filter controls (Phase 47) — project,
 * status, and exposure, all applying through the existing
 * `GET /api/v1/risks` contract server-side; this component holds no
 * filtering logic of its own, mirroring
 * features/audit/components/AuditFilterBar.tsx and
 * features/users/components/UsersFilterBar.tsx. Reuses the existing
 * ProjectFilterPicker verbatim (the same "All projects" optional-filter
 * component the Insights page already uses) rather than building a
 * second project dropdown. Status and Exposure reuse this codebase's own
 * finite, authoritative vocabularies (RISK_STATUSES/RISK_EXPOSURE_LEVELS)
 * — never an invented taxonomy. */
export function OrgRiskFilterBar({
  projectId,
  onProjectChange,
  statusValue,
  onStatusChange,
  exposureValue,
  onExposureChange,
}: OrgRiskFilterBarProps) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="w-56">
        <ProjectFilterPicker value={projectId} onChange={onProjectChange} />
      </div>
      <div className="w-44">
        <Select
          label="Status"
          value={statusValue}
          placeholder="All statuses"
          options={STATUS_OPTIONS}
          onChange={(event) => onStatusChange(event.target.value as RiskStatus | '')}
        />
      </div>
      <div className="w-44">
        <Select
          label="Exposure"
          value={exposureValue}
          placeholder="All exposure levels"
          options={EXPOSURE_OPTIONS}
          onChange={(event) => onExposureChange(event.target.value as RiskExposure | '')}
        />
      </div>
    </div>
  )
}
