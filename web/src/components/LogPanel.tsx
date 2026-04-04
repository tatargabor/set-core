import { useRef, useEffect, useState, useCallback } from 'react'
import type { ChangeInfo, SessionInfo } from '../lib/api'
import { getChangeSession } from '../lib/api'
import useIsMobile from '../hooks/useIsMobile'

interface Props {
  orchLines: string[]
  selectedChange: ChangeInfo | null
  project: string
}

function orchLineColor(line: string): string {
  if (line.includes('ERROR')) return 'text-red-400'
  if (line.includes('WARN')) return 'text-yellow-400'
  if (line.includes('REPLAN')) return 'text-cyan-400'
  if (line.includes('CHECKPOINT')) return 'text-yellow-300'
  return 'text-neutral-400'
}

function sessionLineColor(line: string): string {
  if (line.startsWith('>>>')) return 'text-neutral-200'
  if (line.startsWith('  [Read]') || line.startsWith('  [Glob]') || line.startsWith('  [Grep]'))
    return 'text-cyan-500/70'
  if (line.startsWith('  [Write]') || line.startsWith('  [Edit]'))
    return 'text-amber-400/80'
  if (line.startsWith('  [Bash]'))
    return 'text-purple-400/80'
  if (line.startsWith('  ['))
    return 'text-neutral-500'
  if (line.startsWith('---'))
    return 'text-neutral-600'
  if (line.includes('ERROR') || line.includes('error')) return 'text-red-400'
  if (line.includes('WARN') || line.includes('warning')) return 'text-yellow-400'
  return 'text-neutral-400'
}

const SPLIT_RATIO_KEY = 'set-log-split-ratio'

function loadSplitRatio(): number {
  try {
    const v = localStorage.getItem(SPLIT_RATIO_KEY)
    if (v) {
      const n = parseFloat(v)
      if (n >= 0.15 && n <= 0.85) return n
    }
  } catch {}
  return 0.5
}

/** Scrollable log pane with auto-scroll and jump-to-bottom */
function LogPane({ lines, colorFn, label, lineCount, live }: {
  lines: string[]
  colorFn: (line: string) => string
  label: string
  lineCount?: number
  live?: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight
    }
  }, [lines, autoScroll])

  const handleScroll = () => {
    if (!ref.current) return
    const { scrollTop, scrollHeight, clientHeight } = ref.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }

  return (
    <div className="relative flex flex-col h-full min-w-0">
      <div className="flex items-center px-2 py-0.5 border-b border-neutral-800 bg-neutral-900/50">
        <span className="text-sm text-neutral-500 font-medium">{label}</span>
        <span className="ml-auto text-sm text-neutral-600">
          {lineCount ?? lines.length} lines
          {live && <span className="ml-1.5 text-green-600 animate-pulse">LIVE</span>}
        </span>
      </div>
      <div
        ref={ref}
        onScroll={handleScroll}
        className="flex-1 overflow-auto p-2 text-sm leading-5"
      >
        {lines.map((line, i) => (
          <div key={i} className={`whitespace-pre-wrap break-all ${colorFn(line)}`}>{line}</div>
        ))}
        {lines.length === 0 && (
          <p className="text-neutral-600">No data</p>
        )}
      </div>
      {!autoScroll && (
        <button
          onClick={() => {
            setAutoScroll(true)
            if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
          }}
          className="absolute bottom-2 right-2 px-1.5 py-0.5 text-sm bg-neutral-800 text-neutral-400 rounded hover:bg-neutral-700"
        >
          Bottom
        </button>
      )}
    </div>
  )
}

type SubTab = 'task' | 'build' | 'test' | 'e2e' | 'review' | 'smoke' | 'merge'

interface GateTab {
  id: SubTab
  label: string
  result?: string
  output?: string
  ms?: number
}

const gateResultStyle: Record<string, string> = {
  pass: 'text-green-400',
  fail: 'text-red-400',
  critical: 'text-red-500 font-semibold',
  skip: 'text-neutral-500',
}

function buildGateTabs(change: ChangeInfo): GateTab[] {
  const gates: GateTab[] = [
    { id: 'build', label: 'Build', result: change.build_result, output: change.build_output, ms: change.gate_build_ms },
    { id: 'test', label: 'Test', result: change.test_result, output: change.test_output, ms: change.gate_test_ms },
    { id: 'e2e', label: 'E2E', result: change.e2e_result, output: change.e2e_output, ms: change.gate_e2e_ms },
    { id: 'review', label: 'Review', result: change.review_result, output: change.review_output, ms: change.gate_review_ms },
    { id: 'smoke', label: 'Smoke', result: change.smoke_result, output: change.smoke_output, ms: change.gate_smoke_ms },
  ]
  return gates.filter(g => g.result)
}

function GateOutputPane({ gate }: { gate: GateTab }) {
  return (
    <div className="h-full flex flex-col p-3">
      <div className="flex items-center gap-3 mb-2 shrink-0">
        <span className="text-sm font-medium text-neutral-300">{gate.label}</span>
        <span className={`text-sm ${gateResultStyle[gate.result!] ?? 'text-neutral-400'}`}>{gate.result}</span>
        {gate.ms != null && (
          <span className="text-sm text-neutral-500">{(gate.ms / 1000).toFixed(1)}s</span>
        )}
      </div>
      <div className="flex-1 overflow-auto">
        {gate.output ? (
          <pre className="text-sm text-neutral-400 whitespace-pre-wrap leading-relaxed">{gate.output}</pre>
        ) : (
          <span className="text-sm text-neutral-600">No output</span>
        )}
      </div>
    </div>
  )
}

export default function LogPanel({ orchLines, selectedChange, project }: Props) {
  const [sessions, setSessions] = useState<SessionInfo[]>([])
  const [sessionLines, setSessionLines] = useState<string[]>([])
  const [sessionLoading, setSessionLoading] = useState(false)
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [activeSubTab, setActiveSubTab] = useState<SubTab>('task')
  const [splitRatio, setSplitRatio] = useState(loadSplitRatio)
  const [dragging, setDragging] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const isMobile = useIsMobile()

  // Persist split ratio
  useEffect(() => {
    try { localStorage.setItem(SPLIT_RATIO_KEY, String(splitRatio)) } catch {}
  }, [splitRatio])

  // When change selection changes, load sessions and auto-select sub-tab
  useEffect(() => {
    if (!selectedChange) {
      setSessions([])
      setSessionLines([])
      setActiveSessionId(null)
      setActiveSubTab('task')
      return
    }
    // Auto-select first failing gate, otherwise default to task
    const gates = buildGateTabs(selectedChange)
    const firstFail = gates.find(g => g.result === 'fail' || g.result === 'critical')
    setActiveSubTab(firstFail ? firstFail.id : 'task')

    setSessionLoading(true)
    getChangeSession(project, selectedChange.name, 500)
      .then((data) => {
        setSessions(data.sessions)
        setSessionLines(data.lines)
        setActiveSessionId(data.session_id)
      })
      .catch(() => {
        setSessions([])
        setSessionLines(['(Failed to load session)'])
        setActiveSessionId(null)
      })
      .finally(() => setSessionLoading(false))
  }, [project, selectedChange?.name])

  // Load specific session
  const loadSession = (sessionId: string) => {
    if (!selectedChange) return
    setActiveSessionId(sessionId)
    setSessionLoading(true)
    getChangeSession(project, selectedChange.name, 500, sessionId)
      .then((data) => setSessionLines(data.lines))
      .catch(() => setSessionLines(['(Failed to load session)']))
      .finally(() => setSessionLoading(false))
  }

  // Auto-refresh for running changes
  useEffect(() => {
    if (!activeSessionId || !selectedChange || selectedChange.status !== 'running') return
    const interval = setInterval(() => {
      getChangeSession(project, selectedChange.name, 500, activeSessionId)
        .then((data) => {
          setSessionLines(data.lines)
          if (data.sessions.length !== sessions.length) setSessions(data.sessions)
        })
        .catch(() => {})
    }, 3000)
    return () => clearInterval(interval)
  }, [activeSessionId, project, selectedChange?.name, selectedChange?.status, sessions.length])

  // Drag handler for split resizer
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    setDragging(true)
  }, [])

  useEffect(() => {
    if (!dragging) return
    const onMove = (e: MouseEvent) => {
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const ratio = (e.clientX - rect.left) / rect.width
      setSplitRatio(Math.min(0.85, Math.max(0.15, ratio)))
    }
    const onUp = () => setDragging(false)
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [dragging])

  // Session tab label
  const sessionLabel = (s: SessionInfo, idx: number) => {
    const label = (s as SessionInfo & { label?: string }).label
    if (label) return label
    const d = new Date(s.mtime)
    const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return `#${sessions.length - idx} ${time}`
  }

  // No change selected: full-width orch log
  if (!selectedChange) {
    return (
      <div className="h-full">
        <LogPane lines={orchLines} colorFn={orchLineColor} label="Orchestration Log" />
      </div>
    )
  }

  // Build sub-tabs: Task + gate tabs + merge tab
  const gateTabs = buildGateTabs(selectedChange)
  const mergeLines = selectedChange.status === 'merged'
    ? orchLines.filter(l => {
        const lower = l.toLowerCase()
        return lower.includes(selectedChange.name) && (
          lower.includes('merge') || lower.includes('archive') || lower.includes('merge-queue')
        )
      })
    : []
  const showMerge = mergeLines.length > 0

  // Right pane content (shared between mobile and desktop)
  const sessionPane = (
    <div className="h-full min-w-0 flex flex-col">
      {/* Sub-tab bar: Task | Build | Test | E2E | ... | Merge */}
      <div className="flex items-center gap-1 px-2 py-0.5 border-b border-neutral-800 bg-neutral-900/50 overflow-x-auto shrink-0">
        <button
          onClick={() => setActiveSubTab('task')}
          className={`px-1.5 py-0.5 text-sm rounded shrink-0 ${
            activeSubTab === 'task' ? 'bg-blue-900/60 text-blue-300' : 'text-neutral-500 hover:text-neutral-300'
          }`}
        >
          Task
        </button>
        {gateTabs.map(g => (
          <button
            key={g.id}
            onClick={() => setActiveSubTab(g.id)}
            className={`px-1.5 py-0.5 text-sm rounded shrink-0 flex items-center gap-1 ${
              activeSubTab === g.id ? 'bg-blue-900/60 text-blue-300' : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            {g.label}
            <span className={`text-xs ${gateResultStyle[g.result!] ?? ''}`}>
              {g.result === 'pass' ? '✓' : g.result === 'fail' ? '✗' : g.result === 'skip' ? '–' : ''}
            </span>
          </button>
        ))}
        {showMerge && (
          <button
            onClick={() => setActiveSubTab('merge')}
            className={`px-1.5 py-0.5 text-sm rounded shrink-0 ${
              activeSubTab === 'merge' ? 'bg-blue-900/60 text-blue-300' : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            Merge
          </button>
        )}
      </div>

      {/* Sub-tab content */}
      <div className="flex-1 min-h-0">
        {activeSubTab === 'task' ? (
          <>
            {/* Session picker */}
            <div className="flex items-center gap-1 px-2 py-0.5 border-b border-neutral-800 bg-neutral-900/30 overflow-x-auto">
              <span className="text-sm text-neutral-600 shrink-0 mr-1">{selectedChange.name}</span>
              {sessions.map((s, i) => {
                const isActive = activeSessionId === s.id
                const isLatest = i === 0
                return (
                  <button
                    key={s.id}
                    onClick={() => loadSession(s.id)}
                    className={`px-1.5 py-0.5 text-sm rounded transition-colors shrink-0 ${
                      isActive
                        ? 'bg-neutral-800 text-neutral-200'
                        : 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-900'
                    }`}
                    title={s.full_label || `Session ${s.id.slice(0, 8)}… — ${new Date(s.mtime).toLocaleString()}`}
                  >
                    {sessionLabel(s, i)}{isLatest ? ' *' : ''}
                  </button>
                )
              })}
              {sessions.length === 0 && (
                <span className="text-sm text-neutral-600">No sessions</span>
              )}
            </div>
            {sessionLoading ? (
              <div className="p-2 text-sm text-neutral-600">Loading session...</div>
            ) : (
              <LogPane
                lines={sessionLines}
                colorFn={sessionLineColor}
                label="Session Log"
                live={selectedChange.status === 'running'}
              />
            )}
          </>
        ) : activeSubTab === 'merge' ? (
          <LogPane
            lines={mergeLines}
            colorFn={orchLineColor}
            label="Merge Log"
          />
        ) : (
          // Gate output pane
          (() => {
            const gate = gateTabs.find(g => g.id === activeSubTab)
            return gate ? <GateOutputPane gate={gate} /> : <div className="p-2 text-sm text-neutral-600">No data</div>
          })()
        )}
      </div>
    </div>
  )

  // Mobile: session log only (orch log has its own tab)
  if (isMobile) {
    return <div className="h-full">{sessionPane}</div>
  }

  // Desktop: if no orch lines, show session pane full width
  if (orchLines.length === 0) {
    return <div className="h-full">{sessionPane}</div>
  }

  // Desktop: split view — orch left, session right
  return (
    <div ref={containerRef} className="h-full flex" style={{ userSelect: dragging ? 'none' : undefined }}>
      <div style={{ width: `${splitRatio * 100}%` }} className="h-full min-w-0">
        <LogPane lines={orchLines} colorFn={orchLineColor} label="Orchestration Log" />
      </div>
      <div
        onMouseDown={onMouseDown}
        className={`w-1 cursor-col-resize flex-shrink-0 transition-colors ${
          dragging ? 'bg-blue-500' : 'bg-neutral-800 hover:bg-neutral-600'
        }`}
      />
      <div style={{ width: `${(1 - splitRatio) * 100}%` }}>
        {sessionPane}
      </div>
    </div>
  )
}
