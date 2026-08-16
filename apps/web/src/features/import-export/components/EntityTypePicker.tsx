import { Select } from '@/components/ui/Select'
import { IMPORT_ENTITY_TYPES, type ImportEntityType } from '../types/importExport'

interface EntityTypePickerProps {
  value: ImportEntityType
  onChange: (value: ImportEntityType) => void
  label?: string
}

export function EntityTypePicker({
  value,
  onChange,
  label = 'Entity',
}: EntityTypePickerProps) {
  return (
    <Select
      label={label}
      value={value}
      onChange={(event) => onChange(event.target.value as ImportEntityType)}
      options={IMPORT_ENTITY_TYPES}
    />
  )
}
