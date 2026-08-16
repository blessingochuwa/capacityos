import { useMutation } from '@tanstack/react-query'
import { importExportApi } from '../api/importExportApi'
import type { ImportEntityType, ImportMode } from '../types/importExport'

/** Stage A of the validate-then-apply flow (docs/adr/0006-phase-6-import-export.md)
 * — never writes anything, so it needs no cache invalidation. */
export function useValidateImport() {
  return useMutation({
    mutationFn: ({
      entityType,
      file,
      mode,
    }: {
      entityType: ImportEntityType
      file: File
      mode: ImportMode
    }) => importExportApi.validate(entityType, file, mode),
  })
}
