import { useState, useCallback, useRef, useEffect, useMemo, lazy, Suspense } from 'react'
import { useWebSocket, type WSEvent } from '../hooks/useWebSocket'
import StatusHeader from '../components/StatusHeader'
import ChangeTable from '../components/ChangeTable'
import LogPanel from '../components/LogPanel'
import CheckpointBanner from '../components/CheckpointBanner'
import { CompletionCard } from '../components/CompletionCard'
import PlanViewer from '../components/PlanViewer'
import TokenChart from '../components/TokenChart'
import AuditPanel from '../components/AuditPanel'
import PhaseView from '../components/PhaseView'
import DigestView from '../components/DigestView'
import SessionPanel from '../components/SessionPanel'
import OrchestrationChat from '../components/OrchestrationChat'
// SentinelPanel replaced by raw log view
import ShutdownProgress from '../components/ShutdownProgress'
import LearningsPanel from '../components/LearningsPanel'
const ChangeDagPanel = lazy(() => import('../components/ChangeDagPanel'))
import BattleView from './BattleView'
import ActivityView from '../components/ActivityView'
// useIsMobile removed — no longer needed
// useSentinelData removed — sentinel tab now shows raw log
import { getDigest, getPlans, getState, getLog, getSentinelLog } from '../lib/api'
import type { StateData } from '../lib/api'

type PanelTab = 'changes' | 'phases' | 'plan' | 'tokens' | 'audit' | 'digest' | 'sessions' | 'log' | 'agent' | 'sentinel' | 'learnings' | 'battle' | 'activity'

interface Props {
  project: string | null
  /** When set from route, forces this tab active on mount */
  initialTab?: string
}

export default function Dashboard({ project, initialTab }: Props) {
  const [state, setState] = useState<StateData | null>(null)
  const stateJsonRef = useRef<string>('')
  const [logLines, setLogLines] = useState<string[]>([])
  const [checkpoint, setCheckpoint] = useState(false)
  const [checkpointType, setCheckpointType] = useState<string | null>(null)
  const [selectedChange, setSelectedChange] = useState<string | null>(null)
  // autoFollow drives two coupled behaviors:
  //   1) selected change tracks the running change (effect below)
  //   2) the DAG re-fits the viewport when new nodes arrive (ChangeDagPanel)
  // The checkbox lives in DagToolbar and is passed down via ChangeDagPanel.
  // Preference persists in localStorage so it survives reloads.
  const [autoFollow, setAutoFollow] = useState(() => {
    try {
      // Default to ON — prior manual opt-out is respected via the explicit '0' marker.
      const v = localStorage.getItem('set-auto-follow')
      return v === null ? true : v === '1'
    } catch { return true }
  })
  // URL-backed tab state: ?tab=digest&sub=domains
  const params = useMemo(() => new URLSearchParams(window.location.search), [])
  const [activeTab, setActiveTabRaw] = useState<PanelTab>(() => {
    // Route-driven tab takes priority over query param
    if (initialTab && ['changes','phases','plan','tokens','context','audit','digest','sessions','log','agent','sentinel','learnings','battle','activity'].includes(initialTab)) {
      return initialTab as PanelTab
    }
    const t = params.get('tab')
    return (t && ['changes','phases','plan','tokens','audit','digest','sessions','log','agent','sentinel','learnings','battle','activity'].includes(t)) ? t as PanelTab : 'changes'
  })
  const setActiveTab = useCallback((tab: PanelTab) => {
    setActiveTabRaw(tab)
    const url = new URL(window.location.href)
    url.searchParams.set('tab', tab)
    if (tab !== 'digest') url.searchParams.delete('sub')
    window.history.replaceState(null, '', url.toString())
  }, [])
  // logExpanded removed — log panel is now its own tab
  const [hasDigest, setHasDigest] = useState(false)
  const [hasPlans, setHasPlans] = useState(false)
  // isMobile removed — log panel no longer uses mobile bottom sheet
  const [sentinelLogLines, setSentinelLogLines] = useState<string[]>([])
  const tabBarRef = useRef<HTMLDivElement>(null)

  const onEvent = useCallback((event: WSEvent) => {
    switch (event.event) {
      case 'state_update': {
        // Dedup against REST poll to prevent flickering between WS and REST data
        const json = JSON.stringify(event.data)
        if (json !== stateJsonRef.current) {
          stateJsonRef.current = json
          setState(event.data as StateData)
        }
        break
      }
      case 'log_lines': {
        const { lines } = event.data as { lines: string[] }
        setLogLines((prev) => [...prev, ...lines].slice(-2000))
        break
      }
      case 'checkpoint_pending':
        setCheckpoint(true)
        setCheckpointType((event.data as { type?: string })?.type ?? null)
        break
    }
  }, [])

  const { connected } = useWebSocket({ project, onEvent })

  // REST poll fallback — fetch state periodically in case WS watcher is down
  useEffect(() => {
    if (!project) return
    let cancelled = false
    const poll = () => {
      getState(project)
        .then(d => {
          if (cancelled) return
          const json = JSON.stringify(d)
          if (json !== stateJsonRef.current) {
            stateJsonRef.current = json
            setState(d)
          }
        })
        .catch(() => {})
    }
    // Initial fetch after short delay (give WS a chance first)
    const t = setTimeout(poll, 2000)
    // Then poll every 5s
    const iv = setInterval(poll, 5000)
    return () => { cancelled = true; clearTimeout(t); clearInterval(iv) }
  }, [project])

  // REST log fallback — fetch log via REST if WS doesn't provide it
  useEffect(() => {
    if (!project) return
    let cancelled = false
    const fetchLog = () => {
      getLog(project)
        .then(d => {
          if (cancelled) return
          const lines = d.lines ?? []
          if (lines.length > 0) {
            setLogLines(prev => prev.length > 0 ? prev : lines)
          }
        })
        .catch(() => {})
    }
    // Fetch after 3s (give WS a chance first)
    const t = setTimeout(fetchLog, 3000)
    // Re-fetch every 10s if still empty
    const iv = setInterval(() => {
      setLogLines(prev => {
        if (prev.length === 0) fetchLog()
        return prev
      })
    }, 10000)
    return () => { cancelled = true; clearTimeout(t); clearInterval(iv) }
  }, [project])

  // Check if digest exists (poll until it does)
  useEffect(() => {
    if (!project) return
    let cancelled = false
    const check = () => {
      getDigest(project)
        .then(d => { if (!cancelled && d.exists) setHasDigest(true) })
        .catch(() => {})
    }
    check()
    const iv = setInterval(check, 15000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project])

  // Check if plans exist
  useEffect(() => {
    if (!project) return
    let cancelled = false
    const check = () => {
      getPlans(project)
        .then(d => { if (!cancelled) setHasPlans(d.plans.length > 0) })
        .catch(() => {})
    }
    check()
    const iv = setInterval(check, 15000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project])

  // Poll sentinel log when sentinel tab is active
  useEffect(() => {
    if (!project || activeTab !== 'sentinel') return
    let timer: ReturnType<typeof setTimeout>
    let cancelled = false
    const poll = () => {
      getSentinelLog(project, 500)
        .then(d => {
          if (!cancelled && d.lines) setSentinelLogLines(d.lines)
          timer = setTimeout(poll, 3000)
        })
        .catch(() => { timer = setTimeout(poll, 10000) })
    }
    poll()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [project, activeTab])

  if (!project) {
    return (
      <div className="flex items-center justify-center h-full text-neutral-500">
        Select a project to begin
      </div>
    )
  }

  const changes = state?.changes ?? []

  // Persist autoFollow
  useEffect(() => {
    try { localStorage.setItem('set-auto-follow', autoFollow ? '1' : '0') } catch {}
  }, [autoFollow])

  // Auto-follow: select the running change, but only on transitions.
  //
  // Previous implementation re-selected the running change on every poll,
  // which snapped the user back whenever they manually clicked a different
  // row — the next 5s REST poll reasserted the running change and the
  // manual click silently disappeared. Track which running change we
  // last auto-selected and fire setSelectedChange only when that changes
  // (new change entered `running`, or autoFollow was just turned on with
  // a running change already in progress). This lets the user park on
  // any row they want without the pager pulling them back.
  const lastAutoSelectedRunningRef = useRef<string | null>(null)
  useEffect(() => {
    if (!autoFollow) {
      lastAutoSelectedRunningRef.current = null
      return
    }
    if (changes.length === 0) return
    const running = changes.find(c => c.status === 'running')
    if (!running) {
      lastAutoSelectedRunningRef.current = null
      return
    }
    if (running.name !== lastAutoSelectedRunningRef.current) {
      lastAutoSelectedRunningRef.current = running.name
      setSelectedChange(running.name)
    }
  }, [autoFollow, changes])

  // Auto-select first change when none selected
  useEffect(() => {
    if (!selectedChange && changes.length > 0) {
      setSelectedChange(changes[0].name)
    }
  }, [selectedChange, changes])
  const hasAudit = (state?.phase_audit_results?.length ?? 0) > 0

  const tabs: { id: PanelTab; label: string; hidden?: boolean }[] = [
    // High-level status (what's happening)
    { id: 'changes', label: 'Changes' },
    { id: 'activity', label: 'Activity' },
    { id: 'phases', label: 'Phases' },
    // Runtime state
    { id: 'sessions', label: 'Sessions' },
    { id: 'sentinel', label: 'Sentinel' },
    // Diagnostics / details
    { id: 'log', label: 'Log' },
    { id: 'tokens', label: 'Tokens' },
    { id: 'digest', label: 'Digest', hidden: !hasDigest },
    { id: 'audit', label: 'Audit', hidden: !hasAudit },
    { id: 'plan', label: 'Plan', hidden: !hasPlans },
    // Knowledge
    { id: 'learnings', label: 'Learnings' },
    // Conversational supervisor (second-to-last)
    { id: 'agent', label: 'Agent' },
    // Game (always last)
    { id: 'battle', label: '\u{1F3AE} Battle' },
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <StatusHeader state={state} connected={connected} project={project} />
      {checkpoint && (
        <CheckpointBanner project={project} checkpointType={checkpointType} onDismiss={() => setCheckpoint(false)} />
      )}
      {state?.status === 'done' || state?.status === 'awaiting_confirmation' ? (
        <div className="px-3 pt-2">
          <CompletionCard project={project} timeout={300} />
        </div>
      ) : null}

      {/* Tab bar — shrink-0 keeps it fixed at top within flex column */}
      <div
        ref={tabBarRef}
        className="flex items-center gap-1 px-3 py-1 border-b border-neutral-800 bg-neutral-900 overflow-x-auto max-w-full scrollbar-hide shrink-0"
      >
        {tabs.filter(t => !t.hidden).map(t => (
          <button
            key={t.id}
            onClick={() => {
              setActiveTab(t.id)
              // Auto-scroll active tab into view on mobile
              if (tabBarRef.current) {
                const btn = tabBarRef.current.querySelector(`[data-tab="${t.id}"]`)
                btn?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
              }
            }}
            data-tab={t.id}
            className={`px-3 min-h-[44px] md:min-h-0 md:py-1 text-sm whitespace-nowrap rounded transition-colors ${
              activeTab === t.id
                ? 'bg-neutral-800 text-neutral-200 font-medium'
                : 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content + log split */}
      <div className="flex-1 min-h-0 relative">
        {/* Agent tab — full height */}
        {activeTab === 'agent' && (
          <OrchestrationChat project={project} />
        )}

        {/* Battle tab — always mounted, hidden when not active */}
        <div className={`h-full ${activeTab === 'battle' ? '' : 'hidden'}`}>
          <BattleView project={project} changes={changes} isVisible={activeTab === 'battle'} />
        </div>

        {/* Sentinel tab — raw stdout log */}
        {activeTab === 'sentinel' && (
          <div className="h-full overflow-y-auto p-3 font-mono text-xs">
            {sentinelLogLines.length === 0 ? (
              <div className="text-neutral-600">No sentinel log yet</div>
            ) : (
              sentinelLogLines.map((line, i) => (
                <div key={i} className={`py-0.5 whitespace-pre-wrap ${
                  line.includes('ERROR') || line.includes('FAIL') ? 'text-red-400' :
                  line.includes('WARNING') || line.includes('WARN') ? 'text-amber-400' :
                  line.includes('merged') || line.includes('SUCCESS') || line.includes('fixed') ? 'text-green-400' :
                  line.startsWith('#') || line.startsWith('|') ? 'text-neutral-300' :
                  'text-neutral-500'
                }`}>
                  {line}
                </div>
              ))
            )}
          </div>
        )}

        {/* Changes tab — with change detail panel when selected.
         * Layout: table auto-sizes to its content (shrink-0 with a 50% cap
         * so the DAG below always gets at least half the viewport, no
         * matter how long the change list grows); ChangeDagPanel fills the
         * rest and carries its own DAG/Log view toggle. No separate
         * Log/Timeline header here. */}
        {activeTab === 'changes' && (
          selectedChange ? (
            /* Hard 50/50 split — basis-0 + equal grow on both children
               gives exact halves regardless of content size. shrink-0 is
               removed so flexbox can compute both heights from basis. */
            <div className="h-full flex flex-col">
              <div className="basis-0 grow shrink min-h-0 overflow-auto border-b border-neutral-800">
                <ShutdownProgress project={project} />
                <ChangeTable
                  changes={changes}
                  project={project}
                  selected={selectedChange}
                  onSelect={setSelectedChange}
                />
              </div>
              <div className="basis-0 grow shrink min-h-0 relative">
                <Suspense fallback={<div className="p-3 text-sm text-neutral-500">Loading DAG...</div>}>
                  <ChangeDagPanel
                    project={project}
                    changeName={selectedChange}
                    autoFollow={autoFollow}
                    onAutoFollowChange={setAutoFollow}
                  />
                </Suspense>
              </div>
            </div>
          ) : (
            <div className="h-full overflow-auto">
              <ShutdownProgress project={project} />
              <ChangeTable
                changes={changes}
                project={project}
                selected={selectedChange}
                onSelect={setSelectedChange}
              />
            </div>
          )
        )}

        {/* Log tab — orchestration log full height */}
        {activeTab === 'log' && (
          <div className="h-full">
            <LogPanel
              orchLines={logLines}
              selectedChange={null}
              project={project}
            />
          </div>
        )}

        {/* All other tabs — full height, no log panel */}
        {activeTab === 'phases' && (
          <div className="h-full overflow-auto">
            <PhaseView changes={changes} state={state} />
          </div>
        )}

        {/* Learnings tab — full height */}
        {activeTab === 'learnings' && (
          <div className="h-full overflow-auto">
            <LearningsPanel project={project} />
          </div>
        )}

        {/* Activity tab — time-based activity timeline */}
        {activeTab === 'activity' && (
          <div className="h-full overflow-auto">
            <ActivityView project={project} isRunning={!!state && state.status !== 'done'} />
          </div>
        )}

        {activeTab !== 'changes' && activeTab !== 'phases' && activeTab !== 'agent' && activeTab !== 'sentinel' && activeTab !== 'log' && activeTab !== 'battle' && activeTab !== 'learnings' && activeTab !== 'activity' && (
          <div className="h-full overflow-auto">
            {activeTab === 'plan' && (
              <PlanViewer project={project} />
            )}
            {activeTab === 'tokens' && (
              <TokenChart changes={changes} project={project} />
            )}
            {activeTab === 'audit' && state?.phase_audit_results && (
              <AuditPanel results={state.phase_audit_results} />
            )}
            {activeTab === 'digest' && (
              <DigestView project={project} />
            )}
            {activeTab === 'sessions' && (
              <SessionPanel project={project} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
