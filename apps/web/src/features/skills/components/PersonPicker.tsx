import { usePeople } from '@/hooks/usePeople'
import { Select } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'

interface PersonPickerProps {
  value: string | undefined
  onChange: (personId: string) => void
}

export function PersonPicker({ value, onChange }: PersonPickerProps) {
  const { data, isPending, isError, refetch } = usePeople()

  if (isPending) {
    return (
      <Select
        label="Person"
        options={[]}
        placeholder="Loading people…"
        disabled
        value=""
        onChange={() => {}}
      />
    )
  }

  if (isError || !data) {
    return (
      <div className="flex items-end gap-2">
        <Select
          label="Person"
          options={[]}
          placeholder="Couldn't load people"
          disabled
          value=""
          onChange={() => {}}
        />
        <Button variant="ghost" onClick={() => void refetch()}>
          Retry
        </Button>
      </div>
    )
  }

  return (
    <Select
      label="Person"
      value={value ?? ''}
      placeholder={data.items.length === 0 ? 'No people yet' : 'Select a person'}
      options={data.items.map((person) => ({
        value: person.id,
        label: person.display_name,
      }))}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}
