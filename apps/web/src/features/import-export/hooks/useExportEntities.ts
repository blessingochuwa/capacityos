import { useMutation } from '@tanstack/react-query'
import { importExportApi, type ExportScope } from '../api/importExportApi'
import { saveBlob } from '../utils/download'
import type { ExportFormat, ImportEntityType } from '../types/importExport'

export function useExportEntities() {
  return useMutation({
    mutationFn: async ({
      entityType,
      format,
      scope,
    }: {
      entityType: ImportEntityType
      format: ExportFormat
      scope: ExportScope
    }) => {
      const { blob, filename } = await importExportApi.exportEntities(
        entityType,
        format,
        scope,
      )
      saveBlob(blob, filename)
    },
  })
}
