import { useState, useCallback, useRef, useEffect } from 'react'
import { useWebSocket, type WSEvent } from '../hooks/useWebSocket'
import StatusHeader from '../components/StatusHeader'
import ChangeTable from '../components/ChangeTable'
import LogPanel from '../components/LogPanel'
import CheckpointBanner from '../components/CheckpointBanner'
import ResizableSplit from '../components/ResizableSplit'
import PlanViewer from '../components/PlanViewer'
import TokenChart from '../components/TokenChart'
import AuditPanel from '../components/AuditPanel'
import PhaseView from '../components/PhaseView'
import ProgressView from '../components/ProgressView'
import DigestView from '../components/DigestView'
import SessionPanel from '../components/SessionPanel'
import OrchestrationChat from '../components/OrchestrationChat'
import SentinelPanel from '../components/SentinelPanel'
import BattleView from './BattleView'
// useIsMobile removed — no longer needed
import { useSentinelData } from '../hooks/useSentinelData'
import { getDigest, getPlans, getState } from '../lib/api'
import type { StateData, ChangeInfo } from '../lib/api'

type PanelTab = 'changes' | 'phases' | 'plan' | 'tokens' | 'requirements' | 'audit' | 'digest' | 'sessions' | 'log' | 'agent' | 'sentinel' | 'battle'

interface Props {
  project: string | null
}

export default function Dashboard({ project }: Props) {
  const [state, setState] = useState<StateData | null>(null)
  const stateJsonRef = useRef<string>('')
  const [logLines, setLogLines] = useState<string[]>([])
  const [checkpoint, setCheckpoint] = useState(false)
  const [checkpointType, setCheckpointType] = useState<string | null>(null)
  const [selectedChange, setSelectedChange] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<PanelTab>('changes')
  // logExpanded removed — log panel is now its own tab
  const [hasDigest, setHasDigest] = useState(false)
  const [hasPlans, setHasPlans] = useState(false)
  // isMobile removed — log panel no longer uses mobile bottom sheet
  const sentinelData = useSentinelData(project)
  const tabBarRef = useRef<HTMLDivElement>(null)

  const onEvent = useCallback((event: WSEvent) => {
    switch (event.event) {
      case 'state_update':
        setState(event.data as StateData)
        break
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

  if (!project) {
    return (
      <div className="flex items-center justify-center h-full text-neutral-500">
        Select a project to begin
      </div>
    )
  }

  const changes = state?.changes ?? []
  const selectedChangeInfo: ChangeInfo | null =
    selectedChange ? changes.find((c) => c.name === selectedChange) ?? null : null
  const hasAudit = (state?.phase_audit_results?.length ?? 0) > 0

  const tabs: { id: PanelTab; label: string; hidden?: boolean }[] = [
    { id: 'changes', label: 'Changes' },
    { id: 'phases', label: 'Phases' },
    { id: 'log', label: 'Log' },
    { id: 'tokens', label: 'Tokens' },
    { id: 'requirements', label: 'Requirements' },
    { id: 'audit', label: 'Audit', hidden: !hasAudit },
    { id: 'digest', label: 'Digest', hidden: !hasDigest },
    { id: 'sessions', label: 'Sessions' },
    { id: 'agent', label: 'Agent' },
    { id: 'sentinel', label: 'Sentinel', hidden: !sentinelData.hasSentinel },
    { id: 'plan', label: 'Plan', hidden: !hasPlans },
    { id: 'battle', label: '\u{1F3AE} Battle' },
  ]

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <StatusHeader state={state} connected={connected} project={project} />
      {checkpoint && (
        <CheckpointBanner project={project} checkpointType={checkpointType} onDismiss={() => setCheckpoint(false)} />
      )}

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
            className={`px-3 min-h-[44px] md:min-h-0 md:py-1 text-sm md:text-[11px] whitespace-nowrap rounded transition-colors ${
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

        {/* Sentinel tab — full height */}
        {activeTab === 'sentinel' && (
          <SentinelPanel
            project={project}
            events={sentinelData.events}
            findings={sentinelData.findings}
            status={sentinelData.status}
          />
        )}

        {/* Changes tab — with change detail panel when selected */}
        {activeTab === 'changes' && (
          selectedChange ? (
            <ResizableSplit
              top={
                <div className="h-full overflow-auto">
                  <ChangeTable
                    changes={changes}
                    project={project}
                    selected={selectedChange}
                    onSelect={setSelectedChange}
                  />
                </div>
              }
              bottom={
                <LogPanel
                  orchLines={[]}
                  selectedChange={selectedChangeInfo}
                  project={project}
                />
              }
              defaultRatio={0.55}
            />
          ) : (
            <div className="h-full overflow-auto">
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

        {activeTab !== 'changes' && activeTab !== 'phases' && activeTab !== 'agent' && activeTab !== 'sentinel' && activeTab !== 'log' && activeTab !== 'battle' && (
          <div className="h-full overflow-auto">
            {activeTab === 'plan' && (
              <PlanViewer project={project} />
            )}
            {activeTab === 'tokens' && (
              <TokenChart changes={changes} />
            )}
            {activeTab === 'requirements' && (
              <ProgressView project={project} />
            )}
            {activeTab === 'audit' && state?.phase_audit_results && (
              <AuditPanel results={state.phase_audit_results} />
            )}
            {activeTab === 'digest' && (
              <DigestView project={project} />
            )}
            {activeTab === 'sessions' && (
              <SessionPanel project={project} change={selectedChange} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
