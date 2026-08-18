import { useState } from 'react'
import { PageHeader } from '@/components/layout/PageHeader'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/Button'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { FileInput } from '@/components/ui/FileInput'
import { Select } from '@/components/ui/Select'
import { useAuth } from '@/features/auth/context/AuthContext'
import { ViewOnlyNotice } from '@/features/auth/components/ViewOnlyNotice'
import { EntityTypePicker } from '../components/EntityTypePicker'
import { ExportPanel } from '../components/ExportPanel'
import { ImportModePicker } from '../components/ImportModePicker'
import { ImportRowTable } from '../components/ImportRowTable'
import { ValidationReportSummary } from '../components/ValidationReportSummary'
import { useApplyImport } from '../hooks/useApplyImport'
import { useDownloadTemplate } from '../hooks/useDownloadTemplate'
import { useValidateImport } from '../hooks/useValidateImport'
import type {
  ExportFormat,
  ImportEntityType,
  ImportMode,
} from '../types/importExport'

const TEMPLATE_FORMAT_OPTIONS: { value: ExportFormat; label: string }[] = [
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
]

export function ImportExportPage() {
  const { can } = useAuth()
  const canImport = can('import.use')
  const canExport = can('export.use')
  const [entityType, setEntityType] = useState<ImportEntityType>('person')
  const [mode, setMode] = useState<ImportMode>('upsert')
  const [templateFormat, setTemplateFormat] = useState<ExportFormat>('csv')
  const [file, setFile] = useState<File | null>(null)
  const [confirmingApply, setConfirmingApply] = useState(false)

  const downloadTemplate = useDownloadTemplate()
  const validateImport = useValidateImport()
  const applyImport = useApplyImport()

  function resetWorkflow() {
    validateImport.reset()
    applyImport.reset()
    setConfirmingApply(false)
  }

  function handleEntityTypeChange(value: ImportEntityType) {
    setEntityType(value)
    setFile(null)
    resetWorkflow()
  }

  function handleModeChange(value: ImportMode) {
    setMode(value)
    resetWorkflow()
  }

  function handleFileSelect(selected: File | null) {
    setFile(selected)
    resetWorkflow()
  }

  function handleValidate() {
    if (!file) return
    resetWorkflow()
    validateImport.mutate({ entityType, file, mode })
  }

  function handleApply() {
    if (!file) return
    applyImport.mutate(
      { entityType, file, mode },
      { onSuccess: () => setConfirmingApply(false) },
    )
  }

  const report = validateImport.data
  const applyResult = applyImport.data

  return (
    <div>
      <PageHeader
        title="Import / Export"
        description="Bring operational data into CapacityOS, or export what's already here — CLAUDE.md §39 Phase 6."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader
            title="Import"
            description="Nothing is written until you review the validation report and confirm."
          />
          <CardBody className="space-y-4">
            {!canImport ? (
              <ViewOnlyNotice message="Your role can view operational data but not import it." />
            ) : (
              <>
                <div className="grid gap-3 sm:grid-cols-2">
                  <EntityTypePicker
                    value={entityType}
                    onChange={handleEntityTypeChange}
                  />
                  <ImportModePicker value={mode} onChange={handleModeChange} />
                </div>

                <div className="flex flex-wrap items-end gap-3 border-t border-slate-800 pt-4">
                  <Select
                    label="Template format"
                    value={templateFormat}
                    onChange={(event) =>
                      setTemplateFormat(event.target.value as ExportFormat)
                    }
                    options={TEMPLATE_FORMAT_OPTIONS}
                    className="w-28"
                  />
                  <Button
                    variant="ghost"
                    onClick={() =>
                      downloadTemplate.mutate({
                        entityType,
                        format: templateFormat,
                      })
                    }
                    disabled={downloadTemplate.isPending}
                  >
                    {downloadTemplate.isPending
                      ? 'Downloading…'
                      : 'Download template'}
                  </Button>
                </div>

                <div className="border-t border-slate-800 pt-4">
                  <FileInput
                    label="File"
                    selectedFileName={file?.name}
                    onFileSelect={handleFileSelect}
                  />
                </div>

                <Button
                  variant="primary"
                  onClick={handleValidate}
                  disabled={!file || validateImport.isPending}
                >
                  {validateImport.isPending ? 'Validating…' : 'Validate'}
                </Button>

                {validateImport.isError ? (
                  <p role="alert" className="text-sm text-rose-300">
                    {validateImport.error instanceof ApiError
                      ? validateImport.error.message
                      : 'Validation failed. Try again.'}
                  </p>
                ) : null}

                {report ? (
                  <div className="space-y-4 border-t border-slate-800 pt-4">
                    <ValidationReportSummary report={report} />
                    <ImportRowTable rows={report.rows} />

                    {report.ready_to_apply && !applyResult?.applied ? (
                      <div className="space-y-2">
                        {confirmingApply ? (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-400">
                              Write {report.valid_create_count} new and{' '}
                              {report.valid_update_count} updated record
                              {report.valid_update_count === 1 ? '' : 's'}?
                            </span>
                            <Button
                              variant="primary"
                              onClick={handleApply}
                              disabled={applyImport.isPending}
                            >
                              {applyImport.isPending
                                ? 'Applying…'
                                : 'Confirm apply'}
                            </Button>
                            <Button
                              variant="ghost"
                              onClick={() => setConfirmingApply(false)}
                            >
                              Cancel
                            </Button>
                          </div>
                        ) : (
                          <Button
                            variant="primary"
                            onClick={() => setConfirmingApply(true)}
                          >
                            Apply
                          </Button>
                        )}
                      </div>
                    ) : null}

                    {applyImport.isError ? (
                      <p role="alert" className="text-sm text-rose-300">
                        {applyImport.error instanceof ApiError
                          ? applyImport.error.message
                          : 'Apply failed. Nothing was written.'}
                      </p>
                    ) : null}

                    {applyResult?.applied ? (
                      <p className="rounded-md bg-emerald-950/40 px-3 py-2 text-sm text-emerald-200">
                        Applied: {applyResult.created_count} created,{' '}
                        {applyResult.updated_count} updated,{' '}
                        {applyResult.unchanged_count} unchanged.
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Export"
            description="Source facts only — never a derived capacity or utilization value."
          />
          <CardBody>
            {canExport ? (
              <ExportPanel />
            ) : (
              <ViewOnlyNotice message="Your role doesn't include permission to export data." />
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
