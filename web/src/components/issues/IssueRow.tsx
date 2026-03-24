import type { Issue } from '../../lib/api'
import { SeverityBadge } from './SeverityBadge'
import { StateBadge } from './StateBadge'
import { TimeoutCountdown } from './TimeoutCountdown'

function timeAgo(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime()
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

interface Props {
  issue: Issue
  selected: boolean
  onSelect: (id: string) => void
  checked: boolean
  onCheck: (id: string, checked: boolean) => void
  showEnv?: boolean
}

export function IssueRow({ issue, selected, onSelect, checked, onCheck, showEnv }: Props) {
  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 cursor-pointer rounded transition-colors ${
        selected ? 'bg-neutral-800' : 'hover:bg-neutral-800/50'
      }`}
      onClick={() => onSelect(issue.id)}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={e => { e.stopPropagation(); onCheck(issue.id, e.target.checked) }}
        onClick={e => e.stopPropagation()}
        className="w-3.5 h-3.5 rounded border-neutral-600"
      />
      <span className="text-xs text-neutral-500 font-mono w-16 shrink-0">{issue.id}</span>
      <SeverityBadge severity={issue.severity} />
      <StateBadge state={issue.state} />
      <span className="text-sm text-neutral-300 truncate flex-1">{issue.error_summary}</span>
      {showEnv && <span className="text-xs text-neutral-600 shrink-0">{issue.environment}</span>}
      {issue.group_id && <span className="text-xs text-neutral-600 shrink-0">{issue.group_id}</span>}
      {issue.state === 'awaiting_approval' && issue.timeout_deadline && (
        <TimeoutCountdown deadline={issue.timeout_deadline} startedAt={issue.timeout_started_at} />
      )}
      {issue.state !== 'awaiting_approval' && (
        <span className="text-xs text-neutral-600 shrink-0">{timeAgo(issue.detected_at)}</span>
      )}
      {issue.occurrence_count > 1 && (
        <span className="text-xs text-neutral-500 shrink-0">x{issue.occurrence_count}</span>
      )}
    </div>
  )
}
