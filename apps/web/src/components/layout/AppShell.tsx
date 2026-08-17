import { NavLink, Outlet } from 'react-router-dom'
import { ProjectSwitcher } from '@/features/capacity/components/ProjectSwitcher'

const NAV_LINK_CLASS = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400 ${
    isActive
      ? 'bg-slate-800 text-slate-100'
      : 'text-slate-400 hover:text-slate-100'
  }`

export function AppShell() {
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
              <NavLink to="/import-export" className={NAV_LINK_CLASS}>
                Import / Export
              </NavLink>
            </nav>
          </div>
          <div className="w-56">
            <ProjectSwitcher />
          </div>
        </div>
      </header>
      <main id="main-content" className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <Outlet />
      </main>
    </div>
  )
}
