import { Table, Td, Th } from '@/components/ui/Table'
import { EmptyState } from '@/components/ui/EmptyState'
import type { AvailabilityException } from '@/types/entities'
import { formatAvailabilityType, formatHours } from '../utils/presentation'

interface AvailabilityExceptionsListProps {
  exceptions: AvailabilityException[]
}

/** The availability exceptions behind a person's "unavailable hours" —
 * hours=null renders as "Fully unavailable" per the domain semantics in
 * app/models/availability_exception.py, never as "0h" or blank. */
export function AvailabilityExceptionsList({
  exceptions,
}: AvailabilityExceptionsListProps) {
  if (exceptions.length === 0) {
    return <EmptyState title="No availability exceptions in this period." />
  }

  return (
    <Table caption="Availability exceptions">
      <thead>
        <tr>
          <Th scope="col">Type</Th>
          <Th scope="col">Period</Th>
          <Th scope="col" className="text-right">
            Availability
          </Th>
          <Th scope="col">Notes</Th>
        </tr>
      </thead>
      <tbody>
        {exceptions.map((exception) => (
          <tr key={exception.id}>
            <Td>{formatAvailabilityType(exception.availability_type)}</Td>
            <Td>
              {exception.start_date} – {exception.end_date}
            </Td>
            <Td className="text-right tabular-nums">
              {exception.hours === null
                ? 'Fully unavailable'
                : `${formatHours(exception.hours)}/day`}
            </Td>
            <Td className="text-slate-400">{exception.notes ?? '—'}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  )
}
