import { BrowserRouter, Routes, Route, Navigate, useLocation, useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect, useCallback, useRef } from 'react'
import { TuiStatus } from './components/tui'
import Dashboard from './pages/Dashboard'
import Worktrees from './pages/Worktrees'
import Settings from './pages/Settings'
import Memory from './pages/Memory'
import Home from './pages/Home'
import Manager from './pages/Manager'
import ManagerIssues from './pages/ManagerIssues'
import ManagerMutes from './pages/ManagerMutes'
import UnifiedSidebar from './components/UnifiedSidebar'
import { useProject } from './hooks/useProject'
import type { StateData, ChangeInfo } from './lib/api'
// Import registry to ensure built-in items are registered
import './lib/sidebarRegistry'


function SidebarQuickStatus({ state }: { state: StateData | null }) {
  if (!state) return null
  const changes = state.changes ?? []
  const done = changes.filter(c => ['done', 'merged', 'completed', 'skip_merged'].includes(c.status)).length
  const failed = changes.filter(c => ['failed', 'verify-failed'].includes(c.status)).length
  return (
    <div className="px-3 py-2 space-y-1 text-sm">
      <div className="flex items-center justify-between text-neutral-400">
        <span>{done}/{changes.length} done</span>
        {failed > 0 && <span className="text-red-400">{failed} failed</span>}
      </div>
      {state.plan_version && (
        <div className="text-neutral-600">Plan v{state.plan_version}</div>
      )}
    </div>
  )
}

function SidebarChanges({ changes, onSelect }: {
  changes: ChangeInfo[]
  onSelect?: (name: string) => void
}) {
  if (changes.length === 0) return null
  return (
    <div className="px-2 py-1 space-y-0.5">
      <div className="px-1 py-1 text-sm text-neutral-600 uppercase tracking-wider font-medium">Changes</div>
      {changes.map(c => (
        <button
          key={c.name}
          onClick={() => onSelect?.(c.name)}
          className="w-full flex items-center gap-1.5 px-2 py-1 rounded text-left transition-colors text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-300"
        >
          <TuiStatus status={c.status} label={false} />
          <span className="text-sm truncate">{c.name}</span>
        </button>
      ))}
    </div>
  )
}

/**
 * SharedLayout — unified layout for ALL routes (both /set/* and /manager/*).
 * Uses UnifiedSidebar for cross-navigation. Sidebar stays stable across route changes.
 */
function SharedLayout() {
  const { project: urlProject } = useParams<{ project: string }>()
  const { project: hookProject, setProject, projects } = useProject()
  const location = useLocation()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarState, setSidebarState] = useState<StateData | null>(null)
  const sidebarJsonRef = useRef('')

  // Determine project from URL — works for both /set/:project and /manager/:project
  const project = urlProject || hookProject

  // Extract project from /manager/:project/* routes too
  const managerProjectMatch = location.pathname.match(/^\/manager\/([^/]+)/)
  const effectiveProject = project || (managerProjectMatch ? managerProjectMatch[1] : null)

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  // Fetch orchestration state for quick status (only when on /set routes)
  useEffect(() => {
    if (!effectiveProject) return
    const load = () => {
      fetch(`/api/${effectiveProject}/state`)
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (!d) return
          const json = JSON.stringify(d)
          if (json !== sidebarJsonRef.current) {
            sidebarJsonRef.current = json
            setSidebarState(d)
          }
        })
        .catch(() => {})
    }
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [effectiveProject])

  const handleProjectChange = (name: string) => {
    setProject(name)
  }

  const handleSelectChange = useCallback((name: string) => {
    window.dispatchEvent(new CustomEvent('set-select-change', { detail: name }))
    setSidebarOpen(false)
  }, [])

  // Determine what page we're on
  const path = location.pathname
  const isManagerOverview = path === '/manager'
  const isManagerIssues = path.match(/^\/manager\/[^/]+\/issues/) || path === '/manager/issues'
  const isManagerMutes = path.match(/^\/manager\/[^/]+\/mutes/)
  const isHome = path === '/set'
  const isProjectRoute = path.match(/^\/set\/[^/]+/)

  // Orchestration status for mobile top bar
  const orchStatus = sidebarState?.status ?? 'idle'

  return (
    <div className="flex h-screen bg-neutral-950 text-neutral-200">
      {/* Mobile top bar */}
      <div className="fixed top-0 left-0 right-0 z-30 flex items-center gap-3 px-3 py-2 bg-neutral-950 border-b border-neutral-800 md:hidden">
        <button
          onClick={() => setSidebarOpen(true)}
          className="p-2 -ml-1 rounded text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
          aria-label="Open menu"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M3 5h14M3 10h14M3 15h14" />
          </svg>
        </button>
        <span className="text-sm font-semibold text-neutral-100 truncate">
          {effectiveProject || 'SET'}
        </span>
        {isProjectRoute && <TuiStatus status={orchStatus} label={false} />}
      </div>

      {/* Unified Sidebar */}
      <UnifiedSidebar
        project={effectiveProject}
        projects={projects}
        onProjectChange={handleProjectChange}
        sidebarOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Quick status + changes (only visible on desktop, below sidebar) */}
      {/* This is handled inside UnifiedSidebar now */}

      {/* Main content */}
      <main key={effectiveProject} className="flex-1 overflow-hidden pt-11 md:pt-0">
        {/* Home */}
        {isHome && <Home />}

        {/* Project pages (/set/:project/*) */}
        {isProjectRoute && (
          <Routes>
            <Route index element={<Dashboard project={effectiveProject} />} />
            <Route path="worktrees" element={<Worktrees project={effectiveProject} />} />
            <Route path="memory" element={<Memory project={effectiveProject} />} />
            <Route path="settings" element={<Settings project={effectiveProject} />} />
          </Routes>
        )}

        {/* Manager pages */}
        {isManagerOverview && <Manager />}
        {isManagerIssues && <ManagerIssues />}
        {isManagerMutes && <ManagerMutes />}
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/set" replace />} />
        <Route path="/set" element={<SharedLayout />} />
        <Route path="/set/:project/*" element={<SharedLayout />} />
        <Route path="/manager" element={<SharedLayout />} />
        <Route path="/manager/issues" element={<SharedLayout />} />
        <Route path="/manager/:project/*" element={<SharedLayout />} />
      </Routes>
    </BrowserRouter>
  )
}
