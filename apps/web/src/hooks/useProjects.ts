import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { projectsApi } from '@/api/entities'
import type { Project } from '@/types/entities'

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: projectsApi.list,
  })
}

export function useProjectsLookup(): Map<string, Project> {
  const { data } = useProjects()
  return useMemo(() => {
    const lookup = new Map<string, Project>()
    for (const project of data?.items ?? []) {
      lookup.set(project.id, project)
    }
    return lookup
  }, [data])
}
