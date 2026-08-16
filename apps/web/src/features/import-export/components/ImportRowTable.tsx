import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { Table, Td, Th } from '@/components/ui/Table'
import { ImportRowStatusBadge } from './ImportRowStatusBadge'
import type { ImportRowResult } from '../types/importExport'

/** Only invalid/create/update rows show by default — an unchanged row is
 * rarely interesting, and the spec explicitly warns against building an
 * elaborate spreadsheet-style preview (step 16). "Show all rows" reveals
 * the rest for anyone who wants to audit the whole file. */
export function ImportRowTable({ rows }: { rows: ImportRowResult[] }) {
  const [showAll, setShowAll] = useState(false)

  const visibleRows = showAll
    ? rows
    : rows.filter((row) => row.status !== 'valid_unchanged')
  const hiddenCount = rows.length - visibleRows.length

  if (rows.length === 0) {
    return (
      <EmptyState
        title="No rows to show"
        description="Upload a file and validate it to see row-level results here."
      />
    )
  }

  if (visibleRows.length === 0) {
    return (
      <EmptyState
        title="Every row is unchanged"
        description="Nothing in this file differs from what's already stored."
        action={
          <Button variant="ghost" onClick={() => setShowAll(true)}>
            Show all {rows.length} rows
          </Button>
        }
      />
    )
  }

  return (
    <div className="space-y-2">
      <Table caption="Import row results">
        <thead>
          <tr>
            <Th>Row</Th>
            <Th>Status</Th>
            <Th>Identity</Th>
            <Th>Errors</Th>
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row) => (
            <tr key={row.row_number}>
              <Td className="tabular-nums">{row.row_number}</Td>
              <Td>
                <ImportRowStatusBadge status={row.status} />
              </Td>
              <Td className="max-w-[16rem] break-words">
                {row.identity ?? '—'}
              </Td>
              <Td className="max-w-[20rem]">
                {row.errors.length === 0 ? (
                  '—'
                ) : (
                  <ul className="space-y-0.5">
                    {row.errors.map((error, index) => (
                      <li key={index} className="break-words text-rose-300">
                        {error.field ? `${error.field}: ` : ''}
                        {error.message}
                      </li>
                    ))}
                  </ul>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      {hiddenCount > 0 ? (
        <Button variant="ghost" onClick={() => setShowAll(true)}>
          Show {hiddenCount} unchanged row{hiddenCount === 1 ? '' : 's'}
        </Button>
      ) : null}
    </div>
  )
}
