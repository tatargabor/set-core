import { Link, useLocation, useNavigate } from 'react-router-dom'
import { getSidebarItems, type SidebarItem } from '../lib/sidebarRegistry'
import { useSidebarStats } from '../hooks/useSidebarStats'
import ProjectSelector from './ProjectSelector'
import type { ProjectInfo } from '../lib/api'

interface Props {
  project: string | null
  projects: ProjectInfo[]
  onProjectChange: (name: string) => void
  sidebarOpen: boolean
  onClose: () => void
}

function resolveRoute(route: string, project: string | null): string {
  if (!project) return route.replace('/:project', '')
  return route.replace(':project', project)
}

function isActiveRoute(item: SidebarItem, pathname: string, project: string | null): boolean {
  const resolved = resolveRoute(item.route, project)

  // Check match patterns first
  if (item.matchPatterns) {
    for (const pattern of item.matchPatterns) {
      const resolvedPattern = resolveRoute(pattern, project)
      if (pathname === resolvedPattern || pathname === resolvedPattern + '/') return true
    }
    // If matchPatterns is empty array, never match (e.g., sentinel tab)
    if (item.matchPatterns.length === 0) return false
  }

  // Exact match on resolved route
  if (pathname === resolved || pathname === resolved + '/') return true

  // Prefix match for nested routes (e.g., /manager/craftbrew/issues/ISS-001)
  if (resolved.length > 1 && pathname.startsWith(resolved + '/')) return true

  return false
}

export default function UnifiedSidebar({ project, projects, onProjectChange, sidebarOpen, onClose }: Props) {
  const location = useLocation()
  const navigate = useNavigate()
  const { issueStats, totalOpen, managerOnline } = useSidebarStats()

  const globalItems = getSidebarItems('global')
  const projectItems = getSidebarItems('project')

  const handleProjectChange = (name: string) => {
    onProjectChange(name)
    // Stay in current "mode" — if on /manager route, go to /manager/:project/issues
    if (location.pathname.startsWith('/manager')) {
      navigate(`/manager/${name}/issues`)
    } else {
      navigate(`/set/${name}`)
    }
  }

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
        <Link to="/set" className="block p-4 border-b border-neutral-800 hover:bg-neutral-900 transition-colors">
          <h1 className="text-sm font-semibold text-neutral-100 tracking-wide">SET</h1>
          <p className="text-sm text-neutral-500 tracking-wide">Ship Exactly This!</p>
        </Link>

        {/* Global / Control Plane */}
        <div className="p-3 space-y-0.5">
          <div className="px-1 py-1 text-xs text-neutral-600 uppercase tracking-wider font-medium">Control Plane</div>
          {globalItems.map(item => (
            <SidebarLink
              key={item.id}
              item={item}
              active={isActiveRoute(item, location.pathname, project)}
              project={project}
              badge={item.id === 'manager-all-issues' && totalOpen > 0 ? totalOpen : undefined}
              onClick={onClose}
            />
          ))}
        </div>

        {/* Divider */}
        <div className="border-t border-neutral-800" />

        {/* Project Selector */}
        <div className="p-3">
          <ProjectSelector
            projects={projects}
            current={project}
            onChange={handleProjectChange}
          />
        </div>

        {/* Per-project items */}
        {project && (
          <nav className="px-3 space-y-0.5 flex-1 overflow-y-auto">
            {projectItems.map(item => {
              // Get per-project issue badge
              let badge: number | undefined
              if (item.id === 'project-issues' && project && issueStats[project]) {
                const open = issueStats[project].total_open
                if (open > 0) badge = open
              }

              return (
                <SidebarLink
                  key={item.id}
                  item={item}
                  active={isActiveRoute(item, location.pathname, project)}
                  project={project}
                  badge={badge}
                  onClick={onClose}
                />
              )
            })}
          </nav>
        )}

        {!project && (
          <div className="px-4 py-3 text-sm text-neutral-600">
            Select a project above
          </div>
        )}

        {/* Footer: manager health */}
        <div className="border-t border-neutral-800 px-3 py-2 mt-auto">
          <Link to="/manager" className="flex items-center gap-2 text-sm text-neutral-500 hover:text-neutral-300">
            <span className={`w-2 h-2 rounded-full ${managerOnline ? 'bg-green-400' : 'bg-red-400'}`} />
            <span>Manager: {managerOnline ? 'running' : 'offline'}</span>
          </Link>
        </div>
      </aside>
    </>
  )
}

function SidebarLink({ item, active, project, badge, onClick }: {
  item: SidebarItem
  active: boolean
  project: string | null
  badge?: number
  onClick: () => void
}) {
  const href = resolveRoute(item.route, project)

  return (
    <Link
      to={href}
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
      {/* Render custom badge component if provided */}
      {!badge && item.badge && <item.badge project={project} />}
    </Link>
  )
}
