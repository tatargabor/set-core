import { useState, useCallback, useRef } from 'react'
import { useWebSocket, type WSEvent } from '../hooks/useWebSocket'
import StatusHeader from '../components/StatusHeader'
import ChangeTable from '../components/ChangeTable'
import LogPanel from '../components/LogPanel'
import CheckpointBanner from '../components/CheckpointBanner'
import ResizableSplit from '../components/ResizableSplit'
import PlanViewer from '../components/PlanViewer'
import TokenChart from '../components/TokenChart'
import AuditPanel from '../components/AuditPanel'
import ProgressView from '../components/ProgressView'
import DigestView from '../components/DigestView'
import SessionPanel from '../components/SessionPanel'
import useIsMobile from '../hooks/useIsMobile'
import type { StateData, ChangeInfo } from '../lib/api'

type PanelTab = 'changes' | 'plan' | 'tokens' | 'requirements' | 'audit' | 'digest' | 'sessions'

interface Props {
  project: string | null
}

export default function Dashboard({ project }: Props) {
  const [state, setState] = useState<StateData | null>(null)
  const [logLines, setLogLines] = useState<string[]>([])
  const [checkpoint, setCheckpoint] = useState(false)
  const [checkpointType, setCheckpointType] = useState<string | null>(null)
  const [selectedChange, setSelectedChange] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<PanelTab>('changes')
  const [logExpanded, setLogExpanded] = useState(false)
  const isMobile = useIsMobile()
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
    { id: 'plan', label: 'Plan' },
    { id: 'tokens', label: 'Tokens' },
    { id: 'requirements', label: 'Requirements' },
    { id: 'audit', label: 'Audit', hidden: !hasAudit },
    { id: 'digest', label: 'Digest' },
    { id: 'sessions', label: 'Sessions' },
  ]

  return (
    <div className="flex flex-col h-full">
      <StatusHeader state={state} connected={connected} project={project} />
      {checkpoint && (
        <CheckpointBanner project={project} checkpointType={checkpointType} onDismiss={() => setCheckpoint(false)} />
      )}

      {/* Tab bar */}
      <div
        ref={tabBarRef}
        className="flex items-center gap-1 px-3 py-1 border-b border-neutral-800 bg-neutral-900/30 overflow-x-auto scrollbar-hide"
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
        {isMobile ? (
          <>
            {/* Mobile: stacked — full-height tab content + collapsible log bottom sheet */}
            <div className={`h-full overflow-auto ${logExpanded ? 'pb-[60vh]' : 'pb-11'}`}>
              {activeTab === 'changes' && (
                <ChangeTable
                  changes={changes}
                  project={project}
                  selected={selectedChange}
                  onSelect={setSelectedChange}
                />
              )}
              {activeTab === 'plan' && (
                <PlanViewer project={project} />
              )}
              {activeTab === 'tokens' && (
                <TokenChart project={project} />
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
                <SessionPanel project={project} />
              )}
            </div>

            {/* Mobile log bottom sheet */}
            <div className={`absolute bottom-0 left-0 right-0 bg-neutral-950 border-t border-neutral-800 transition-all duration-200 ${
              logExpanded ? 'h-[60vh]' : 'h-11'
            }`}>
              <button
                onClick={() => setLogExpanded(!logExpanded)}
                className="w-full h-11 flex items-center justify-center gap-2 text-sm text-neutral-400 bg-neutral-900/80 border-b border-neutral-800"
              >
                <span>Logs</span>
                <span className="text-xs">{logExpanded ? '▼' : '▲'}</span>
              </button>
              {logExpanded && (
                <div className="h-[calc(100%-44px)] overflow-auto">
                  <LogPanel
                    orchLines={logLines}
                    selectedChange={selectedChangeInfo}
                    project={project}
                  />
                </div>
              )}
            </div>
          </>
        ) : (
          /* Desktop: resizable split */
          <ResizableSplit
            top={
              <div className="h-full overflow-auto">
                {activeTab === 'changes' && (
                  <ChangeTable
                    changes={changes}
                    project={project}
                    selected={selectedChange}
                    onSelect={setSelectedChange}
                  />
                )}
                {activeTab === 'plan' && (
                  <PlanViewer project={project} />
                )}
                {activeTab === 'tokens' && (
                  <TokenChart project={project} />
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
                  <SessionPanel project={project} />
                )}
              </div>
            }
            bottom={
              <LogPanel
                orchLines={logLines}
                selectedChange={selectedChangeInfo}
                project={project}
              />
            }
            defaultRatio={0.55}
          />
        )}
      </div>
    </div>
  )
}
