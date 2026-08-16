import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { makeImportValidationReport } from '@/test/fixtures'
import { ValidationReportSummary } from './ValidationReportSummary'

describe('ValidationReportSummary', () => {
  it('shows the file-level error and nothing else when the whole file failed', () => {
    render(
      <ValidationReportSummary
        report={makeImportValidationReport({
          file_error: {
            field: null,
            code: 'unsupported_format',
            message: 'Upload a .csv or .json file.',
          },
          total_rows: 0,
          ready_to_apply: false,
        })}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Upload a .csv or .json file.',
    )
  })

  it('shows a ready-to-apply banner when every row is clean', () => {
    render(
      <ValidationReportSummary
        report={makeImportValidationReport({
          total_rows: 3,
          valid_create_count: 2,
          valid_update_count: 1,
          invalid_count: 0,
          ready_to_apply: true,
        })}
      />,
    )
    expect(screen.getByText('Ready to apply.')).toBeInTheDocument()
  })

  it('shows a blocking message with the invalid row count when rows need correction', () => {
    render(
      <ValidationReportSummary
        report={makeImportValidationReport({
          total_rows: 3,
          valid_create_count: 1,
          invalid_count: 2,
          ready_to_apply: false,
        })}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      '2 rows need correction before this can be applied.',
    )
  })
})
