import { MetricTile } from '@/components/ui/MetricTile'
import type { ImportValidationReport } from '../types/importExport'

/** The counts a user needs before deciding to apply — spec step 16 ("42
 * records will be created / 63 updated / 9 unchanged / 6 need correction"),
 * never an elaborate spreadsheet-style preview. */
export function ValidationReportSummary({
  report,
}: {
  report: ImportValidationReport
}) {
  if (report.file_error) {
    return (
      <div
        role="alert"
        className="rounded-md bg-rose-950/40 px-3 py-2 text-sm text-rose-200"
      >
        {report.file_error.message}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <MetricTile label="Rows received" value={report.total_rows} />
        <MetricTile
          label="Will create"
          value={report.valid_create_count}
          tone="success"
        />
        <MetricTile label="Will update" value={report.valid_update_count} />
        <MetricTile
          label="Unchanged"
          value={report.valid_unchanged_count}
        />
      </div>
      {report.invalid_count > 0 ? (
        <p
          role="alert"
          className="rounded-md bg-rose-950/40 px-3 py-2 text-sm text-rose-200"
        >
          {report.invalid_count} row
          {report.invalid_count === 1 ? '' : 's'} need correction before this
          can be applied.
        </p>
      ) : report.total_rows === 0 ? (
        <p className="text-sm text-slate-400">The file has no data rows.</p>
      ) : (
        <p className="rounded-md bg-emerald-950/40 px-3 py-2 text-sm text-emerald-200">
          Ready to apply.
        </p>
      )}
    </div>
  )
}
