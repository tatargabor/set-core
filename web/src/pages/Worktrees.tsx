import { useState, useEffect, useRef } from 'react'
import { getWorktrees, getWorktreeLog, type WorktreeInfo } from '../lib/api'

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

function shortTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

interface Props {
  project: string | null
}

export default function Worktrees({ project }: Props) {
  const [worktrees, setWorktrees] = useState<WorktreeInfo[]>([])
  const [selected, setSelected] = useState<string | null>(null)

  useEffect(() => {
    if (!project) return
    const load = () => getWorktrees(project).then(setWorktrees).catch(() => setWorktrees([]))
    load()
    const interval = setInterval(load, 10000)
    return () => clearInterval(interval)
  }, [project])

  if (!project) {
    return (
      <div className="flex items-center justify-center h-full text-neutral-500">
        Select a project
      </div>
    )
  }

  const selectedWt = worktrees.find((wt) => wt.branch === selected)

  return (
    <div className="flex h-full">
      {/* Worktree list */}
      <div className="w-80 shrink-0 border-r border-neutral-800 overflow-auto">
        <div className="p-3 border-b border-neutral-800">
          <h2 className="text-sm font-semibold text-neutral-100">Worktrees ({worktrees.length})</h2>
        </div>
        {worktrees.length === 0 ? (
          <p className="p-3 text-neutral-500 text-sm">No worktrees found</p>
        ) : (
          <div className="divide-y divide-neutral-800/50">
            {worktrees.map((wt) => (
              <button
                key={wt.path}
                onClick={() => setSelected(wt.branch === selected ? null : wt.branch)}
                className={`w-full text-left p-3 hover:bg-neutral-900 transition-colors ${
                  wt.branch === selected ? 'bg-neutral-900 border-l-2 border-blue-500' : ''
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm text-neutral-200 truncate">{wt.branch}</span>
                  <span className="text-sm text-neutral-600">{wt.head?.slice(0, 7)}</span>
                </div>
                <div className="flex gap-3 text-sm text-neutral-500">
                  {wt.iteration !== undefined && (
                    <span>iter {wt.iteration}{wt.max_iterations ? `/${wt.max_iterations}` : ''}</span>
                  )}
                  {wt.logs && wt.logs.length > 0 && (
                    <span>{wt.logs.length} logs</span>
                  )}
                  {wt.activity?.updated_at && (
                    <span className="ml-auto text-neutral-600" title={new Date(wt.activity.updated_at).toLocaleString()}>
                      {timeAgo(wt.activity.updated_at)}
                    </span>
                  )}
                </div>
                {wt.activity?.broadcast && (
                  <p className="mt-1 text-sm text-neutral-400 truncate">{wt.activity.broadcast}</p>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Log viewer panel */}
      <div className="flex-1 flex flex-col min-w-0">
        {selectedWt ? (
          <WorktreeDetail project={project} worktree={selectedWt} />
        ) : (
          <div className="flex items-center justify-center h-full text-neutral-600 text-sm">
            Select a worktree to view agent logs
          </div>
        )}
      </div>
    </div>
  )
}

function WorktreeDetail({ project, worktree }: { project: string; worktree: WorktreeInfo }) {
  const [activeLog, setActiveLog] = useState<string | null>(null)
  const [logLines, setLogLines] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const logRef = useRef<HTMLDivElement>(null)

  // Auto-select latest log
  useEffect(() => {
    if (worktree.logs && worktree.logs.length > 0) {
      setActiveLog(worktree.logs[worktree.logs.length - 1])
    } else {
      setActiveLog(null)
      setLogLines([])
    }
  }, [worktree.branch, worktree.logs?.length])

  // Load log content
  useEffect(() => {
    if (!activeLog) return
    setLoading(true)
    getWorktreeLog(project, worktree.branch, activeLog)
      .then((data) => {
        setLogLines(data.lines)
        // Scroll to bottom
        setTimeout(() => {
          if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
        }, 50)
      })
      .catch(() => setLogLines(['(Failed to load log)']))
      .finally(() => setLoading(false))
  }, [project, worktree.branch, activeLog])

  // Auto-refresh active log for running worktrees
  useEffect(() => {
    if (!activeLog || !worktree.iteration) return
    const interval = setInterval(() => {
      getWorktreeLog(project, worktree.branch, activeLog)
        .then((data) => setLogLines(data.lines))
        .catch(() => {})
    }, 5000)
    return () => clearInterval(interval)
  }, [project, worktree.branch, activeLog, worktree.iteration])

  return (
    <>
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-neutral-800 bg-neutral-900/50">
        <span className="text-sm text-neutral-200">{worktree.branch}</span>
        {worktree.iteration !== undefined && (
          <span className="text-sm text-neutral-500">
            Iteration {worktree.iteration}{worktree.max_iterations ? ` / ${worktree.max_iterations}` : ''}
          </span>
        )}
        {worktree.activity?.updated_at && (
          <span className="text-sm text-neutral-600" title={new Date(worktree.activity.updated_at).toLocaleString()}>
            {shortTime(worktree.activity.updated_at)}
          </span>
        )}
        <span className="text-sm text-neutral-600 truncate ml-auto">{worktree.path}</span>
      </div>

      {/* Activity bar */}
      {worktree.activity && (
        <div className="px-4 py-1.5 border-b border-neutral-800 text-sm text-neutral-400 bg-neutral-900/30">
          {worktree.activity.broadcast && <span>{worktree.activity.broadcast}</span>}
          {worktree.activity.skill && (
            <span className="ml-3 text-neutral-500">
              Skill: {worktree.activity.skill} {worktree.activity.skill_args ?? ''}
            </span>
          )}
        </div>
      )}

      {/* Log tabs */}
      {worktree.logs && worktree.logs.length > 0 && (
        <div className="flex gap-0.5 px-2 pt-2 border-b border-neutral-800 overflow-x-auto">
          {worktree.logs.map((name) => {
            const label = name.replace('ralph-iter-', '').replace('.log', '').replace('-chain', 'c')
            return (
              <button
                key={name}
                onClick={() => setActiveLog(name)}
                className={`px-2 py-1 text-sm rounded-t transition-colors ${
                  name === activeLog
                    ? 'bg-neutral-800 text-neutral-200'
                    : 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-900'
                }`}
              >
                {label}
              </button>
            )
          })}
        </div>
      )}

      {/* Log content */}
      <div ref={logRef} className="flex-1 overflow-auto p-3 text-sm leading-5">
        {loading && <p className="text-neutral-600">Loading...</p>}
        {!loading && logLines.length === 0 && (
          <p className="text-neutral-600">No logs available</p>
        )}
        {logLines.map((line, i) => (
          <div key={i} className={logLineColor(line)}>
            {line}
          </div>
        ))}
      </div>
    </>
  )
}

function logLineColor(line: string): string {
  if (line.includes('ERROR') || line.includes('error')) return 'text-red-400'
  if (line.includes('WARN') || line.includes('warning')) return 'text-yellow-400'
  if (line.includes('✓') || line.includes('PASS') || line.includes('pass')) return 'text-green-400'
  if (line.includes('FAIL') || line.includes('fail')) return 'text-red-400'
  if (line.includes('>>>') || line.includes('---')) return 'text-cyan-400'
  return 'text-neutral-400'
}
