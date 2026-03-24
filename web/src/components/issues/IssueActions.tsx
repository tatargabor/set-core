import { useState } from 'react'
import type { Issue } from '../../lib/api'
import { investigateIssue, fixIssue, dismissIssue, cancelIssue, skipIssue, muteIssue, extendIssueTimeout } from '../../lib/api'
import { STATE_BUTTONS } from './styles'
import { TimeoutCountdown } from './TimeoutCountdown'

const BUTTON_CONFIG: Record<string, { label: string; className: string; confirm?: string }> = {
  investigate:      { label: '🔍 Investigate',      className: 'bg-yellow-600/20 text-yellow-400 hover:bg-yellow-600/30' },
  fix:              { label: '▶ Fix Now',           className: 'bg-green-600/20 text-green-400 hover:bg-green-600/30' },
  investigate_more: { label: '🔍 Investigate More', className: 'bg-yellow-600/20 text-yellow-400 hover:bg-yellow-600/30' },
  retry:            { label: '↻ Retry',             className: 'bg-yellow-600/20 text-yellow-400 hover:bg-yellow-600/30' },
  dismiss:          { label: '✕ Dismiss',           className: 'bg-neutral-700/50 text-neutral-400 hover:bg-neutral-700', confirm: 'Dismiss this issue? It will be marked as won\'t-fix.' },
  cancel:           { label: '⊘ Cancel',            className: 'bg-neutral-700/50 text-neutral-400 hover:bg-neutral-700', confirm: 'Cancel in-progress work on this issue?' },
  skip:             { label: '→ Skip',              className: 'bg-neutral-700/50 text-neutral-400 hover:bg-neutral-700' },
  mute:             { label: '🔇 Mute',             className: 'bg-neutral-700/50 text-neutral-400 hover:bg-neutral-700' },
  extend:           { label: '⏰ Extend',           className: 'bg-amber-600/20 text-amber-400 hover:bg-amber-600/30' },
  reopen:           { label: '● Reopen',            className: 'bg-blue-600/20 text-blue-400 hover:bg-blue-600/30' },
}

interface Props {
  issue: Issue
  project: string
  onAction: () => void
}

export function IssueActions({ issue, project, onAction }: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const buttons = STATE_BUTTONS[issue.state] || []

  const handleAction = async (action: string) => {
    const cfg = BUTTON_CONFIG[action]
    if (cfg?.confirm && !window.confirm(cfg.confirm)) return

    setBusy(true)
    setError(null)
    try {
      switch (action) {
        case 'investigate':
        case 'investigate_more':
        case 'retry':
          await investigateIssue(project, issue.id); break
        case 'fix':
          await fixIssue(project, issue.id); break
        case 'dismiss':
          await dismissIssue(project, issue.id); break
        case 'cancel':
          await cancelIssue(project, issue.id); break
        case 'skip':
          await skipIssue(project, issue.id); break
        case 'mute':
          await muteIssue(project, issue.id); break
        case 'extend':
          await extendIssueTimeout(project, issue.id, 300); break
        case 'reopen':
          await investigateIssue(project, issue.id); break
      }
      onAction()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  if (buttons.length === 0 && issue.state !== 'awaiting_approval') return null

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {buttons.map(action => {
          const cfg = BUTTON_CONFIG[action]
          if (!cfg) return null
          return (
            <button
              key={action}
              disabled={busy}
              onClick={() => handleAction(action)}
              className={`px-2.5 py-1 text-xs rounded font-medium disabled:opacity-50 ${cfg.className}`}
            >
              {cfg.label}
            </button>
          )
        })}
      </div>
      {issue.state === 'awaiting_approval' && issue.timeout_deadline && (
        <TimeoutCountdown deadline={issue.timeout_deadline} startedAt={issue.timeout_started_at} />
      )}
      {error && (
        <div className="text-xs text-red-400 bg-red-950/30 rounded px-2 py-1">{error}</div>
      )}
    </div>
  )
}
