import { NavLink, Outlet } from 'react-router-dom'
import { ProjectSwitcher } from '@/features/capacity/components/ProjectSwitcher'
import { useAuth } from '@/features/auth/context/AuthContext'
import { OrganizationSwitcher } from '@/features/auth/components/OrganizationSwitcher'
import { UserMenu } from '@/features/auth/components/UserMenu'

const NAV_LINK_CLASS = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 ${
    isActive
      ? 'bg-slate-800 text-slate-100'
      : 'text-slate-400 hover:text-slate-100'
  }`

export function AppShell() {
  const { can } = useAuth()

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-indigo-500 focus:px-3 focus:py-2 focus:text-white"
      >
        Skip to content
      </a>
      <header className="border-b border-slate-800">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <span className="text-sm font-semibold tracking-tight text-slate-100">
              CapacityOS
            </span>
            <nav aria-label="Primary" className="flex items-center gap-1">
              <NavLink to="/capacity" className={NAV_LINK_CLASS} end>
                Capacity
              </NavLink>
              <NavLink to="/scenarios" className={NAV_LINK_CLASS}>
                Scenarios
              </NavLink>
              <NavLink to="/insights" className={NAV_LINK_CLASS}>
                Insights
              </NavLink>
              <NavLink to="/skills" className={NAV_LINK_CLASS}>
                Skills
              </NavLink>
              <NavLink to="/risks" className={NAV_LINK_CLASS}>
                Risks
              </NavLink>
              <NavLink to="/stakeholders" className={NAV_LINK_CLASS}>
                Stakeholders
              </NavLink>
              <NavLink to="/prioritization" className={NAV_LINK_CLASS}>
                Prioritization
              </NavLink>
              {/* Hidden entirely, not disabled, for a role that can never
               * export (CLAUDE.md §13's "view-only access" principle) —
               * the backend independently enforces this regardless. */}
              {can('export.use') ? (
                <NavLink to="/import-export" className={NAV_LINK_CLASS}>
                  Import / Export
                </NavLink>
              ) : null}
              {can('access.manage') ? (
                <NavLink to="/admin/access" className={NAV_LINK_CLASS}>
                  Access
                </NavLink>
              ) : null}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <div className="w-48">
              <OrganizationSwitcher />
            </div>
            <div className="w-56">
              <ProjectSwitcher />
            </div>
            <UserMenu />
          </div>
        </div>
      </header>
      <main id="main-content" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
