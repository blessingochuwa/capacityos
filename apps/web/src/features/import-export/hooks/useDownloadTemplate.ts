import { useMutation } from '@tanstack/react-query'
import { importExportApi } from '../api/importExportApi'
import { saveBlob } from '../utils/download'
import type { ExportFormat, ImportEntityType } from '../types/importExport'

export function useDownloadTemplate() {
  return useMutation({
    mutationFn: async ({
      entityType,
      format,
    }: {
      entityType: ImportEntityType
      format: ExportFormat
    }) => {
      const { blob, filename } = await importExportApi.downloadTemplate(
        entityType,
        format,
      )
      saveBlob(blob, filename)
    },
  })
}
