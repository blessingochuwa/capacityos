import { useProjects } from '@/hooks/useProjects'
import { Select } from '@/components/ui/Select'

interface ProjectFilterPickerProps {
  value: string | undefined
  onChange: (projectId: string | undefined) => void
}

/** An optional narrowing filter (unlike TeamPicker, which is required) — an
 * empty selection means "every project this team's people touch," not "no
 * project," so the placeholder doubles as the clear option. */
export function ProjectFilterPicker({
  value,
  onChange,
}: ProjectFilterPickerProps) {
  const { data, isPending, isError } = useProjects()

  if (isPending || isError || !data) {
    return (
      <Select
        label="Project"
        options={[]}
        placeholder="All projects"
        disabled
        value=""
        onChange={() => {}}
      />
    )
  }

  return (
    <Select
      label="Project"
      value={value ?? ''}
      placeholder="All projects"
      options={data.items.map((project) => ({
        value: project.id,
        label: project.name,
      }))}
      onChange={(event) => onChange(event.target.value || undefined)}
    />
  )
}
