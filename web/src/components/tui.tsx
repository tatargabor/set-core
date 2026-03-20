/** TUI utility components — monospace-native building blocks */

const DONE_STATUSES = new Set(['done', 'merged', 'completed', 'skip_merged'])
const ACTIVE_STATUSES = new Set(['running', 'implementing', 'verifying'])
const FAIL_STATUSES = new Set(['failed', 'verify-failed'])

/** Block-character progress bar: ████░░░░ N/M (P%) */
export function TuiProgress({ done, total, className }: {
  done: number
  total: number
  className?: string
}) {
  if (total === 0) return null
  const pct = Math.round((done / total) * 100)
  const barLen = 10
  const filled = Math.round((done / total) * barLen)
  const bar = '\u2588'.repeat(filled) + '\u2591'.repeat(barLen - filled)
  const allDone = done === total

  return (
    <span className={className ?? 'text-sm'}>
      <span className={allDone ? 'text-blue-400' : 'text-neutral-400'}>{bar}</span>
      {' '}
      <span className="text-neutral-300">{done}/{total}</span>
      {' '}
      <span className="text-neutral-500">({pct}%)</span>
    </span>
  )
}

/** Status indicator: ● done, ◉ running, ○ pending, ✕ failed */
export function TuiStatus({ status, label }: {
  status: string
  label?: boolean
}) {
  let char: string
  let color: string

  if (DONE_STATUSES.has(status)) {
    char = '\u25CF'; color = 'text-blue-400'
  } else if (ACTIVE_STATUSES.has(status)) {
    char = '\u25C9'; color = 'text-green-400'
  } else if (FAIL_STATUSES.has(status)) {
    char = '\u2715'; color = 'text-red-400'
  } else if (status === 'stalled') {
    char = '\u25C9'; color = 'text-yellow-400'
  } else if (status === 'merge-blocked') {
    char = '\u25CB'; color = 'text-orange-400'
  } else {
    char = '\u25CB'; color = 'text-neutral-500'
  }

  return (
    <span className={color}>
      {char}{label !== false && <span className="ml-1">{status}</span>}
    </span>
  )
}

/** Section divider: ── HEADER ── */
export function TuiSection({ label, className }: {
  label: string
  className?: string
}) {
  return (
    <div className={className ?? 'text-sm text-neutral-500 uppercase tracking-wider py-1'}>
      {'── '}{label}{' ──'}
    </div>
  )
}

/** Status color for text (no indicator, just color) */
export function statusColor(status: string): string {
  if (DONE_STATUSES.has(status)) return 'text-blue-400'
  if (ACTIVE_STATUSES.has(status)) return 'text-green-400'
  if (FAIL_STATUSES.has(status)) return 'text-red-400'
  if (status === 'stalled') return 'text-yellow-400'
  if (status === 'planned') return 'text-neutral-400'
  return 'text-neutral-500'
}
