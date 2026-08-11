import { Button } from '@/components/ui/Button'
import { DateField } from '@/components/ui/DateField'
import {
  DATE_RANGE_PRESETS,
  nextWeek,
  resolvePreset,
  thisMonth,
  thisWeek,
  type DateRange,
  type DateRangePreset,
} from '../utils/dateRange'

interface DateRangeControlProps {
  range: DateRange
  onChange: (range: DateRange) => void
}

const PRESET_BUTTONS = DATE_RANGE_PRESETS.filter(
  (preset) => preset.id !== 'custom',
)

/** Which preset (if any) the current range matches — derived from the range
 * itself rather than tracked as separate state, so there's exactly one
 * source of truth for "what period is selected." Editing the date fields
 * directly naturally falls through to 'custom'. */
function detectActivePreset(range: DateRange): DateRangePreset {
  const today = new Date()
  if (
    range.start === thisWeek(today).start &&
    range.end === thisWeek(today).end
  )
    return 'this-week'
  if (
    range.start === nextWeek(today).start &&
    range.end === nextWeek(today).end
  )
    return 'next-week'
  if (
    range.start === thisMonth(today).start &&
    range.end === thisMonth(today).end
  )
    return 'this-month'
  return 'custom'
}

export function DateRangeControl({ range, onChange }: DateRangeControlProps) {
  const activePreset = detectActivePreset(range)

  function handlePresetClick(preset: DateRangePreset) {
    const resolved = resolvePreset(preset)
    if (resolved) onChange(resolved)
  }

  return (
    <div className="flex flex-wrap items-end gap-3">
      <div
        className="flex flex-wrap gap-1"
        role="group"
        aria-label="Date range presets"
      >
        {PRESET_BUTTONS.map((preset) => (
          <Button
            key={preset.id}
            type="button"
            variant={activePreset === preset.id ? 'primary' : 'ghost'}
            aria-pressed={activePreset === preset.id}
            onClick={() => handlePresetClick(preset.id)}
          >
            {preset.label}
          </Button>
        ))}
      </div>
      <DateField
        label="Start date"
        value={range.start}
        max={range.end}
        onChange={(event) => onChange({ ...range, start: event.target.value })}
      />
      <DateField
        label="End date"
        value={range.end}
        min={range.start}
        onChange={(event) => onChange({ ...range, end: event.target.value })}
      />
      {activePreset === 'custom' ? (
        <span className="pb-2 text-xs text-slate-500">Custom range</span>
      ) : null}
    </div>
  )
}
