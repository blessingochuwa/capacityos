import type { ReactNode } from 'react'

export type BadgeVariant = 'neutral' | 'success' | 'info' | 'danger' | 'warning'

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  neutral: 'bg-slate-800 text-slate-300 ring-1 ring-slate-700',
  success: 'bg-emerald-950 text-emerald-300 ring-1 ring-emerald-800',
  info: 'bg-sky-950 text-sky-300 ring-1 ring-sky-800',
  danger: 'bg-rose-950 text-rose-300 ring-1 ring-rose-800',
  warning: 'bg-amber-950 text-amber-300 ring-1 ring-amber-800',
}

interface BadgeProps {
  variant: BadgeVariant
  children: ReactNode
  icon?: ReactNode
}

export function Badge({ variant, children, icon }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${VARIANT_CLASSES[variant]}`}
    >
      {icon}
      {children}
    </span>
  )
}
