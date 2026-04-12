interface Props {
  attemptCount: number
  totalDurationMs: number
  totalGateRuns: number
  viewMode: 'dag' | 'linear'
  onViewModeChange: (mode: 'dag' | 'linear') => void
}

function formatDuration(ms: number): string {
  if (!ms) return '–'
  const secs = ms / 1000
  if (secs < 60) return `${secs.toFixed(1)}s`
  const mins = Math.floor(secs / 60)
  const rem = Math.floor(secs % 60)
  if (mins < 60) return `${mins}m${rem > 0 ? ` ${rem}s` : ''}`
  const hrs = Math.floor(mins / 60)
  return `${hrs}h ${mins % 60}m`
}

export default function DagToolbar({
  attemptCount,
  totalDurationMs,
  totalGateRuns,
  viewMode,
  onViewModeChange,
}: Props) {
  return (
    <div className="flex items-center gap-4 px-3 py-1.5 border-b border-neutral-800 text-xs text-neutral-500 bg-neutral-950/50">
      <span>
        {attemptCount} attempt{attemptCount !== 1 ? 's' : ''}
      </span>
      <span>{formatDuration(totalDurationMs)}</span>
      <span>
        {totalGateRuns} gate run{totalGateRuns !== 1 ? 's' : ''}
      </span>
      <div className="ml-auto flex items-center bg-neutral-900 rounded border border-neutral-800">
        {(['dag', 'linear'] as const).map((m) => (
          <button
            key={m}
            onClick={() => onViewModeChange(m)}
            className={`px-2 py-0.5 text-xs ${
              viewMode === m
                ? 'bg-neutral-800 text-neutral-200'
                : 'text-neutral-500 hover:text-neutral-300'
            }`}
          >
            {m === 'dag' ? 'DAG' : 'Log'}
          </button>
        ))}
      </div>
    </div>
  )
}
