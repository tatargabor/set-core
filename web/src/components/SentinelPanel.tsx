import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { sendSentinelMessage, type SentinelEvent, type SentinelFindingsData, type SentinelStatusData } from '../lib/api'

// ─── Event styling ────────────────────────────────────────────────

const EVENT_STYLES: Record<string, { icon: string; color: string }> = {
  poll:             { icon: '●', color: 'text-neutral-500' },
  crash:            { icon: '✗', color: 'text-red-400' },
  restart:          { icon: '↻', color: 'text-orange-400' },
  decision:         { icon: '✓', color: 'text-green-400' },
  escalation:       { icon: '⚠', color: 'text-yellow-400' },
  finding:          { icon: '◆', color: 'text-purple-400' },
  assessment:       { icon: '◈', color: 'text-blue-400' },
  message_received: { icon: '📨', color: 'text-blue-300' },
  message_sent:     { icon: '📤', color: 'text-blue-300' },
}

function eventStyle(type: string) {
  return EVENT_STYLES[type] ?? { icon: '?', color: 'text-neutral-400' }
}

// ─── Poll condensation ────────────────────────────────────────────

interface DisplayEvent {
  key: string
  type: 'single' | 'condensed'
  event?: SentinelEvent
  count?: number
  firstTs?: string
  lastTs?: string
  state?: string
}

function condenseEvents(events: SentinelEvent[]): DisplayEvent[] {
  const result: DisplayEvent[] = []
  let i = 0
  while (i < events.length) {
    const e = events[i]
    if (e.type === 'poll') {
      // Collect consecutive polls with same state
      let j = i + 1
      while (j < events.length && events[j].type === 'poll' && events[j].state === e.state) {
        j++
      }
      const count = j - i
      if (count >= 3) {
        result.push({
          key: `condensed-${i}`,
          type: 'condensed',
          count,
          firstTs: events[i].ts,
          lastTs: events[j - 1].ts,
          state: e.state as string,
        })
      } else {
        for (let k = i; k < j; k++) {
          result.push({ key: `single-${k}`, type: 'single', event: events[k] })
        }
      }
      i = j
    } else {
      result.push({ key: `single-${i}`, type: 'single', event: e })
      i++
    }
  }
  return result
}

// ─── Event detail text ────────────────────────────────────────────

function eventDetail(e: SentinelEvent): string {
  switch (e.type) {
    case 'poll': return `state=${e.state}${e.change ? ` change=${e.change}` : ''}${e.iteration != null ? ` iter=${e.iteration}` : ''}`
    case 'crash': return `pid=${e.pid} exit=${e.exit_code}${e.stderr_tail ? ` ${(e.stderr_tail as string).slice(0, 80)}` : ''}`
    case 'restart': return `new_pid=${e.new_pid} attempt=${e.attempt}`
    case 'decision': return `${e.action}: ${e.reason}`
    case 'escalation': return `${e.reason}`
    case 'finding': return `[${e.severity}] ${e.change}: ${e.summary}`
    case 'assessment': return `${e.scope}: ${e.summary}`
    case 'message_received': return `← ${e.sender}: ${e.content}`
    case 'message_sent': return `→ ${e.recipient}: ${e.content}`
    default: return JSON.stringify(e)
  }
}

function formatTime(ts: string): string {
  try {
    const d = new Date(ts)
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return ts }
}

// ─── Severity badges ──────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  bug: 'bg-red-900/50 text-red-300 border-red-700',
  observation: 'bg-yellow-900/50 text-yellow-300 border-yellow-700',
  pattern: 'bg-blue-900/50 text-blue-300 border-blue-700',
  regression: 'bg-red-900/60 text-red-200 border-red-600',
}

const STATUS_COLORS: Record<string, string> = {
  open: 'text-yellow-400',
  fixed: 'text-green-400',
  dismissed: 'text-neutral-500',
}

// ─── Main component ───────────────────────────────────────────────

interface Props {
  project: string
  events: SentinelEvent[]
  findings: SentinelFindingsData
  status: SentinelStatusData
}

export default function SentinelPanel({ project, events, findings, status }: Props) {
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const eventsEndRef = useRef<HTMLDivElement>(null)
  const eventsContainerRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  // Auto-scroll detection
  const handleScroll = useCallback(() => {
    const el = eventsContainerRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
    setAutoScroll(atBottom)
  }, [])

  // Auto-scroll to bottom on new events
  useEffect(() => {
    if (autoScroll) {
      eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [events.length, autoScroll])

  const displayEvents = useMemo(() => condenseEvents(events), [events])

  const handleSend = async () => {
    if (!message.trim() || sending) return
    setSending(true)
    try {
      await sendSentinelMessage(project, message.trim())
      setMessage('')
    } catch (err) {
      console.error('Failed to send:', err)
    } finally {
      setSending(false)
    }
  }

  const isActive = status.is_active

  return (
    <div className="flex flex-col h-full">
      {/* Status bar */}
      <div className={`flex items-center gap-3 px-3 py-1.5 text-xs border-b border-neutral-800 ${
        isActive ? 'bg-green-950/30' : 'bg-neutral-900'
      }`}>
        <span className={isActive ? 'text-green-400' : 'text-neutral-600'}>{isActive ? '\u25C9' : '\u25CB'}</span>
        <span className={isActive ? 'text-green-300' : 'text-neutral-500'}>
          {isActive ? 'ACTIVE' : 'NOT RUNNING'}
        </span>
        {status.member && <span className="text-neutral-500">{status.member}</span>}
        {status.started_at && (
          <span className="text-neutral-600">since {formatTime(status.started_at)}</span>
        )}
        {status.orchestrator_pid && (
          <span className="text-neutral-600">PID {status.orchestrator_pid}</span>
        )}
      </div>

      {/* Content area: events + findings side by side on desktop, stacked on mobile */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row">
        {/* Events stream */}
        <div className="flex-1 min-h-0 flex flex-col border-r border-neutral-800">
          <div className="px-3 py-1 text-xs font-medium text-neutral-500 uppercase tracking-wider border-b border-neutral-800 bg-neutral-900/50">
            Events
          </div>
          <div
            ref={eventsContainerRef}
            onScroll={handleScroll}
            className="flex-1 overflow-auto text-xs p-2 space-y-px"
          >
            {displayEvents.length === 0 && (
              <div className="text-neutral-600 text-center py-8">No events yet</div>
            )}
            {displayEvents.map(de => {
              if (de.type === 'condensed') {
                return (
                  <div key={de.key} className="text-neutral-600 pl-1 py-px">
                    <span className="text-neutral-700">{formatTime(de.firstTs!)}–{formatTime(de.lastTs!)}</span>
                    {' '}● {de.count} polls, state={de.state}
                  </div>
                )
              }
              const e = de.event!
              const style = eventStyle(e.type)
              return (
                <div key={de.key} className={`flex gap-2 py-px ${style.color}`}>
                  <span className="text-neutral-600 shrink-0">{formatTime(e.ts)}</span>
                  <span className="shrink-0">{style.icon}</span>
                  <span className="truncate">{eventDetail(e)}</span>
                </div>
              )
            })}
            <div ref={eventsEndRef} />
          </div>
          {!autoScroll && events.length > 0 && (
            <button
              onClick={() => {
                setAutoScroll(true)
                eventsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
              }}
              className="absolute bottom-14 right-4 px-2 py-1 text-xs bg-neutral-800 text-neutral-400 rounded hover:bg-neutral-700"
            >
              ↓ Latest
            </button>
          )}
        </div>

        {/* Right side: findings + assessments */}
        <div className="w-full lg:w-80 flex flex-col min-h-0 shrink-0">
          {/* Findings */}
          <div className="px-3 py-1 text-xs font-medium text-neutral-500 uppercase tracking-wider border-b border-neutral-800 bg-neutral-900/50">
            Findings ({findings.findings.length})
          </div>
          <div className="flex-1 overflow-auto p-2 space-y-1.5 min-h-[100px]">
            {findings.findings.length === 0 && (
              <div className="text-neutral-600 text-center py-4 text-xs">No findings yet</div>
            )}
            {findings.findings.map(f => (
              <div key={f.id} className={`text-xs rounded border px-2 py-1.5 ${SEVERITY_COLORS[f.severity] ?? 'bg-neutral-900 text-neutral-300 border-neutral-700'}`}>
                <div className="flex items-center gap-2">
                  <span className="font-medium">{f.id}</span>
                  <span className="text-xs opacity-70">{f.change}</span>
                  <span className={`ml-auto text-xs ${STATUS_COLORS[f.status] ?? 'text-neutral-400'}`}>{f.status}</span>
                </div>
                <div className="mt-0.5 opacity-90">{f.summary}</div>
              </div>
            ))}
          </div>

          {/* Assessments */}
          {findings.assessments.length > 0 && (
            <>
              <div className="px-3 py-1 text-xs font-medium text-neutral-500 uppercase tracking-wider border-t border-b border-neutral-800 bg-neutral-900/50">
                Assessment
              </div>
              <div className="p-2 space-y-1">
                {findings.assessments.map((a, i) => (
                  <div key={i} className="text-xs bg-neutral-900/50 border border-neutral-800 rounded px-2 py-1.5">
                    <div className="text-neutral-400 font-medium">{a.scope}</div>
                    <div className="text-neutral-300 mt-0.5">{a.summary}</div>
                    {a.recommendation && <div className="text-neutral-500 mt-0.5">→ {a.recommendation}</div>}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Message input */}
      <div className="flex items-center gap-2 px-3 py-2 border-t border-neutral-800 bg-neutral-900/80">
        <input
          type="text"
          value={message}
          onChange={e => setMessage(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSend() }}
          disabled={!isActive}
          placeholder={isActive ? 'Message to sentinel...' : 'Sentinel not running'}
          className="flex-1 bg-neutral-800 border border-neutral-700 rounded px-3 py-1.5 text-sm text-neutral-200 placeholder-neutral-600 outline-none focus:border-neutral-500 disabled:opacity-50 disabled:cursor-not-allowed"
        />
        <button
          onClick={handleSend}
          disabled={!isActive || !message.trim() || sending}
          className="px-3 py-1.5 text-sm bg-neutral-700 text-neutral-200 rounded hover:bg-neutral-600 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>
    </div>
  )
}
