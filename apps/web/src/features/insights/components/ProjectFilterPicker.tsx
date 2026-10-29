import { useProjects } from '@/hooks/useProjects'
import { Select } from '@/components/ui/Select'

interface ProjectFilterPickerProps {
  value: string | undefined
  onChange: (projectId: string | undefined) => void
  /** Overrides Select's label-derived id ("project"). Required whenever a
   * page renders two pickers at once (e.g. the per-project and org-wide
   * registers, Phase 48) — otherwise both share id="project" and the
   * second picker's label points at the first select, leaving the second
   * one without an accessible name. */
  id?: string
}

/** An optional narrowing filter (unlike TeamPicker, which is required) — an
 * empty selection means "every project this team's people touch," not "no
 * project," so the placeholder doubles as the clear option. */
export function ProjectFilterPicker({
  value,
  onChange,
  id,
}: ProjectFilterPickerProps) {
  const { data, isPending, isError } = useProjects()

  if (isPending || isError || !data) {
    return (
      <Select
        id={id}
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
      id={id}
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
