import { EmptyState } from '@/components/ui/EmptyState'
import { formatDateRange } from '@/features/capacity/utils/presentation'
import { SeverityBadge } from './SeverityBadge'
import { signalKey } from '../utils/presentation'
import type { Signal } from '../types/insights'

interface SignalListProps {
  signals: Signal[]
  selectedKey?: string
  onSelect?: (key: string) => void
}

/** Renders signals in the order the backend already returned them
 * (InsightService._prioritize) — never re-sorted here. */
export function SignalList({ signals, selectedKey, onSelect }: SignalListProps) {
  if (signals.length === 0) {
    return (
      <EmptyState
        title="No signals — this team is healthy for this period."
        description="Over-allocation, capacity risk, and planning signals will appear here as soon as one is detected."
      />
    )
  }

  return (
    <ul className="space-y-2">
      {signals.map((signal) => {
        const key = signalKey(signal)
        const selected = key === selectedKey
        return (
          <li key={key}>
            <button
              type="button"
              onClick={() => onSelect?.(key)}
              aria-pressed={selected}
              className={`flex w-full flex-col gap-1 rounded-md border px-3 py-2 text-left text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 ${
                selected
                  ? 'border-indigo-500 bg-slate-800'
                  : 'border-slate-800 bg-slate-900/40 hover:border-slate-700'
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={signal.severity} />
                <span className="font-medium text-slate-100">
                  {signal.entity_label}
                </span>
                <span className="text-xs text-slate-500">
                  {formatDateRange(signal.start_date, signal.end_date)}
                </span>
              </div>
              <p className="text-slate-300">{signal.explanation}</p>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
