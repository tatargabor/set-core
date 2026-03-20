import { useState } from 'react'
import { approve, stopOrchestrator } from '../lib/api'

interface Props {
  project: string
  checkpointType: string | null
  onDismiss: () => void
}

export default function CheckpointBanner({ project, checkpointType, onDismiss }: Props) {
  const [loading, setLoading] = useState<string | null>(null)
  const [confirmStop, setConfirmStop] = useState(false)
  const [confirmApprove, setConfirmApprove] = useState(false)

  const handleApprove = async () => {
    if (!confirmApprove) {
      setConfirmApprove(true)
      return
    }
    setLoading('approve')
    try {
      await approve(project)
      onDismiss()
    } catch {
      // error will show in state
    }
    setLoading(null)
    setConfirmApprove(false)
  }

  const handleStop = async () => {
    if (!confirmStop) {
      setConfirmStop(true)
      return
    }
    setLoading('stop')
    try {
      await stopOrchestrator(project)
      onDismiss()
    } catch {
      // error will show in state
    }
    setLoading(null)
    setConfirmStop(false)
  }

  const isMcpAuth = checkpointType === 'mcp_auth'

  return (
    <div className={`flex items-center gap-3 px-4 py-3 border-b shrink-0 ${
      isMcpAuth
        ? 'bg-orange-900/30 border-orange-800/50'
        : 'bg-yellow-900/30 border-yellow-800/50'
    }`}>
      <div className="flex-1">
        {isMcpAuth ? (
          <>
            <span className="text-orange-300 text-sm font-medium block">
              MCP Authentication Required
            </span>
            <span className="text-orange-400/70 text-sm">
              Design MCP needs authentication. Run <code className="bg-neutral-800 px-1 rounded">/mcp</code> → select server → Authenticate in Claude Code, then approve.
            </span>
          </>
        ) : (
          <span className="text-yellow-300 text-sm font-medium">
            Checkpoint pending — orchestration is waiting for approval
          </span>
        )}
      </div>
      <button
        onClick={handleApprove}
        disabled={loading !== null}
        className={`px-3 py-1.5 text-sm rounded font-medium disabled:opacity-50 ${
          confirmApprove
            ? 'bg-green-600 text-white hover:bg-green-500'
            : 'bg-green-700 text-white hover:bg-green-600'
        }`}
      >
        {loading === 'approve' ? 'Approving...' : confirmApprove ? 'Are you sure?' : 'Approve'}
      </button>
      <button
        onClick={handleStop}
        disabled={loading !== null}
        className={`px-3 py-1.5 text-sm rounded font-medium disabled:opacity-50 ${
          confirmStop
            ? 'bg-red-700 text-white hover:bg-red-600'
            : 'bg-neutral-700 text-neutral-300 hover:bg-neutral-600'
        }`}
      >
        {confirmStop ? 'Confirm Stop' : 'Stop'}
      </button>
    </div>
  )
}
