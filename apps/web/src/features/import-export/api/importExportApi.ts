import { apiGetBlob, apiPostFormData } from '@/api/client'
import type {
  ExportFormat,
  ImportApplyResult,
  ImportEntityType,
  ImportMode,
  ImportValidationReport,
} from '../types/importExport'

/** Thin typed wrappers over apps/api's imports/exports endpoints
 * (apps/api/app/api/v1/imports.py, exports.py). Unlike every other read-only
 * api module in this app, uploads/downloads deal in files, not JSON bodies —
 * see apiPostFormData/apiGetBlob in src/api/client.ts. */

export interface ExportScope {
  person_id?: string
  team_id?: string
  project_id?: string
}

export const importExportApi = {
  validate: (entityType: ImportEntityType, file: File, mode: ImportMode) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiPostFormData<ImportValidationReport>(
      `/api/v1/imports/${entityType}/validate`,
      formData,
      { mode },
    )
  },

  apply: (entityType: ImportEntityType, file: File, mode: ImportMode) => {
    const formData = new FormData()
    formData.append('file', file)
    return apiPostFormData<ImportApplyResult>(
      `/api/v1/imports/${entityType}/apply`,
      formData,
      { mode },
    )
  },

  downloadTemplate: (entityType: ImportEntityType, format: ExportFormat) =>
    apiGetBlob(`/api/v1/imports/${entityType}/template`, { format }),

  exportEntities: (
    entityType: ImportEntityType,
    format: ExportFormat,
    scope: ExportScope,
  ) => apiGetBlob(`/api/v1/exports/${entityType}`, { format, ...scope }),
}
