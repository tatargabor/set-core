import { useState, useCallback } from 'react'
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
import type { StateData, ChangeInfo } from '../lib/api'

type PanelTab = 'changes' | 'plan' | 'tokens' | 'requirements' | 'audit'

interface Props {
  project: string | null
}

export default function Dashboard({ project }: Props) {
  const [state, setState] = useState<StateData | null>(null)
  const [logLines, setLogLines] = useState<string[]>([])
  const [checkpoint, setCheckpoint] = useState(false)
  const [selectedChange, setSelectedChange] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<PanelTab>('changes')

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
  ]

  return (
    <div className="flex flex-col h-full">
      <StatusHeader state={state} connected={connected} project={project} />
      {checkpoint && (
        <CheckpointBanner project={project} onDismiss={() => setCheckpoint(false)} />
      )}

      {/* Tab bar */}
      <div className="flex items-center gap-1 px-3 py-1 border-b border-neutral-800 bg-neutral-900/30">
        {tabs.filter(t => !t.hidden).map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-3 py-1 text-[11px] rounded transition-colors ${
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
      <div className="flex-1 min-h-0">
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
      </div>
    </div>
  )
}
