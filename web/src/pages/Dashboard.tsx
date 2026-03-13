import { useState, useCallback } from 'react'
import { useWebSocket, type WSEvent } from '../hooks/useWebSocket'
import { useNotifications } from '../hooks/useNotifications'
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

interface Props {
  project: string | null
}

export default function Dashboard({ project }: Props) {
  const [state, setState] = useState<StateData | null>(null)
  const [logLines, setLogLines] = useState<string[]>([])
  const [checkpoint, setCheckpoint] = useState(false)
  const [selectedChange, setSelectedChange] = useState<string | null>(null)
  const [showPlan, setShowPlan] = useState(false)
  const [showTokens, setShowTokens] = useState(false)
  const [showAudit, setShowAudit] = useState(false)
  const [showProgress, setShowProgress] = useState(false)
  const { notify } = useNotifications()

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
        notify('Checkpoint pending', `${project} requires approval`)
        break
      case 'change_complete':
        notify('Change complete', `A change finished in ${project}`)
        break
      case 'error':
        notify('Error', `Error in ${project}`)
        break
    }
  }, [project, notify])

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

  return (
    <div className="flex flex-col h-full">
      <StatusHeader state={state} connected={connected} project={project} />
      {checkpoint && (
        <CheckpointBanner project={project} onDismiss={() => setCheckpoint(false)} />
      )}

      {/* Collapsible panels — between header and main split */}
      <div className="flex items-center gap-3 px-4 py-1 border-b border-neutral-800/50">
        <button
          onClick={() => setShowPlan(p => !p)}
          className="flex items-center gap-1 text-[10px] text-neutral-500 hover:text-neutral-300"
        >
          <span>{showPlan ? '▾' : '▸'}</span>
          <span>Plan</span>
        </button>
        <button
          onClick={() => setShowTokens(p => !p)}
          className="flex items-center gap-1 text-[10px] text-neutral-500 hover:text-neutral-300"
        >
          <span>{showTokens ? '▾' : '▸'}</span>
          <span>Tokens</span>
        </button>
        {(state?.phase_audit_results?.length ?? 0) > 0 && (
          <button
            onClick={() => setShowAudit(p => !p)}
            className="flex items-center gap-1 text-[10px] text-neutral-500 hover:text-neutral-300"
          >
            <span>{showAudit ? '▾' : '▸'}</span>
            <span>Audit</span>
          </button>
        )}
        <button
          onClick={() => setShowProgress(p => !p)}
          className="flex items-center gap-1 text-[10px] text-neutral-500 hover:text-neutral-300"
        >
          <span>{showProgress ? '▾' : '▸'}</span>
          <span>Requirements</span>
        </button>
      </div>
      {showPlan && (
        <div className="border-b border-neutral-800 max-h-[250px] overflow-auto">
          <PlanViewer project={project} />
        </div>
      )}
      {showTokens && (
        <div className="border-b border-neutral-800">
          <TokenChart project={project} />
        </div>
      )}
      {showAudit && state?.phase_audit_results && (
        <div className="border-b border-neutral-800 max-h-[300px] overflow-auto">
          <AuditPanel results={state.phase_audit_results} />
        </div>
      )}
      {showProgress && (
        <div className="border-b border-neutral-800 max-h-[400px] overflow-hidden">
          <ProgressView project={project} />
        </div>
      )}

      <div className="flex-1 min-h-0">
        <ResizableSplit
          top={
            <ChangeTable
              changes={changes}
              project={project}
              selected={selectedChange}
              onSelect={setSelectedChange}
            />
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
