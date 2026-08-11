import type { ReactNode, TdHTMLAttributes, ThHTMLAttributes } from 'react'

interface TableProps {
  caption: string
  children: ReactNode
  className?: string
}

/** A real <table> (not a div-grid) so assistive tech gets row/column
 * semantics for free (spec §21). Wrapped in overflow-x-auto so a wide table
 * scrolls within itself on narrow viewports instead of the whole page
 * overflowing horizontally (spec §20). */
export function Table({ caption, children, className = '' }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table
        className={`w-full min-w-[640px] border-collapse text-sm ${className}`}
      >
        <caption className="sr-only">{caption}</caption>
        {children}
      </table>
    </div>
  )
}

export function Th({
  className = '',
  ...props
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={`border-b border-slate-800 px-4 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-400 ${className}`}
      {...props}
    />
  )
}

export function Td({
  className = '',
  ...props
}: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={`border-b border-slate-800/60 px-4 py-2.5 text-slate-200 ${className}`}
      {...props}
    />
  )
}
