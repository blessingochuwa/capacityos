/** "View-only access" is preferable to a destructive-looking control that
 * later fails at the API (CLAUDE.md §13) — used wherever a write
 * affordance is hidden because the current role lacks the permission,
 * instead of just omitting the control silently. */
export function ViewOnlyNotice({
  message = "Your role doesn't include permission to make changes here.",
}: {
  message?: string
}) {
  return (
    <p className="rounded-md bg-slate-800/60 px-3 py-2 text-xs text-slate-400">
      {message}
    </p>
  )
}
