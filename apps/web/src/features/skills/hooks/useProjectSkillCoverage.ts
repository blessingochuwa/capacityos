import { useQuery } from '@tanstack/react-query'
import { skillsApi } from '../api/skillsApi'
import type { DateRangeParams } from '../api/skillsApi'

export function useProjectSkillCoverage(
  projectId: string | undefined,
  range: DateRangeParams,
) {
  return useQuery({
    queryKey: [
      'projects',
      projectId,
      'skill-coverage',
      range.start_date,
      range.end_date,
    ],
    queryFn: () =>
      skillsApi.getProjectSkillCoverage(projectId as string, range),
    enabled: projectId !== undefined,
  })
}
