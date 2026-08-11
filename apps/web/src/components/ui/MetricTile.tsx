import type { ReactNode } from 'react'

interface MetricTileProps {
  label: string
  value: ReactNode
  tooltip?: ReactNode
  tone?: 'default' | 'danger' | 'success'
}

const TONE_CLASSES: Record<NonNullable<MetricTileProps['tone']>, string> = {
  default: 'text-slate-100',
  danger: 'text-rose-300',
  success: 'text-emerald-300',
}

export function MetricTile({
  label,
  value,
  tooltip,
  tone = 'default',
}: MetricTileProps) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-medium text-slate-400">{label}</span>
        {tooltip}
      </div>
      <span
        className={`text-2xl font-semibold tabular-nums ${TONE_CLASSES[tone]}`}
      >
        {value}
      </span>
    </div>
  )
}
