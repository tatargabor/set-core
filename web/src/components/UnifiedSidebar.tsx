import { useCallback, useEffect, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { getApps, getGlobalItems, type SidebarApp, type SidebarSubItem, type GlobalItem } from '../lib/sidebarRegistry'
import { useSidebarStats } from '../hooks/useSidebarStats'
import { restartManager, startManager, type StateData } from '../lib/api'
import LineageList from './LineageList'

function SidebarIcon({ icon, className }: { icon: string | LucideIcon; className?: string }) {
  if (typeof icon === 'string') {
    return <span className={className}>{icon}</span>
  }
  const Icon = icon
  return <Icon size={16} className={className} />
}

interface Props {
  project: string | null
  sidebarOpen: boolean
  onClose: () => void
  sidebarState?: StateData | null
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

/**
 * Is the rail collapsed to icons?
 *
 * Persisted, unlike anything the status surface keeps: this is a preference about the CHROME,
 * carrying no value the project reported, so `localStorage` holds nothing a reader would mind
 * leaving behind. The rule the table obeys — never persist a control whose value IS the
 * producer's data — is about the data, not about storage.
 */
const COLLAPSE_KEY = 'set:sidebar-collapsed'

function useCollapsed(): [boolean, () => void] {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(COLLAPSE_KEY) === '1' } catch { return false }
  })
  const toggle = useCallback(() => {
    setCollapsed(c => {
      try { localStorage.setItem(COLLAPSE_KEY, c ? '0' : '1') } catch { /* private mode */ }
      return !c
    })
  }, [])
  // Ctrl/Cmd+B, the convention every editor this audience already uses has settled on.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'b') {
        e.preventDefault()
        toggle()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggle])
  return [collapsed, toggle]
}

export default function UnifiedSidebar({ project, sidebarOpen, onClose, sidebarState }: Props) {
  const location = useLocation()
  const { issueStats, totalOpen, managerOnline } = useSidebarStats()
  const [restarting, setRestarting] = useState(false)
  const [collapsed, toggleCollapsed] = useCollapsed()

  const apps = getApps()
  const globalItems = getGlobalItems()
  const activeAppId = project ? detectActiveApp(apps, location.pathname, project) : null
  const activeApp = apps.find(a => a.id === activeAppId)

  return (
    <>
      {/* Backdrop (mobile) */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 bg-surface-page/60 md:hidden" onClick={onClose} />
      )}

      <aside className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-surface-page border-r border-surface-line flex flex-col
        transform transition-transform duration-200 ease-in-out
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        md:relative md:translate-x-0 md:transition-[width] md:duration-150 ${collapsed ? 'md:w-14' : 'md:w-56'}
      `}>
        {/* Header — the title collapses to the mark; the toggle stays reachable in both states. */}
        {/* Collapsed, the rail is 56px wide and the toggle cannot sit beside the mark without
            landing on it — measured, it overlapped. So the header stacks instead of overlaying:
            an absolutely-positioned control on a rail this narrow has no space that is not
            already someone's. */}
        <div className={`flex border-b border-surface-line ${collapsed ? 'flex-col items-stretch' : 'items-center'}`}>
          <Link
            to="/"
            title="SET — Ship Exactly This!"
            className={`flex-1 min-w-0 hover:bg-surface-panel transition-colors ${collapsed ? 'py-3 text-center' : 'p-4'}`}
          >
            <h1 className="text-sm font-semibold text-fg-loud tracking-wide">SET</h1>
            {!collapsed && <p className="text-sm text-fg-faint tracking-wide">Ship Exactly This!</p>}
          </Link>
          <button
            onClick={toggleCollapsed}
            title={collapsed ? 'Expand sidebar (Ctrl+B)' : 'Collapse sidebar (Ctrl+B)'}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            className={`hidden md:block shrink-0 text-fg-ghost hover:text-fg-normal hover:bg-surface-panel transition-colors ${
              collapsed ? 'w-full py-1 border-t border-surface-line text-center' : 'px-2 py-4'
            }`}
          >
            {collapsed ? '\u00BB' : '\u00AB'}
          </button>
        </div>

        {/* Project name (when inside a project) */}
        {project && !collapsed && (
          <div className="px-4 py-2 border-b border-surface-line">
            <span className="text-xs text-fg-faint">Project</span>
            <div className="text-sm font-medium text-fg-strong truncate">{project}</div>
          </div>
        )}

        {/* Lineage selector — rendered between the project-name block and the app menu (Section 14.1). */}
        {project && !collapsed && <LineageList project={project} sidebarState={sidebarState ?? null} />}

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
                    // The label is the ONLY thing that names this destination, so when it is
                    // hidden the `title` has to carry it — an icon rail without tooltips is a
                    // memory test. The badge survives collapse as a dot: a count the reader
                    // cannot see is a failure hidden by compacting.
                    title={collapsed ? app.label + (issueBadge ? ` (${issueBadge})` : '') : undefined}
                    className={`relative flex items-center gap-2 py-2 rounded text-sm transition-colors ${
                      collapsed ? 'justify-center px-0' : 'px-3'
                    } ${
                      isActive
                        ? 'bg-surface-raised text-fg-loud'
                        : 'text-fg-muted hover:bg-surface-raised/50 hover:text-fg-normal'
                    }`}
                  >
                    <SidebarIcon icon={app.icon} className="w-5 text-center shrink-0" />
                    {!collapsed && <span className="flex-1">{app.label}</span>}
                    {issueBadge != null && issueBadge > 0 && (
                      collapsed
                        ? <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-status-warn" />
                        : <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-status-warn">
                            {issueBadge}
                          </span>
                    )}
                  </Link>
                )
              })}
            </div>

            {/* Level 2: Sub-items for active app */}
            {activeApp && activeApp.children.length > 1 && !collapsed && (
              <>
                <div className="border-t border-surface-line" />
                <nav className="px-3 py-2 space-y-0.5 flex-1 overflow-y-auto">
                  <div className="px-3 py-1 text-xs text-fg-ghost uppercase tracking-wider font-medium">
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
                collapsed={collapsed}
                onClick={onClose}
              />
            ))}
            {/* A prompt is only a prompt if it is readable. On the collapsed rail
                it had nowhere to go and simply overflowed onto the page. */}
            {!collapsed && (
              <div className="px-4 py-3 text-sm text-fg-ghost">
                Select a project
              </div>
            )}
          </div>
        )}

        {/* Footer: manager health */}
        <div className="border-t border-surface-line px-3 py-2 mt-auto">
          <div className="flex items-center gap-2">
            <Link
              to="/"
              title={collapsed ? `Manager: ${managerOnline ? 'running' : 'offline'}` : undefined}
              className={`flex items-center gap-2 text-sm text-fg-faint hover:text-fg-normal flex-1 ${collapsed ? 'justify-center' : ''}`}
            >
              <span className={`w-2 h-2 rounded-full shrink-0 ${managerOnline ? 'bg-status-active' : 'bg-status-fail'}`} />
              {!collapsed && <span>Manager: {restarting ? 'restarting...' : managerOnline ? 'running' : 'offline'}</span>}
            </Link>
            {managerOnline ? (
              <button
                disabled={restarting}
                onClick={async () => {
                  setRestarting(true)
                  try { await restartManager() } catch {}
                  setTimeout(() => setRestarting(false), 5000)
                }}
                className="px-1.5 py-0.5 text-xs rounded text-fg-ghost hover:text-fg-muted hover:bg-surface-raised disabled:opacity-50"
                title="Restart manager"
              >
                ↻
              </button>
            ) : (
              <button
                disabled={restarting}
                onClick={async () => {
                  setRestarting(true)
                  try { await startManager() } catch {}
                  setTimeout(() => setRestarting(false), 5000)
                }}
                className="px-1.5 py-0.5 text-xs rounded text-blue-600/50 hover:text-blue-400 hover:bg-surface-raised disabled:opacity-50"
                title="Start manager"
              >
                Start
              </button>
            )}
          </div>
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
          ? 'bg-surface-raised/70 text-fg-strong'
          : 'text-fg-faint hover:bg-surface-raised/30 hover:text-fg-muted'
      }`}
    >
      <span className="flex-1">{item.label}</span>
      {item.badge && <item.badge project={project} />}
    </Link>
  )
}

function GlobalLink({ item, active, badge, collapsed, onClick }: {
  item: GlobalItem
  active: boolean
  badge?: number
  collapsed: boolean
  onClick: () => void
}) {
  return (
    <Link
      to={item.route}
      onClick={onClick}
      // Same three moves the app links above already make when the rail collapses,
      // and for the same reasons: the `title` carries the name the hidden label
      // was carrying (an icon rail without tooltips is a memory test), and the
      // badge survives as a dot, because a count the reader cannot see is a
      // failure hidden by compacting.
      title={collapsed ? item.label + (badge ? ` (${badge})` : '') : undefined}
      className={`relative flex items-center gap-2 py-2 rounded text-sm transition-colors ${
        collapsed ? 'justify-center px-0' : 'px-3'
      } ${
        active
          ? 'bg-surface-raised text-fg-loud'
          : 'text-fg-muted hover:bg-surface-raised/50 hover:text-fg-normal'
      }`}
    >
      <SidebarIcon icon={item.icon} className="w-5 text-center shrink-0" />
      {!collapsed && <span className="flex-1">{item.label}</span>}
      {badge != null && badge > 0 && (
        collapsed
          ? <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-amber-400" />
          : <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400">
              {badge}
            </span>
      )}
    </Link>
  )
}
