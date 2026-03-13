import { BrowserRouter, Routes, Route, Navigate, useLocation, Link } from 'react-router-dom'
import { useState, useEffect, useCallback } from 'react'
import Dashboard from './pages/Dashboard'
import Worktrees from './pages/Worktrees'
import Settings from './pages/Settings'
import Home from './pages/Home'
import ProjectSelector from './components/ProjectSelector'
import { useProject } from './hooks/useProject'
import type { StateData, ChangeInfo } from './lib/api'
import { estimateCost, formatCost } from './lib/pricing'

const statusDot: Record<string, string> = {
  running: 'bg-green-500',
  implementing: 'bg-green-500',
  verifying: 'bg-cyan-500',
  done: 'bg-blue-500',
  merged: 'bg-blue-500',
  completed: 'bg-blue-500',
  failed: 'bg-red-500',
  'verify-failed': 'bg-red-500',
  pending: 'bg-neutral-600',
  stalled: 'bg-yellow-500',
  skip_merged: 'bg-neutral-600',
  skipped: 'bg-neutral-600',
}

function formatDuration(secs?: number): string {
  if (!secs) return ''
  const m = Math.floor(secs / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  return `${h}h${m % 60}m`
}

function SidebarQuickStatus({ state }: { state: StateData | null }) {
  if (!state) return null
  const changes = state.changes ?? []
  const done = changes.filter(c => ['done', 'merged', 'completed', 'skip_merged'].includes(c.status)).length
  const failed = changes.filter(c => ['failed', 'verify-failed'].includes(c.status)).length
  const totals = changes.reduce(
    (acc, c) => ({
      input: acc.input + (c.input_tokens ?? 0),
      output: acc.output + (c.output_tokens ?? 0),
      cacheRead: acc.cacheRead + (c.cache_read_tokens ?? 0),
      cacheCreate: acc.cacheCreate + (c.cache_create_tokens ?? 0),
    }),
    { input: 0, output: 0, cacheRead: 0, cacheCreate: 0 },
  )
  const cost = estimateCost({
    input_tokens: totals.input,
    output_tokens: totals.output,
    cache_read_tokens: totals.cacheRead,
    cache_create_tokens: totals.cacheCreate,
  })

  return (
    <div className="px-3 py-2 space-y-1 text-[10px]">
      <div className="flex items-center justify-between text-neutral-400">
        <span>{done}/{changes.length} done</span>
        {failed > 0 && <span className="text-red-400">{failed} failed</span>}
      </div>
      <div className="flex items-center justify-between text-neutral-500">
        <span>{formatDuration(state.active_seconds)}</span>
        <span className="text-neutral-300 font-medium">{formatCost(cost)}</span>
      </div>
      {state.plan_version && (
        <div className="text-neutral-600">Plan v{state.plan_version}</div>
      )}
    </div>
  )
}

function SidebarChanges({ changes, selected, onSelect }: {
  changes: ChangeInfo[]
  selected?: string | null
  onSelect?: (name: string) => void
}) {
  if (changes.length === 0) return null

  return (
    <div className="px-2 py-1 space-y-0.5">
      <div className="px-1 py-1 text-[9px] text-neutral-600 uppercase tracking-wider font-medium">Changes</div>
      {changes.map(c => {
        const dot = statusDot[c.status] ?? 'bg-neutral-700'
        const isActive = selected === c.name
        return (
          <button
            key={c.name}
            onClick={() => onSelect?.(c.name)}
            className={`w-full flex items-center gap-1.5 px-2 py-1 rounded text-left transition-colors ${
              isActive ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-300'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dot}`} />
            <span className="text-[11px] font-mono truncate">{c.name}</span>
          </button>
        )
      })}
    </div>
  )
}

function ProjectLayout() {
  const { project, setProject, projects } = useProject()
  const location = useLocation()
  const [sidebarState, setSidebarState] = useState<StateData | null>(null)

  const pathAfterProject = location.pathname.split('/').slice(3).join('/')
  const activeTab = pathAfterProject || 'dashboard'

  // Fetch state for sidebar (lightweight poll)
  useEffect(() => {
    if (!project) return
    const load = () => {
      fetch(`/api/${project}/state`)
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d) setSidebarState(d) })
        .catch(() => {})
    }
    load()
    const interval = setInterval(load, 5000)
    return () => clearInterval(interval)
  }, [project])

  // Navigate to change on dashboard when clicking sidebar changes
  const navigate = useCallback((name: string) => {
    // Will be picked up by Dashboard via URL or state
    window.dispatchEvent(new CustomEvent('wt-select-change', { detail: name }))
  }, [])

  return (
    <div className="flex h-screen bg-neutral-950 text-neutral-200">
      <aside className="w-56 shrink-0 border-r border-neutral-800 flex flex-col">
        <Link to="/wt" className="block p-4 border-b border-neutral-800 hover:bg-neutral-900 transition-colors">
          <h1 className="text-sm font-semibold text-neutral-100 tracking-wide">wt-tools</h1>
        </Link>
        <div className="p-3">
          <ProjectSelector
            projects={projects}
            current={project}
            onChange={setProject}
          />
        </div>
        <nav className="p-3 space-y-1">
          <Link
            to={project ? `/wt/${project}` : '/wt'}
            className={`block px-3 py-2 rounded text-sm ${activeTab === 'dashboard' ? 'bg-neutral-800 text-neutral-100' : 'hover:bg-neutral-800 text-neutral-300'}`}
          >
            Dashboard
          </Link>
          <Link
            to={project ? `/wt/${project}/worktrees` : '/wt'}
            className={`block px-3 py-2 rounded text-sm ${activeTab === 'worktrees' ? 'bg-neutral-800 text-neutral-100' : 'hover:bg-neutral-800 text-neutral-300'}`}
          >
            Worktrees
          </Link>
          <Link
            to={project ? `/wt/${project}/settings` : '/wt'}
            className={`block px-3 py-2 rounded text-sm ${activeTab === 'settings' ? 'bg-neutral-800 text-neutral-100' : 'hover:bg-neutral-800 text-neutral-300'}`}
          >
            Settings
          </Link>
        </nav>

        {/* Quick status */}
        <div className="border-t border-neutral-800">
          <SidebarQuickStatus state={sidebarState} />
        </div>

        {/* Changes mini-list */}
        <div className="flex-1 overflow-y-auto border-t border-neutral-800">
          <SidebarChanges changes={sidebarState?.changes ?? []} onSelect={navigate} />
        </div>

        {/* Footer */}
        <div className="border-t border-neutral-800 px-3 py-2">
          <div className="text-[9px] text-neutral-600 font-mono truncate">{project}</div>
          <div className="text-[9px] text-neutral-700">:8765</div>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">
        <Routes>
          <Route index element={<Dashboard project={project} />} />
          <Route path="worktrees" element={<Worktrees project={project} />} />
          <Route path="settings" element={<Settings project={project} />} />
        </Routes>
      </main>
    </div>
  )
}

function HomeLayout() {
  return (
    <div className="flex h-screen bg-neutral-950 text-neutral-200">
      <aside className="w-56 shrink-0 border-r border-neutral-800 flex flex-col">
        <div className="p-4 border-b border-neutral-800">
          <h1 className="text-sm font-semibold text-neutral-100 tracking-wide">wt-tools</h1>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <Home />
      </main>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/wt" replace />} />
        <Route path="/wt" element={<HomeLayout />} />
        <Route path="/wt/:project/*" element={<ProjectLayout />} />
      </Routes>
    </BrowserRouter>
  )
}
