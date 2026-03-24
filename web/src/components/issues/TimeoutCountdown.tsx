import { useState, useEffect } from 'react'

function calcRemaining(deadline: string): number {
  return Math.max(0, Math.floor((new Date(deadline).getTime() - Date.now()) / 1000))
}

function formatDuration(secs: number): string {
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function TimeoutCountdown({ deadline, startedAt }: { deadline: string; startedAt?: string | null }) {
  const [remaining, setRemaining] = useState(calcRemaining(deadline))

  useEffect(() => {
    const interval = setInterval(() => setRemaining(calcRemaining(deadline)), 1000)
    return () => clearInterval(interval)
  }, [deadline])

  const total = startedAt
    ? Math.max(1, (new Date(deadline).getTime() - new Date(startedAt).getTime()) / 1000)
    : 300
  const elapsed = total - remaining
  const pct = Math.min(100, Math.round((elapsed / total) * 100))

  if (remaining <= 0) {
    return <span className="text-xs text-amber-400">Auto-fixing...</span>
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-amber-400">⏱ {formatDuration(remaining)}</span>
      <div className="w-20 h-1.5 bg-neutral-800 rounded-full overflow-hidden">
        <div className="h-full bg-amber-400/60 rounded-full transition-all" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
