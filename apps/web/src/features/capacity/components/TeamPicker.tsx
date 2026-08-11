import { useTeams } from '@/hooks/useTeams'
import { Select } from '@/components/ui/Select'
import { Button } from '@/components/ui/Button'

interface TeamPickerProps {
  value: string | undefined
  onChange: (teamId: string) => void
}

export function TeamPicker({ value, onChange }: TeamPickerProps) {
  const { data, isPending, isError, refetch } = useTeams()

  if (isPending) {
    return (
      <Select
        label="Team"
        options={[]}
        placeholder="Loading teams…"
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
          label="Team"
          options={[]}
          placeholder="Couldn't load teams"
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
      label="Team"
      value={value ?? ''}
      placeholder={data.items.length === 0 ? 'No teams yet' : 'Select a team'}
      options={data.items.map((team) => ({ value: team.id, label: team.name }))}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}
