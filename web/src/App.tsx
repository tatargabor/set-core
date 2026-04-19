import { BrowserRouter, Routes, Route, Navigate, useLocation, useParams, Outlet } from 'react-router-dom'
import { useState, useEffect, useRef } from 'react'
import { TuiStatus } from './components/tui'
import Dashboard from './pages/Dashboard'
import Worktrees from './pages/Worktrees'
import Settings from './pages/Settings'
import Memory from './pages/Memory'
import Manager from './pages/Manager'
import ManagerIssues from './pages/ManagerIssues'
import ManagerMutes from './pages/ManagerMutes'
// SentinelPage removed — controls now in StatusHeader, /sentinel redirects to /orch
import UnifiedSidebar from './components/UnifiedSidebar'
import { SelectedLineageProvider } from './lib/lineage'
import type { StateData } from './lib/api'
// Import registry to ensure built-in apps are registered
import './lib/sidebarRegistry'

/**
 * ProjectLayout — layout wrapper for /p/:name/* routes.
 * Extracts project name from URL and passes it as prop to children.
 */
function ProjectLayout() {
  const { name } = useParams<{ name: string }>()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [_sidebarState, setSidebarState] = useState<StateData | null>(null)
  const sidebarJsonRef = useRef('')

  const project = name || null

  // Close sidebar on route change (mobile)
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  // Fetch orchestration state for quick status
  useEffect(() => {
    if (!project) return
    const load = () => {
      fetch(`/api/${project}/state`)
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
  }, [project])

  const orchStatus = _sidebarState?.status ?? 'idle'

  return (
    <SelectedLineageProvider project={project}>
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
            {project || 'SET'}
          </span>
          <TuiStatus status={orchStatus} label={false} />
        </div>

        <UnifiedSidebar
          project={project}
          sidebarOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          sidebarState={_sidebarState}
        />

        <main key={project} className="flex-1 overflow-hidden pt-11 md:pt-0">
          <Outlet />
        </main>
      </div>
    </SelectedLineageProvider>
  )
}

/**
 * GlobalLayout — layout for non-project routes (/, /issues).
 */
function GlobalLayout() {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  return (
    <div className="flex h-screen bg-neutral-950 text-neutral-200">
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
        <span className="text-sm font-semibold text-neutral-100 truncate">SET</span>
      </div>

      <UnifiedSidebar
        project={null}
        sidebarOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <main className="flex-1 overflow-hidden pt-11 md:pt-0">
        <Outlet />
      </main>
    </div>
  )
}

/**
 * Route-driven Dashboard wrappers — pass forced tab to Dashboard.
 * Dashboard reads `initialTab` prop to set the active tab from the route.
 */
function OrchPage({ tab }: { tab?: string }) {
  const { name } = useParams<{ name: string }>()
  return <Dashboard project={name || null} initialTab={tab} />
}

function IssuesPage() {
  const { name } = useParams<{ name: string }>()
  return <ManagerIssues project={name || null} />
}

function MemoryPage() {
  const { name } = useParams<{ name: string }>()
  return <Memory project={name || null} />
}

function SettingsPage() {
  const { name } = useParams<{ name: string }>()
  return <Settings project={name || null} />
}

function MutesPage() {
  const { name } = useParams<{ name: string }>()
  return <ManagerMutes project={name || null} />
}

function WorktreesPage() {
  const { name } = useParams<{ name: string }>()
  return <Worktrees project={name || null} />
}

function SentinelChatPage() {
  const { name } = useParams<{ name: string }>()
  // Reuse Dashboard's agent chat tab
  return <Dashboard project={name || null} initialTab="agent" />
}

/**
 * Legacy redirect helpers
 */
function LegacySetRedirect() {
  const { project, '*': rest } = useParams()
  const tabMap: Record<string, string> = {
    'worktrees': 'orch/worktrees',
    'memory': 'memory',
    'settings': 'settings',
  }
  const mapped = rest && tabMap[rest] ? tabMap[rest] : 'orch'
  return <Navigate to={`/p/${project}/${mapped}`} replace />
}

function LegacyManagerRedirect() {
  const { project, '*': rest } = useParams()
  if (!project) return <Navigate to="/" replace />
  const pathMap: Record<string, string> = {
    'issues': 'issues',
    'mutes': 'settings/mutes',
  }
  const mapped = rest && pathMap[rest] ? pathMap[rest] : 'orch'
  return <Navigate to={`/p/${project}/${mapped}`} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Global routes */}
        <Route element={<GlobalLayout />}>
          <Route index element={<Manager />} />
          <Route path="issues" element={<ManagerIssues />} />
        </Route>

        {/* Project routes — /p/:name/* */}
        <Route path="/p/:name" element={<ProjectLayout />}>
          {/* Orchestration */}
          <Route path="orch" element={<OrchPage />} />
          <Route path="orch/sessions" element={<OrchPage tab="sessions" />} />
          <Route path="orch/worktrees" element={<WorktreesPage />} />
          <Route path="orch/log" element={<OrchPage tab="log" />} />
          <Route path="orch/tokens" element={<OrchPage tab="tokens" />} />
          <Route path="orch/learnings" element={<OrchPage tab="learnings" />} />
          <Route path="orch/battle" element={<OrchPage tab="battle" />} />
          {/* Sentinel — redirects to orch (controls now in StatusHeader) */}
          <Route path="sentinel" element={<Navigate to="../orch" replace />} />
          <Route path="sentinel/chat" element={<SentinelChatPage />} />
          {/* Issues */}
          <Route path="issues" element={<IssuesPage />} />
          {/* Memory */}
          <Route path="memory" element={<MemoryPage />} />
          {/* Settings */}
          <Route path="settings" element={<SettingsPage />} />
          <Route path="settings/mutes" element={<MutesPage />} />
          {/* Default: redirect to orch */}
          <Route index element={<Navigate to="orch" replace />} />
        </Route>

        {/* Legacy redirects */}
        <Route path="/set" element={<Navigate to="/" replace />} />
        <Route path="/set/:project/*" element={<LegacySetRedirect />} />
        <Route path="/manager" element={<Navigate to="/" replace />} />
        <Route path="/manager/issues" element={<Navigate to="/issues" replace />} />
        <Route path="/manager/:project/*" element={<LegacyManagerRedirect />} />

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
