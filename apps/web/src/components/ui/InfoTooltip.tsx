import { useEffect, useId, useRef, useState } from 'react'
import { InfoIcon } from './icons'

interface InfoTooltipProps {
  label: string
  children: string
}

/** Explainability primitive (spec §14: "never show a number without making
 * it possible to understand where it came from"). Click/keyboard-toggled
 * rather than hover-only, so it works for keyboard and touch users, not
 * just a mouse. */
export function InfoTooltip({ label, children }: InfoTooltipProps) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return

    function handlePointerDown(event: PointerEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setOpen(false)
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  return (
    <div className="relative inline-block" ref={containerRef}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`More about ${label}`}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex items-center rounded-full text-slate-500 hover:text-slate-300 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
      >
        <InfoIcon />
      </button>
      {open ? (
        <div
          id={panelId}
          role="tooltip"
          className="absolute left-1/2 top-full z-10 mt-1.5 w-56 -translate-x-1/2 rounded-md border border-slate-700 bg-slate-800 px-3 py-2 text-xs leading-relaxed text-slate-200 shadow-lg"
        >
          {children}
        </div>
      ) : null}
    </div>
  )
}
