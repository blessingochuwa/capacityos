import type { ChangeEvent, InputHTMLAttributes } from 'react'

interface FileInputProps
  extends Omit<
    InputHTMLAttributes<HTMLInputElement>,
    'type' | 'onChange' | 'value'
  > {
  label: string
  selectedFileName?: string | null
  onFileSelect: (file: File | null) => void
}

/** The app's first file-upload control (Phase 6 import) — follows Button's
 * prop-extends-native-element pattern. Reports the selected File itself
 * (not a change event) so callers never touch event.target.files. */
export function FileInput({
  label,
  selectedFileName,
  onFileSelect,
  id,
  className = '',
  accept = '.csv,.json',
  ...props
}: FileInputProps) {
  const inputId = id ?? label.toLowerCase().replace(/\s+/g, '-')

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onFileSelect(event.target.files?.[0] ?? null)
  }

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={inputId} className="text-xs font-medium text-slate-400">
        {label}
      </label>
      <input
        id={inputId}
        type="file"
        accept={accept}
        onChange={handleChange}
        className={`text-sm text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-slate-100 hover:file:bg-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 ${className}`}
        {...props}
      />
      {selectedFileName ? (
        <span className="text-xs text-slate-400">
          Selected: {selectedFileName}
        </span>
      ) : null}
    </div>
  )
}
