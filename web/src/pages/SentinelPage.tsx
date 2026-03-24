import { useState, useEffect, useRef } from 'react'
import { SentinelControl } from '../components/manager/SentinelControl'
import { useProjectDetail } from '../hooks/useProjectDetail'
import { getState, getLog, type StateData } from '../lib/api'

interface Props {
  project: string | null
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

function RunSummary({ state }: { state: StateData | null }) {
  if (!state || !state.changes?.length) return null

  const changes = state.changes
  const byStatus: Record<string, number> = {}
  let totalIn = 0, totalOut = 0
  for (const c of changes) {
    byStatus[c.status] = (byStatus[c.status] || 0) + 1
    totalIn += c.input_tokens ?? 0
    totalOut += c.output_tokens ?? 0
  }

  const merged = byStatus['merged'] || 0
  const running = byStatus['running'] || 0
  const pending = byStatus['pending'] || 0
  const failed = (byStatus['failed'] || 0) + (byStatus['merge-blocked'] || 0) + (byStatus['integration-failed'] || 0)
  const done = byStatus['done'] || 0

  return (
    <div className="space-y-3">
      {/* Status badges */}
      <div className="flex flex-wrap gap-2">
        <span className={`text-xs px-2 py-1 rounded font-medium ${
          state.status === 'running' ? 'bg-green-900/50 text-green-300' :
          state.status === 'done' ? 'bg-blue-900/50 text-blue-300' :
          state.status === 'stopped' ? 'bg-amber-900/50 text-amber-300' :
          'bg-neutral-800 text-neutral-400'
        }`}>
          {state.status}
        </span>
        <span className="text-xs text-neutral-400">{changes.length} changes</span>
      </div>

      {/* Progress bar */}
      <div className="space-y-1">
        <div className="flex gap-1 h-2 rounded-full overflow-hidden bg-neutral-800">
          {merged > 0 && <div className="bg-green-500" style={{ width: `${(merged / changes.length) * 100}%` }} />}
          {done > 0 && <div className="bg-blue-500" style={{ width: `${(done / changes.length) * 100}%` }} />}
          {running > 0 && <div className="bg-yellow-500 animate-pulse" style={{ width: `${(running / changes.length) * 100}%` }} />}
          {failed > 0 && <div className="bg-red-500" style={{ width: `${(failed / changes.length) * 100}%` }} />}
        </div>
        <div className="flex gap-4 text-xs text-neutral-500">
          {merged > 0 && <span className="text-green-400">{merged} merged</span>}
          {done > 0 && <span className="text-blue-400">{done} done</span>}
          {running > 0 && <span className="text-yellow-400">{running} running</span>}
          {failed > 0 && <span className="text-red-400">{failed} failed</span>}
          {pending > 0 && <span>{pending} pending</span>}
        </div>
      </div>

      {/* Token usage */}
      {(totalIn > 0 || totalOut > 0) && (
        <div className="text-xs text-neutral-500">
          Tokens: <span className="text-neutral-300">{formatTokens(totalIn)}</span> in / <span className="text-neutral-300">{formatTokens(totalOut)}</span> out
        </div>
      )}

      {/* Change list */}
      <div className="space-y-1">
        {changes.map(c => (
          <div key={c.name} className="flex items-center gap-2 text-xs">
            <span className={`w-2 h-2 rounded-full shrink-0 ${
              c.status === 'merged' ? 'bg-green-400' :
              c.status === 'done' ? 'bg-blue-400' :
              c.status === 'running' ? 'bg-yellow-400 animate-pulse' :
              c.status === 'pending' ? 'bg-neutral-600' :
              'bg-red-400'
            }`} />
            <span className="text-neutral-300 truncate flex-1">{c.name}</span>
            <span className={`shrink-0 ${
              c.status === 'merged' ? 'text-green-500' :
              c.status === 'running' ? 'text-yellow-500' :
              c.status === 'pending' ? 'text-neutral-600' :
              'text-neutral-500'
            }`}>{c.status}</span>
            {(c.input_tokens ?? 0) > 0 && (
              <span className="text-neutral-600 shrink-0">{formatTokens(c.input_tokens!)}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

function LogViewer({ lines }: { lines: string[] }) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [lines.length, autoScroll])

  const handleScroll = () => {
    if (!scrollRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }

  if (lines.length === 0) {
    return <div className="text-xs text-neutral-600 p-3">No log data</div>
  }

  return (
    <div ref={scrollRef} onScroll={handleScroll} className="h-full overflow-y-auto p-3 font-mono text-xs">
      {lines.map((line, i) => (
        <div key={i} className={`py-0.5 ${
          line.includes('ERROR') || line.includes('FAIL') ? 'text-red-400' :
          line.includes('WARNING') || line.includes('WARN') ? 'text-amber-400' :
          line.includes('merged') || line.includes('PASS') || line.includes('SUCCESS') ? 'text-green-400' :
          line.includes('[sentinel]') ? 'text-cyan-400' :
          'text-neutral-400'
        }`}>
          {line}
        </div>
      ))}
    </div>
  )
}

export default function SentinelPage({ project }: Props) {
  const { project: status, specPaths, loading } = useProjectDetail(project || undefined)
  const [state, setState] = useState<StateData | null>(null)
  const [logLines, setLogLines] = useState<string[]>([])
  const [activeTab, setActiveTab] = useState<'overview' | 'log'>('overview')
  const stateJsonRef = useRef('')

  // Poll orchestration state (with backoff on failure)
  useEffect(() => {
    if (!project) return
    let cancelled = false
    let fails = 0
    let timer: ReturnType<typeof setTimeout>
    const poll = () => {
      getState(project).then(d => {
        if (cancelled) return
        fails = 0
        const json = JSON.stringify(d)
        if (json !== stateJsonRef.current) {
          stateJsonRef.current = json
          setState(d)
        }
        timer = setTimeout(poll, 5000)
      }).catch(() => {
        if (cancelled) return
        fails++
        timer = setTimeout(poll, Math.min(5000 * Math.pow(2, fails - 1), 30000))
      })
    }
    poll()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [project])

  // Fetch log (with backoff on failure)
  useEffect(() => {
    if (!project) return
    let cancelled = false
    let fails = 0
    let timer: ReturnType<typeof setTimeout>
    const fetchLog = () => {
      getLog(project).then(d => {
        if (cancelled) return
        fails = 0
        if (d.lines?.length) setLogLines(d.lines)
        timer = setTimeout(fetchLog, 10000)
      }).catch(() => {
        if (cancelled) return
        fails++
        timer = setTimeout(fetchLog, Math.min(10000 * Math.pow(2, fails - 1), 60000))
      })
    }
    fetchLog()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [project])

  if (!project) {
    return <div className="flex items-center justify-center h-full text-neutral-500">Select a project</div>
  }

  if (loading) {
    return <div className="p-6 text-sm text-neutral-500">Loading...</div>
  }

  return (
    <div className="flex flex-col h-full">
      {/* Sentinel control */}
      <div className="p-6 border-b border-neutral-800">
        <SentinelControl
          project={project}
          alive={status?.sentinel.alive ?? false}
          startedAt={status?.sentinel.started_at}
          crashCount={status?.sentinel.crash_count}
          activeSpec={status?.sentinel.spec}
          specPaths={specPaths}
        />
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 px-6 py-2 border-b border-neutral-800 bg-neutral-900 shrink-0">
        {(['overview', 'log'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1 text-sm rounded transition-colors capitalize ${
              activeTab === tab
                ? 'bg-neutral-800 text-neutral-200 font-medium'
                : 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50'
            }`}
          >
            {tab}
          </button>
        ))}
        <span className="text-xs text-neutral-600 ml-auto">{logLines.length} log lines</span>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-hidden">
        {activeTab === 'overview' && (
          <div className="h-full overflow-y-auto p-6">
            <RunSummary state={state} />
          </div>
        )}
        {activeTab === 'log' && (
          <LogViewer lines={logLines} />
        )}
      </div>
    </div>
  )
}
