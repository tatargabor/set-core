import { Link, useLocation } from 'react-router-dom'
import { getApps, getGlobalItems, type SidebarApp, type SidebarSubItem, type GlobalItem } from '../lib/sidebarRegistry'
import { useSidebarStats } from '../hooks/useSidebarStats'

interface Props {
  project: string | null
  sidebarOpen: boolean
  onClose: () => void
}

function resolve(route: string, project: string | null): string {
  if (!project) return route.replace('/:name', '')
  return route.replace(':name', project)
}

function isRouteActive(route: string, matchPatterns: string[] | undefined, pathname: string, project: string | null): boolean {
  // Check match patterns first
  if (matchPatterns && matchPatterns.length > 0) {
    for (const pattern of matchPatterns) {
      const resolved = resolve(pattern, project)
      if (pathname === resolved || pathname.startsWith(resolved + '/')) return true
    }
  }
  // Exact or prefix match on route
  const resolved = resolve(route, project)
  if (pathname === resolved || pathname === resolved + '/') return true
  if (resolved.length > 1 && pathname.startsWith(resolved + '/')) return true
  return false
}

function detectActiveApp(apps: SidebarApp[], pathname: string, project: string | null): string | null {
  for (const app of apps) {
    if (isRouteActive(app.defaultRoute, app.matchPatterns, pathname, project)) return app.id
    for (const child of app.children) {
      if (isRouteActive(child.route, child.matchPatterns, pathname, project)) return app.id
    }
  }
  return apps[0]?.id ?? null
}

export default function UnifiedSidebar({ project, sidebarOpen, onClose }: Props) {
  const location = useLocation()
  const { issueStats, totalOpen, managerOnline } = useSidebarStats()

  const apps = getApps()
  const globalItems = getGlobalItems()
  const activeAppId = project ? detectActiveApp(apps, location.pathname, project) : null
  const activeApp = apps.find(a => a.id === activeAppId)

  return (
    <>
      {/* Backdrop (mobile) */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-black/60 md:hidden" onClick={onClose} />
      )}

      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-neutral-950 border-r border-neutral-800 flex flex-col
        transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        md:relative md:translate-x-0 md:w-56 md:transition-none
      `}>
        {/* Header */}
        <Link to="/" className="block p-4 border-b border-neutral-800 hover:bg-neutral-900 transition-colors">
          <h1 className="text-sm font-semibold text-neutral-100 tracking-wide">SET</h1>
          <p className="text-sm text-neutral-500 tracking-wide">Ship Exactly This!</p>
        </Link>

        {/* Project name (when inside a project) */}
        {project && (
          <div className="px-4 py-2 border-b border-neutral-800">
            <span className="text-xs text-neutral-500">Project</span>
            <div className="text-sm font-medium text-neutral-200 truncate">{project}</div>
          </div>
        )}

        {project ? (
          <>
            {/* Level 1: App selector */}
            <div className="p-3 space-y-0.5">
              {apps.map(app => {
                const isActive = app.id === activeAppId
                const issueBadge = app.id === 'issues' && project && issueStats[project]?.total_open > 0
                  ? issueStats[project].total_open
                  : undefined
                return (
                  <Link
                    key={app.id}
                    to={resolve(app.defaultRoute, project)}
                    onClick={onClose}
                    className={`flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
                      isActive
                        ? 'bg-neutral-800 text-neutral-100'
                        : 'text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-300'
                    }`}
                  >
                    <span className="w-5 text-center text-xs">{app.icon}</span>
                    <span className="flex-1">{app.label}</span>
                    {issueBadge != null && issueBadge > 0 && (
                      <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400">
                        {issueBadge}
                      </span>
                    )}
                  </Link>
                )
              })}
            </div>

            {/* Level 2: Sub-items for active app */}
            {activeApp && activeApp.children.length > 1 && (
              <>
                <div className="border-t border-neutral-800" />
                <nav className="px-3 py-2 space-y-0.5 flex-1 overflow-y-auto">
                  <div className="px-3 py-1 text-xs text-neutral-600 uppercase tracking-wider font-medium">
                    {activeApp.label}
                  </div>
                  {activeApp.children.map(child => (
                    <SubItemLink
                      key={child.id}
                      item={child}
                      active={isRouteActive(child.route, child.matchPatterns, location.pathname, project)}
                      project={project}
                      onClick={onClose}
                    />
                  ))}
                </nav>
              </>
            )}
          </>
        ) : (
          /* Global items (no project selected) */
          <div className="p-3 space-y-0.5">
            {globalItems.map(item => (
              <GlobalLink
                key={item.id}
                item={item}
                active={location.pathname === item.route || location.pathname === item.route + '/'}
                badge={item.id === 'global-all-issues' && totalOpen > 0 ? totalOpen : undefined}
                onClick={onClose}
              />
            ))}
            <div className="px-4 py-3 text-sm text-neutral-600">
              Select a project above
            </div>
          </div>
        )}

        {/* Footer: manager health */}
        <div className="border-t border-neutral-800 px-3 py-2 mt-auto">
          <Link to="/" className="flex items-center gap-2 text-sm text-neutral-500 hover:text-neutral-300">
            <span className={`w-2 h-2 rounded-full ${managerOnline ? 'bg-green-400' : 'bg-red-400'}`} />
            <span>Manager: {managerOnline ? 'running' : 'offline'}</span>
          </Link>
        </div>
      </aside>
    </>
  )
}

function SubItemLink({ item, active, project, onClick }: {
  item: SidebarSubItem
  active: boolean
  project: string | null
  onClick: () => void
}) {
  return (
    <Link
      to={resolve(item.route, project)}
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-1.5 rounded text-sm transition-colors ${
        active
          ? 'bg-neutral-800/70 text-neutral-200'
          : 'text-neutral-500 hover:bg-neutral-800/30 hover:text-neutral-400'
      }`}
    >
      <span className="flex-1">{item.label}</span>
      {item.badge && <item.badge project={project} />}
    </Link>
  )
}

function GlobalLink({ item, active, badge, onClick }: {
  item: GlobalItem
  active: boolean
  badge?: number
  onClick: () => void
}) {
  return (
    <Link
      to={item.route}
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
        active
          ? 'bg-neutral-800 text-neutral-100'
          : 'text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-300'
      }`}
    >
      <span className="w-5 text-center text-xs">{item.icon}</span>
      <span className="flex-1">{item.label}</span>
      {badge != null && badge > 0 && (
        <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400">
          {badge}
        </span>
      )}
    </Link>
  )
}
