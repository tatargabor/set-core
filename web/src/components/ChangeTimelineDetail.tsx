import { useEffect, useMemo, useState } from 'react'
import {
  getChangeJournal,
  getChangeSession,
  getChangeTimeline,
  getProjectSessions,
  type ChangeJournal,
  type ChangeTimelineData,
  type SessionInfo,
} from '../lib/api'
import { journalToAttemptGraph } from '../lib/dag/journalToAttemptGraph'
import { enrichWithSessions } from '../lib/dag/enrichWithSessions'
import type { Attempt, AttemptNode, GateResult } from '../lib/dag/types'

interface Props {
  project: string
  changeName: string
}

const GATE_ICON: Record<string, string> = {
  pass: '✓',
  fail: '✗',
  warn: '⚠',
  skip: '–',
  running: '●',
}

const GATE_COLOR: Record<string, string> = {
  pass: 'text-green-400',
  fail: 'text-red-400',
  warn: 'text-amber-400',
  skip: 'text-neutral-500',
  running: 'text-blue-400',
}

const OUTCOME_STYLE: Record<string, string> = {
  merged: 'bg-green-900/40 text-green-300 border-green-500/30',
  retry: 'bg-amber-900/40 text-amber-300 border-amber-500/30',
  failed: 'bg-red-900/40 text-red-300 border-red-500/30',
  'in-progress': 'bg-blue-900/40 text-blue-300 border-blue-500/30',
}

function iconFor(result: GateResult): string {
  if (!result) return '○'
  return GATE_ICON[result] ?? '○'
}

function colorFor(result: GateResult): string {
  if (!result) return 'text-neutral-600'
  return GATE_COLOR[result] ?? 'text-neutral-600'
}

function formatMs(ms: number | null): string {
  if (ms == null) return '–'
  if (ms < 1000) return `${ms}ms`
  const secs = ms / 1000
  if (secs < 60) return `${secs.toFixed(1)}s`
  const mins = Math.floor(secs / 60)
  const rem = Math.floor(secs % 60)
  return `${mins}m${rem > 0 ? ` ${rem}s` : ''}`
}

function formatTokens(n?: number): string {
  if (!n) return ''
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

function shortModel(model?: string): string {
  if (!model) return ''
  const m = model.toLowerCase()
  if (m.includes('opus')) return 'opus'
  if (m.includes('sonnet')) return 'sonnet'
  if (m.includes('haiku')) return 'haiku'
  return model
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ''
  }
}

function attemptDuration(a: Attempt): number {
  const start = Date.parse(a.startedAt)
  const end = a.endedAt ? Date.parse(a.endedAt) : Date.now()
  return Math.max(0, end - start)
}

function sessionsForAttempt(all: SessionInfo[], attempt: Attempt): SessionInfo[] {
  const start = Date.parse(attempt.startedAt)
  const end = attempt.endedAt ? Date.parse(attempt.endedAt) : Date.now()
  return all
    .filter((s) => {
      const t = Date.parse(s.mtime)
      return !Number.isNaN(t) && t >= start - 1000 && t <= end + 2000
    })
    .sort((a, b) => Date.parse(a.mtime) - Date.parse(b.mtime))
}

interface RowProps {
  node: AttemptNode
  selected: boolean
  sessionCount?: number
  onClick: () => void
}

function NodeRow({ node, selected, sessionCount, onClick }: RowProps) {
  const isImpl = node.kind === 'impl'
  const icon = isImpl ? '✎' : iconFor(node.result)
  const color = isImpl ? 'text-violet-300' : colorFor(node.result)
  const isRunning = node.result === 'running'
  const hasDowngrade =
    (node.downgrades && node.downgrades.length > 0) ||
    node.verdictSource === 'classifier_downgrade'
  const model = shortModel(node.model)
  const hasTokens = (node.inputTokens ?? 0) + (node.outputTokens ?? 0) > 0

  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2 px-3 py-1.5 text-left border-t border-neutral-800/70 transition-colors ${
        selected ? 'bg-blue-900/30 ring-1 ring-inset ring-blue-500/40' : 'hover:bg-neutral-900/40'
      }`}
    >
      <span className={`text-sm font-medium w-4 ${color} ${isRunning ? 'animate-pulse' : ''}`}>
        {icon}
      </span>
      <span className="text-xs font-medium text-neutral-200 capitalize w-20 truncate">
        {isImpl ? 'impl' : node.kind.replace('_', ' ')}
      </span>
      {isImpl ? (
        <span className="text-[10px] text-neutral-400 bg-neutral-800 px-1 rounded">
          #{node.attempt}
        </span>
      ) : node.runIndexForKind > 1 ? (
        <span className="text-[10px] text-neutral-400 bg-neutral-800 px-1 rounded">
          ⟳{node.runIndexForKind}
        </span>
      ) : null}
      {hasDowngrade && <span className="text-[11px] text-amber-400">⚖</span>}
      <span className="text-[11px] text-neutral-500 w-12 text-right">{formatMs(node.ms)}</span>
      <span className="text-[10px] text-neutral-600 ml-2">{formatTime(node.startedAt)}</span>
      {model && <span className="text-[10px] text-neutral-400 ml-2">{model}</span>}
      {hasTokens && (
        <span className="text-[10px] text-neutral-500 ml-1">
          {formatTokens(node.inputTokens)}/{formatTokens(node.outputTokens)}
        </span>
      )}
      {isImpl && sessionCount != null && (
        <span className="ml-auto text-[10px] text-neutral-600">
          {sessionCount} session{sessionCount !== 1 ? 's' : ''}
        </span>
      )}
    </button>
  )
}

interface AttemptCardProps {
  attempt: Attempt
  allSessions: SessionInfo[]
  selectedNodeId: string | null
  onSelectNode: (id: string) => void
}

function AttemptCard({ attempt, allSessions, selectedNodeId, onSelectNode }: AttemptCardProps) {
  const outcomeClass = OUTCOME_STYLE[attempt.outcome] ?? OUTCOME_STYLE['in-progress']
  const sessions = useMemo(() => sessionsForAttempt(allSessions, attempt), [allSessions, attempt])
  const dur = attemptDuration(attempt)

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900/40 mb-3 overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-neutral-800 bg-neutral-900/60">
        <span className="text-sm font-semibold text-neutral-200">Attempt #{attempt.n}</span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium ${outcomeClass}`}>
          {attempt.outcome}
          {attempt.retryReason ? ` · ${attempt.retryReason}` : ''}
        </span>
        <span className="text-[10px] text-neutral-500 ml-auto">
          {formatMs(dur)} · {formatTime(attempt.startedAt)}
          {attempt.endedAt ? ` → ${formatTime(attempt.endedAt)}` : ' → running'}
        </span>
      </div>
      {attempt.nodes.map((node) => (
        <NodeRow
          key={node.id}
          node={node}
          selected={selectedNodeId === node.id}
          sessionCount={node.kind === 'impl' ? sessions.length : undefined}
          onClick={() => onSelectNode(node.id)}
        />
      ))}
    </div>
  )
}

interface DetailPaneProps {
  node: AttemptNode | null
  attempt: Attempt | null
  allSessions: SessionInfo[]
  project: string
  changeName: string
}

function DetailPane({ node, attempt, allSessions, project, changeName }: DetailPaneProps) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [sessionLines, setSessionLines] = useState<string[] | null>(null)
  const [sessionLoading, setSessionLoading] = useState(false)

  const isImpl = node?.kind === 'impl'
  const attemptSessions = useMemo(
    () => (attempt ? sessionsForAttempt(allSessions, attempt) : []),
    [allSessions, attempt],
  )

  // Reset session selection when switching nodes.
  useEffect(() => {
    if (!isImpl) {
      setActiveSessionId(null)
      setSessionLines(null)
      return
    }
    // Auto-select the first session for this attempt.
    if (attemptSessions.length > 0) {
      setActiveSessionId(attemptSessions[0].id)
    } else {
      setActiveSessionId(null)
      setSessionLines(null)
    }
  }, [isImpl, node?.id, attemptSessions])

  useEffect(() => {
    if (!isImpl || !activeSessionId) return
    setSessionLoading(true)
    getChangeSession(project, changeName, 500, activeSessionId)
      .then((d) => setSessionLines(d.lines))
      .catch(() => setSessionLines(['(Failed to load session)']))
      .finally(() => setSessionLoading(false))
  }, [isImpl, activeSessionId, project, changeName])

  if (!node) {
    return (
      <div className="h-full flex items-center justify-center p-6 text-[11px] text-neutral-600 italic">
        Click a row on the left to inspect its output or session log.
      </div>
    )
  }

  const hasDowngrade =
    (node.downgrades && node.downgrades.length > 0) ||
    node.verdictSource === 'classifier_downgrade'

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-neutral-800 bg-neutral-900/60 shrink-0">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${isImpl ? 'text-violet-300' : colorFor(node.result)}`}>
            {isImpl ? '✎' : iconFor(node.result)}
          </span>
          <span className="text-sm font-semibold text-neutral-200 capitalize">
            {isImpl ? `impl #${node.attempt}` : node.kind.replace('_', ' ')}
          </span>
          {!isImpl && node.runIndexForKind > 1 && (
            <span className="text-[10px] text-neutral-400 bg-neutral-800 px-1 rounded">
              run #{node.runIndexForKind}
            </span>
          )}
          <span className="text-[10px] text-neutral-500 ml-auto">
            {formatMs(node.ms)} · {formatTime(node.startedAt)}
          </span>
        </div>
        {node.verdictSource && (
          <div className="mt-1 text-[10px] text-neutral-500">
            verdict source <span className="text-neutral-300">{node.verdictSource}</span>
          </div>
        )}
        {hasDowngrade && node.downgrades && node.downgrades.length > 0 && (
          <div className="mt-1 text-[10px] text-amber-400 border border-amber-700/40 bg-amber-900/20 rounded p-1.5">
            downgrade {node.downgrades[0].from} → {node.downgrades[0].to}
            {node.downgrades[0].reason ? ` · ${node.downgrades[0].reason}` : ''}
          </div>
        )}
      </div>

      {isImpl ? (
        <div className="flex-1 min-h-0 flex flex-col">
          {attemptSessions.length === 0 ? (
            <div className="p-3 text-[10px] text-neutral-600 italic">
              No session logs recorded for this attempt window.
            </div>
          ) : (
            <>
              <div className="flex items-center gap-1 px-3 py-1 border-b border-neutral-800/50 overflow-x-auto shrink-0">
                <span className="text-[10px] text-neutral-600 shrink-0 mr-1">sessions</span>
                {attemptSessions.map((s, i) => {
                  const isActive = s.id === activeSessionId
                  const time = formatTime(s.mtime)
                  return (
                    <button
                      key={s.id}
                      onClick={() => setActiveSessionId(s.id)}
                      className={`px-1.5 py-0.5 text-[10px] rounded shrink-0 transition-colors ${
                        isActive
                          ? 'bg-blue-900/60 text-blue-300'
                          : 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-900'
                      }`}
                      title={s.full_label || s.label || s.id}
                    >
                      #{i + 1} {time}
                    </button>
                  )
                })}
              </div>
              <div className="flex-1 min-h-0 overflow-auto p-2">
                {sessionLoading ? (
                  <div className="text-[10px] text-neutral-600 italic">Loading session...</div>
                ) : sessionLines && sessionLines.length > 0 ? (
                  <pre className="bg-neutral-950/60 border border-neutral-800 rounded p-2 text-[11px] text-neutral-400 whitespace-pre-wrap leading-relaxed">
                    {sessionLines.join('\n')}
                  </pre>
                ) : (
                  <div className="text-[10px] text-neutral-600 italic">
                    Click a session button above to load its log.
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-auto p-2">
          {node.output ? (
            <pre className="bg-neutral-950/60 border border-neutral-800 rounded p-2 text-[11px] text-neutral-400 whitespace-pre-wrap leading-relaxed">
              {node.output}
            </pre>
          ) : (
            <div className="text-[10px] text-neutral-600 italic">
              No gate output captured (fast path or cached).
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function ChangeTimelineDetail({ project, changeName }: Props) {
  const [journal, setJournal] = useState<ChangeJournal | null>(null)
  const [timeline, setTimeline] = useState<ChangeTimelineData | null>(null)
  const [allSessions, setAllSessions] = useState<SessionInfo[]>([])
  const [error, setError] = useState<string | null>(null)
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = () => {
      getChangeJournal(project, changeName)
        .then((d) => {
          if (cancelled) return
          setJournal(d)
          setError(null)
        })
        .catch((e) => {
          if (cancelled) return
          const msg = e instanceof Error ? e.message : String(e)
          const looksLikeSpaFallback =
            msg.includes("Unexpected token '<'") || msg.includes('is not valid JSON')
          if (looksLikeSpaFallback) {
            setJournal({ entries: [], grouped: {} })
            setError(null)
          } else {
            setError(msg)
          }
        })
      getProjectSessions(project, changeName)
        .then((d) => {
          if (cancelled) return
          setAllSessions(d.sessions)
        })
        .catch(() => {
          if (cancelled) return
          setAllSessions([])
        })
      getChangeTimeline(project, changeName)
        .then((d) => {
          if (cancelled) return
          setTimeline(d)
        })
        .catch(() => {
          if (cancelled) return
          setTimeline(null)
        })
    }
    load()
    const iv = setInterval(load, 10000)
    return () => {
      cancelled = true
      clearInterval(iv)
    }
  }, [project, changeName])

  const graph = useMemo(() => {
    if (!journal) return null
    try {
      const g = journalToAttemptGraph(journal.entries)
      if (timeline?.sessions) {
        enrichWithSessions(g, timeline.sessions)
      }
      return g
    } catch (err) {
      console.error('journalToAttemptGraph failed for', changeName, err)
      return null
    }
  }, [journal, timeline, changeName])

  // Find the selected node + its attempt for the detail pane.
  const { selectedNode, selectedAttempt } = useMemo(() => {
    if (!graph || !selectedNodeId) return { selectedNode: null, selectedAttempt: null }
    for (const attempt of graph.attempts) {
      for (const node of attempt.nodes) {
        if (node.id === selectedNodeId) {
          return { selectedNode: node, selectedAttempt: attempt }
        }
      }
    }
    return { selectedNode: null, selectedAttempt: null }
  }, [graph, selectedNodeId])

  if (error) {
    return <div className="p-3 text-xs text-red-400">{error}</div>
  }
  if (!graph) {
    return <div className="p-3 text-xs text-neutral-500">Loading timeline...</div>
  }
  if (graph.attempts.length === 0) {
    return <div className="p-3 text-xs text-neutral-600">No journal data for this change yet.</div>
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center gap-4 text-[11px] text-neutral-500 px-3 py-2 border-b border-neutral-800 shrink-0">
        <span>
          {graph.attempts.length} attempt{graph.attempts.length !== 1 ? 's' : ''}
        </span>
        <span>{formatMs(graph.totalMs)}</span>
        <span>
          {graph.totalGateRuns} gate run{graph.totalGateRuns !== 1 ? 's' : ''}
        </span>
        <span>
          {allSessions.length} session{allSessions.length !== 1 ? 's' : ''}
        </span>
      </div>
      <div className="flex-1 min-h-0 flex">
        <div className="w-[50%] min-w-[360px] overflow-auto p-3 border-r border-neutral-800">
          {graph.attempts.map((a) => (
            <AttemptCard
              key={a.n}
              attempt={a}
              allSessions={allSessions}
              selectedNodeId={selectedNodeId}
              onSelectNode={setSelectedNodeId}
            />
          ))}
        </div>
        <div className="flex-1 min-w-0">
          <DetailPane
            node={selectedNode}
            attempt={selectedAttempt}
            allSessions={allSessions}
            project={project}
            changeName={changeName}
          />
        </div>
      </div>
    </div>
  )
}
