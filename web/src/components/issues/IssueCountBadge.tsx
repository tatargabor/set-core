import type { IssueStats } from '../../lib/api'

export function IssueCountBadge({ stats }: { stats?: IssueStats }) {
  if (!stats || stats.total_open === 0) return null
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400">
      {stats.total_open}
    </span>
  )
}
