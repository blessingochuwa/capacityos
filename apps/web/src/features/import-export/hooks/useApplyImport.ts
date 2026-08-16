import { useMutation, useQueryClient } from '@tanstack/react-query'
import { importExportApi } from '../api/importExportApi'
import type { ImportEntityType, ImportMode } from '../types/importExport'

/** Entity types with an existing shared list hook elsewhere in the app
 * (src/hooks/use{People,Projects,Teams}.ts) whose cached data a successful
 * apply can make stale. Allocation/WorkingSchedule/AvailabilityException/
 * TeamMembership have no standalone top-level list query today — the
 * capacity/insights views that derive from them fetch fresh on navigation,
 * so there's nothing further to invalidate for those. */
const INVALIDATES: Partial<Record<ImportEntityType, string>> = {
  person: 'people',
  project: 'projects',
  team: 'teams',
}

/** Stage B of the validate-then-apply flow — re-validates the same file
 * server-side and only writes if every row is clean
 * (docs/adr/0006-phase-6-import-export.md). */
export function useApplyImport() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      entityType,
      file,
      mode,
    }: {
      entityType: ImportEntityType
      file: File
      mode: ImportMode
    }) => importExportApi.apply(entityType, file, mode),
    onSuccess: (result, { entityType }) => {
      if (!result.applied) return
      const key = INVALIDATES[entityType]
      if (key) {
        void queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
  })
}
