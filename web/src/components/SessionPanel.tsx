import { useState, useEffect, useRef } from 'react'
import { getProjectSessions, getProjectSession, type SessionInfo } from '../lib/api'

interface Props {
  project: string
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

export default function SessionPanel({ project }: Props) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [lines, setLines] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  // Load session list
  useEffect(() => {
    let cancelled = false
    const load = () => {
      getProjectSessions(project)
        .then(d => {
          if (cancelled) return
          setSessions(d.sessions)
          // Auto-select most recent if none selected
          if (!selected && d.sessions.length > 0) {
            setSelected(d.sessions[0].id)
          }
        })
        .catch(e => { if (!cancelled) setError(String(e)) })
    }
    load()
    const iv = setInterval(load, 15000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project]) // eslint-disable-line react-hooks/exhaustive-deps

  // Load selected session content
  useEffect(() => {
    if (!selected) return
    let cancelled = false
    setLoading(true)
    const load = () => {
      getProjectSession(project, selected, 500)
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

  if (error) return <div className="p-4 text-xs text-red-400">{error}</div>
  if (sessions.length === 0) return <div className="p-4 text-xs text-neutral-500">No sessions found</div>

  return (
    <div className="flex h-full">
      {/* Session list sidebar */}
      <div className="w-48 shrink-0 border-r border-neutral-800 overflow-y-auto">
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
      <div className="flex-1 overflow-y-auto p-3 font-mono text-[11px] leading-5">
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
