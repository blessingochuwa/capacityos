/** Persistent visual distinction between "current plan" and "what-if
 * scenario" (prompt §29/§16 UX safety) — every scenario workspace surface
 * carries this so a user can never mistake scenario numbers for live data. */
export function ScenarioBanner() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-amber-800/60 bg-amber-950/40 px-3 py-2 text-xs text-amber-200">
      <span aria-hidden="true">◇</span>
      <span>
        <strong className="font-semibold">What-if scenario.</strong> This does
        not change your current plan.
      </span>
    </div>
  )
}
