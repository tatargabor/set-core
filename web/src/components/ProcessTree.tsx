import { useState, useEffect, useRef } from 'react'
import { getProcesses, stopProcess, stopAllProcesses, type ProcessNode } from '../lib/api'

interface Props {
  project: string
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h${m % 60}m`
  return `${Math.floor(h / 24)}d${h % 24}h`
}

function ProcessRow({ node, depth, project, onRefresh }: {
  node: ProcessNode
  depth: number
  project: string
  onRefresh: () => void
}) {
  const [stopping, setStopping] = useState(false)

  const handleStop = async () => {
    setStopping(true)
    try {
      await stopProcess(project, node.pid)
      setTimeout(onRefresh, 1000)
    } finally { setStopping(false) }
  }

  const roleLabel = node.role
    ? node.role.charAt(0).toUpperCase() + node.role.slice(1)
    : null
  const isOrphan = node.role === 'orphan'

  // Truncate command for display
  const cmd = node.command.length > 60 ? node.command.slice(0, 57) + '...' : node.command

  return (
    <>
      <div className="flex items-center gap-2 py-1.5 px-2 hover:bg-surface-raised/30 rounded group" style={{ paddingLeft: `${8 + depth * 20}px` }}>
        {/* Tree connector */}
        {depth > 0 && (
          <span className="text-fg-dim text-xs">└─</span>
        )}
        {/* Status dot — amber for orphan to flag re-parented processes
            that lost their supervisor (set-loop / playwright leftovers). */}
        <span className={`w-2 h-2 rounded-full shrink-0 ${isOrphan ? 'bg-amber-400' : 'bg-green-400'}`} />
        {/* Role badge — red for orphan, blue otherwise */}
        {roleLabel && (
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium shrink-0 ${
            isOrphan
              ? 'bg-red-900/50 text-red-300'
              : 'bg-blue-900/40 text-blue-300'
          }`} title={isOrphan ? 'Process matches the project/worktree path but is not under a tracked supervisor — likely a leftover from a killed sentinel.' : undefined}>
            {roleLabel}
          </span>
        )}
        {/* PID */}
        <span className="text-xs text-fg-faint shrink-0">{node.pid}</span>
        {/* Command */}
        <span className="text-xs text-fg-muted truncate flex-1" title={node.command}>
          {cmd}
        </span>
        {/* Stats */}
        <span className="text-xs text-fg-ghost shrink-0">{formatUptime(node.uptime_seconds)}</span>
        <span className="text-xs text-fg-ghost shrink-0 w-12 text-right">{node.cpu_percent.toFixed(1)}%</span>
        <span className="text-xs text-fg-ghost shrink-0 w-14 text-right">{node.memory_mb}MB</span>
        {/* Stop button */}
        <button
          onClick={handleStop}
          disabled={stopping}
          className="text-xs px-2 py-0.5 rounded bg-red-950/30 text-red-400 hover:bg-red-950/50 opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          {stopping ? '...' : 'Stop'}
        </button>
      </div>
      {node.children.map(child => (
        <ProcessRow key={child.pid} node={child} depth={depth + 1} project={project} onRefresh={onRefresh} />
      ))}
    </>
  )
}

export default function ProcessTree({ project }: Props) {
  const [processes, setProcesses] = useState<ProcessNode[]>([])
  const [loading, setLoading] = useState(true)
  const [stoppingAll, setStoppingAll] = useState(false)
  const [confirmStop, setConfirmStop] = useState(false)
  const jsonRef = useRef('')

  const load = () => {
    getProcesses(project)
      .then(d => {
        const json = JSON.stringify(d.processes)
        if (json !== jsonRef.current) {
          jsonRef.current = json
          setProcesses(d.processes)
        }
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const iv = setInterval(load, 5000)
    return () => clearInterval(iv)
  }, [project])

  const handleStopAll = async () => {
    if (!confirmStop) {
      setConfirmStop(true)
      return
    }
    setStoppingAll(true)
    setConfirmStop(false)
    try {
      await stopAllProcesses(project)
      setTimeout(load, 2000)
    } finally { setStoppingAll(false) }
  }

  // Count total processes
  const countNodes = (nodes: ProcessNode[]): number =>
    nodes.reduce((s, n) => s + 1 + countNodes(n.children), 0)
  const total = countNodes(processes)

  if (loading && processes.length === 0) {
    return <div className="text-xs text-fg-faint py-2">Loading processes...</div>
  }

  if (total === 0) {
    return (
      <div className="text-xs text-fg-ghost py-2">No processes running</div>
    )
  }

  return (
    <div className="space-y-2">
      {/* Header with Stop All */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-fg-faint">{total} process{total !== 1 ? 'es' : ''}</span>
        <button
          onClick={handleStopAll}
          disabled={stoppingAll}
          className={`px-3 py-1 text-xs rounded font-medium disabled:opacity-50 disabled:cursor-not-allowed ${
            confirmStop
              ? 'bg-red-700 text-white hover:bg-red-600'
              : 'bg-red-900/50 text-red-300 hover:bg-red-900'
          }`}
        >
          {stoppingAll ? 'Stopping...' : confirmStop ? 'Confirm Stop All' : 'Stop All'}
        </button>
      </div>

      {/* Process tree */}
      <div className="rounded-lg border border-surface-line bg-surface-panel/30 divide-y divide-surface-line/30">
        {processes.map(node => (
          <ProcessRow key={node.pid} node={node} depth={0} project={project} onRefresh={load} />
        ))}
      </div>
    </div>
  )
}
