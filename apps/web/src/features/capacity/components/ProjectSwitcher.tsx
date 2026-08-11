import { useNavigate } from 'react-router-dom'
import { useProjects } from '@/hooks/useProjects'
import { Select } from '@/components/ui/Select'

/** A launcher, not a live filter: TeamCapacityRead has no project parameter,
 * so selecting a project here navigates to its own capacity view rather
 * than narrowing the team numbers on screen (which the API can't do). */
export function ProjectSwitcher() {
  const navigate = useNavigate()
  const { data, isPending, isError } = useProjects()

  if (isPending || isError || !data || data.items.length === 0) {
    return null
  }

  return (
    <Select
      label="Jump to project"
      value=""
      placeholder="View a project"
      options={data.items.map((project) => ({
        value: project.id,
        label: project.name,
      }))}
      onChange={(event) => {
        if (event.target.value) {
          void navigate(`/capacity/projects/${event.target.value}`)
        }
      }}
    />
  )
}
