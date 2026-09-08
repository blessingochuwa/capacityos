import { Select } from '@/components/ui/Select'

interface AuditFilterBarProps {
  actorOptions: { value: string; label: string }[]
  actorValue: string
  onActorChange: (value: string) => void
  actionValue: string
  onActionChange: (value: string) => void
  resourceTypeValue: string
  onResourceTypeChange: (value: string) => void
  /** `datetime-local` input values (e.g. "2026-01-15T09:30"), local time —
   * converted to an ISO instant only where sent to the API (AuditLogPage),
   * never here. */
  startValue: string
  onStartChange: (value: string) => void
  endValue: string
  onEndChange: (value: string) => void
}

const INPUT_CLASS =
  'rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400'

/** The audit log's filter controls — actor, action, resource type, and a
 * since/until date range. All five apply through the existing
 * `GET /api/v1/audit` contract server-side (`actor_user_id`, `action`,
 * `resource_type`, `start`, `end`); this component holds no filtering
 * logic of its own, mirroring features/users/components/UsersFilterBar.tsx.
 *
 * Action and Resource type (Phase 44) are deliberately PLAIN TEXT inputs,
 * not dropdowns: apps/api/app/models/enums.py's own `AuditAction`
 * docstring calls it "an open... vocabulary" expected to grow with the
 * product, so a dropdown would either duplicate that backend-owned list
 * (a drift risk) or be built from only the currently-loaded page's
 * distinct values (misrepresenting completeness — see docs/adr/0043).
 * Both match the value typed EXACTLY against `AuditEvent.action` /
 * `AuditEvent.resource_type` server-side (an equality comparison, not a
 * substring search — see `app/repositories/audit_event.py::list_filtered`),
 * so the placeholder text demonstrates the expected format ("e.g.
 * person.create") without implying the UI knows every possible value. */
export function AuditFilterBar({
  actorOptions,
  actorValue,
  onActorChange,
  actionValue,
  onActionChange,
  resourceTypeValue,
  onResourceTypeChange,
  startValue,
  onStartChange,
  endValue,
  onEndChange,
}: AuditFilterBarProps) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="w-64">
        <Select
          label="Actor"
          value={actorValue}
          placeholder="All actors"
          options={actorOptions}
          onChange={(event) => onActorChange(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="audit-action" className="text-xs font-medium text-slate-400">
          Action
        </label>
        <input
          id="audit-action"
          type="search"
          value={actionValue}
          onChange={(event) => onActionChange(event.target.value)}
          placeholder="e.g. person.create"
          className={`${INPUT_CLASS} w-48`}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="audit-resource-type" className="text-xs font-medium text-slate-400">
          Resource type
        </label>
        <input
          id="audit-resource-type"
          type="search"
          value={resourceTypeValue}
          onChange={(event) => onResourceTypeChange(event.target.value)}
          placeholder="e.g. project"
          className={`${INPUT_CLASS} w-40`}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="audit-since" className="text-xs font-medium text-slate-400">
          Since
        </label>
        <input
          id="audit-since"
          type="datetime-local"
          value={startValue}
          onChange={(event) => onStartChange(event.target.value)}
          className={INPUT_CLASS}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="audit-until" className="text-xs font-medium text-slate-400">
          Until
        </label>
        <input
          id="audit-until"
          type="datetime-local"
          value={endValue}
          onChange={(event) => onEndChange(event.target.value)}
          className={INPUT_CLASS}
        />
      </div>
    </div>
  )
}
