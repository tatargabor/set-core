import { useState, useEffect, useRef } from 'react'
import { getProjectSessions, getProjectSession, type SessionInfo } from '../lib/api'

interface Props {
  project: string
  change?: string | null
}

function colorLine(line: string): string {
  if (line.startsWith('>>>')) return 'text-neutral-200'
  if (line.startsWith('  [Edit]') || line.startsWith('  [Write]')) return 'text-yellow-400'
  if (line.startsWith('  [Bash]')) return 'text-green-400'
  if (line.startsWith('  [Read]') || line.startsWith('  [Glob]') || line.startsWith('  [Grep]')) return 'text-blue-400'
  if (line.startsWith('  [')) return 'text-cyan-400'
  if (line.startsWith('---')) return 'text-neutral-600'
  return 'text-neutral-400'
}

export default function SessionPanel({ project, change }: Props) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [lines, setLines] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [listOpen, setListOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Track selected in ref so the poll closure always sees current value
  const selectedRef = useRef(selected)
  selectedRef.current = selected

  // Reset state when change switches
  useEffect(() => {
    setSelected(null)
    setSessions([])
    setLines([])
    setError(null)
  }, [change])

  // Load session list
  useEffect(() => {
    let cancelled = false
    const load = () => {
      getProjectSessions(project, change)
        .then(d => {
          if (cancelled) return
          setSessions(d.sessions)
          // Auto-select most recent only if nothing is selected yet
          if (!selectedRef.current && d.sessions.length > 0) {
            setSelected(d.sessions[0].id)
          }
        })
        .catch(e => { if (!cancelled) setError(String(e)) })
    }
    load()
    const iv = setInterval(load, 15000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project, change])

  // Load selected session content
  useEffect(() => {
    if (!selected) return
    let cancelled = false
    setLoading(true)
    const load = () => {
      getProjectSession(project, selected, 500, change)
        .then(d => {
          if (cancelled) return
          setLines(d.lines)
          setLoading(false)
        })
        .catch(e => {
          if (cancelled) return
          setError(String(e))
          setLoading(false)
        })
    }
    load()
    // Auto-refresh for the most recent session
    const isLatest = sessions.length > 0 && sessions[0].id === selected
    const iv = isLatest ? setInterval(load, 5000) : undefined
    return () => { cancelled = true; if (iv) clearInterval(iv) }
  }, [project, selected, sessions])

  // Auto-scroll on new lines for latest session
  useEffect(() => {
    const isLatest = sessions.length > 0 && sessions[0].id === selected
    if (isLatest && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [lines, selected, sessions])

  const selectedLabel = sessions.find(s => s.id === selected)?.label || selected?.slice(0, 8) || '—'

  if (error) return <div className="p-4 text-xs text-red-400">{error}</div>
  if (sessions.length === 0) return <div className="p-4 text-xs text-neutral-500">No sessions found{change ? ` for ${change}` : ''}</div>

  return (
    <div className="flex flex-col md:flex-row h-full">
      {/* Change context banner */}
      {change && (
        <div className="px-3 py-1.5 bg-blue-950/30 border-b border-blue-900/30 text-[11px] text-blue-300 shrink-0 md:hidden">
          Sessions for <span className="font-mono font-medium">{change}</span>
        </div>
      )}
      {/* Mobile: dropdown session picker */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-neutral-800 md:hidden shrink-0">
        <button
          onClick={() => setListOpen(!listOpen)}
          className="flex items-center gap-2 px-2 py-1 bg-neutral-800 rounded text-[11px] text-neutral-300"
        >
          <span className="truncate max-w-[200px]">{selectedLabel}</span>
          <span className="text-neutral-500">{listOpen ? '▲' : '▼'}</span>
        </button>
        <span className="text-[10px] text-neutral-600 ml-auto">{sessions.length} sessions</span>
      </div>

      {/* Mobile: collapsible session list */}
      {listOpen && (
        <div className="md:hidden max-h-48 overflow-y-auto border-b border-neutral-800 shrink-0">
          {sessions.map(s => {
            const isActive = s.id === selected
            const age = timeSince(s.mtime)
            return (
              <button
                key={s.id}
                onClick={() => { setSelected(s.id); setListOpen(false) }}
                className={`w-full text-left px-3 py-2 border-b border-neutral-800/30 transition-colors ${
                  isActive ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-400 hover:bg-neutral-800/50'
                }`}
              >
                <div className="text-[11px] font-medium truncate">
                  {s.label || s.id.slice(0, 8)}
                </div>
                <div className="text-[10px] text-neutral-600 truncate" title={s.full_label}>
                  {age} · {(s.size / 1024).toFixed(0)}KB
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* Desktop: session list sidebar */}
      <div className="hidden md:block w-48 shrink-0 border-r border-neutral-800 overflow-y-auto">
        {sessions.map(s => {
          const isActive = s.id === selected
          const age = timeSince(s.mtime)
          return (
            <button
              key={s.id}
              onClick={() => setSelected(s.id)}
              className={`w-full text-left px-3 py-2 border-b border-neutral-800/30 transition-colors ${
                isActive ? 'bg-neutral-800 text-neutral-200' : 'text-neutral-400 hover:bg-neutral-800/50'
              }`}
            >
              <div className="text-[11px] font-medium truncate">
                {s.label || s.id.slice(0, 8)}
              </div>
              <div className="text-[10px] text-neutral-600 truncate" title={s.full_label}>
                {age} · {(s.size / 1024).toFixed(0)}KB
              </div>
            </button>
          )
        })}
      </div>

      {/* Session content */}
      <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] leading-5 min-h-0">
        {loading && lines.length === 0 ? (
          <div className="text-neutral-500">Loading session...</div>
        ) : (
          lines.map((line, i) => (
            <div key={i} className={`whitespace-pre-wrap break-all ${colorLine(line)}`}>
              {line}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function timeSince(isoStr: string): string {
  const ms = Date.now() - new Date(isoStr).getTime()
  const mins = Math.floor(ms / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}
