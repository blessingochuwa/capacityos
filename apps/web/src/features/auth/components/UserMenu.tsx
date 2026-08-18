import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { useAuth } from '../context/AuthContext'

const ROLE_LABEL: Record<string, string> = {
  owner: 'Owner',
  admin: 'Admin',
  manager: 'Manager',
  member: 'Member',
  viewer: 'Viewer',
}

/** Current-user identity + logout — the one place in the app shell that
 * shows "who am I, and what can I do here" (CLAUDE.md §13). Renders
 * nothing if there's no session (e.g. briefly during the loading state,
 * or if used outside AuthProvider) rather than showing a broken menu. */
export function UserMenu() {
  const { user, logout } = useAuth()

  if (!user) {
    return null
  }

  return (
    <div className="flex items-center gap-3">
      <div className="flex flex-col items-end">
        <span className="text-sm font-medium text-slate-100">
          {user.display_name}
        </span>
        <Badge variant="neutral">{ROLE_LABEL[user.role] ?? user.role}</Badge>
      </div>
      <Button variant="ghost" onClick={() => void logout()}>
        Sign out
      </Button>
    </div>
  )
}
