import type { IssueState } from '../../lib/api'
import { STATE_STYLES } from './styles'

export function StateBadge({ state }: { state: IssueState }) {
  const s = STATE_STYLES[state] || STATE_STYLES.new
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium ${s.color} ${s.bg}`}>
      <span>{s.icon}</span>
      <span>{s.label}</span>
    </span>
  )
}
