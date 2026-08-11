import type { InputHTMLAttributes } from 'react'

interface DateFieldProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'type'
> {
  label: string
}

export function DateField({
  label,
  id,
  className = '',
  ...props
}: DateFieldProps) {
  const inputId = id ?? label.toLowerCase().replace(/\s+/g, '-')
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={inputId} className="text-xs font-medium text-slate-400">
        {label}
      </label>
      <input
        id={inputId}
        type="date"
        className={`rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 ${className}`}
        {...props}
      />
    </div>
  )
}
