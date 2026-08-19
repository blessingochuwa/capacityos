import { Select } from '@/components/ui/Select'
import { useUsers } from '../hooks/useUsers'

interface UserPickerProps {
  value: string | undefined
  onChange: (userId: string) => void
  /** Excluded from the option list — e.g. users who already hold a grant
   * for the resource currently being managed, so the picker only offers
   * users who could actually be granted access. */
  excludeUserIds?: string[]
}

export function UserPicker({ value, onChange, excludeUserIds = [] }: UserPickerProps) {
  const { data, isPending, isError } = useUsers()

  if (isPending || isError || !data) {
    return (
      <Select
        label="User"
        options={[]}
        placeholder={isError ? "Couldn't load users" : 'Loading users…'}
        disabled
        value=""
        onChange={() => {}}
      />
    )
  }

  const options = data.items
    .filter((user) => !excludeUserIds.includes(user.id))
    .map((user) => ({
      value: user.id,
      label: `${user.display_name} (${user.email}) — ${user.role}`,
    }))

  return (
    <Select
      label="User"
      value={value ?? ''}
      placeholder={options.length === 0 ? 'No eligible users' : 'Select a user'}
      options={options}
      onChange={(event) => onChange(event.target.value)}
    />
  )
}
