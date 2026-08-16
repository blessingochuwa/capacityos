import { Select } from '@/components/ui/Select'
import type { ImportMode } from '../types/importExport'

const MODE_OPTIONS: { value: ImportMode; label: string }[] = [
  { value: 'upsert', label: 'Upsert (create or update)' },
  { value: 'create_only', label: 'Create only' },
  { value: 'update_only', label: 'Update only' },
]

const MODE_DESCRIPTION: Record<ImportMode, string> = {
  upsert: 'Matching rows update the existing record; new rows create one.',
  create_only: 'A row matching an existing record is rejected, not updated.',
  update_only: 'A row with no existing match is rejected, not created.',
}

interface ImportModePickerProps {
  value: ImportMode
  onChange: (value: ImportMode) => void
}

export function ImportModePicker({ value, onChange }: ImportModePickerProps) {
  return (
    <div className="flex flex-col gap-1">
      <Select
        label="Mode"
        value={value}
        onChange={(event) => onChange(event.target.value as ImportMode)}
        options={MODE_OPTIONS}
      />
      <p className="text-xs text-slate-500">{MODE_DESCRIPTION[value]}</p>
    </div>
  )
}
