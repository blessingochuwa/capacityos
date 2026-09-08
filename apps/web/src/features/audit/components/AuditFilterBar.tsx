import { Select } from '@/components/ui/Select'

interface AuditFilterBarProps {
  actorOptions: { value: string; label: string }[]
  actorValue: string
  onActorChange: (value: string) => void
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

/** The audit log's filter controls (Phase 43) — actor, and a since/until
 * date range. Both apply through the existing `GET /api/v1/audit`
 * contract server-side (`actor_user_id`, `start`, `end`); this component
 * holds no filtering logic of its own, mirroring
 * features/users/components/UsersFilterBar.tsx exactly. `action` and
 * `resource_type`, though also real query parameters, are deliberately
 * NOT exposed as filter controls here: apps/api/app/models/enums.py's own
 * `AuditAction` docstring calls it "an open... vocabulary" expected to
 * grow with the product, so a dropdown built from it would either
 * duplicate that backend-owned list (a drift risk) or be built from only
 * the currently-loaded page's distinct values (which would misrepresent
 * completeness — exactly what the Phase 43 brief warns against). Both
 * remain visible as plain table columns instead. */
export function AuditFilterBar({
  actorOptions,
  actorValue,
  onActorChange,
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
