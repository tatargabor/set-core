import type { ChangeInfo } from '../lib/api'

interface Props {
  change: ChangeInfo
}

interface Phase {
  name: string
  ms?: number
  result?: 'pass' | 'fail' | 'skip' | 'current' | 'pending'
}

const phaseColors: Record<string, string> = {
  pass: 'bg-green-700',
  fail: 'bg-red-700',
  skip: 'bg-neutral-700',
  current: 'bg-blue-600 animate-pulse',
  pending: 'bg-neutral-800',
}

const phaseLabelColors: Record<string, string> = {
  pass: 'text-green-400',
  fail: 'text-red-400',
  skip: 'text-neutral-600',
  current: 'text-blue-400',
  pending: 'text-neutral-600',
}

function formatMs(ms?: number): string {
  if (!ms) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function derivePhases(c: ChangeInfo): Phase[] {
  const isRunning = ['running', 'implementing'].includes(c.status)
  const isVerifying = c.status === 'verifying'
  const isDone = ['done', 'merged', 'completed', 'skip_merged'].includes(c.status)
  const isFailed = ['failed', 'verify-failed'].includes(c.status)

  // Estimate implementation time: total time minus gate time
  const totalMs = c.started_at
    ? (c.completed_at ? new Date(c.completed_at).getTime() : Date.now()) - new Date(c.started_at).getTime()
    : 0
  const gateMs = c.gate_total_ms ?? 0
  const implMs = totalMs > gateMs ? totalMs - gateMs : 0

  const phases: Phase[] = []

  // Implementation phase
  if (c.started_at) {
    let implResult: Phase['result'] = 'pending'
    if (c.build_result || c.test_result || c.review_result || c.smoke_result || isDone || isFailed) {
      implResult = 'pass'
    } else if (isRunning) {
      implResult = 'current'
    }
    phases.push({ name: 'Impl', ms: implMs > 0 ? implMs : undefined, result: implResult })
  }

  // Build
  if (c.build_result) {
    phases.push({ name: 'Build', ms: c.gate_build_ms, result: c.build_result as Phase['result'] })
  } else if (isVerifying) {
    phases.push({ name: 'Build', result: 'current' })
  }

  // Test
  if (c.test_result) {
    phases.push({ name: 'Test', ms: c.gate_test_ms, result: c.test_result as Phase['result'] })
  } else if (c.build_result === 'pass' && isVerifying) {
    phases.push({ name: 'Test', result: 'current' })
  }

  // Review
  if (c.review_result) {
    phases.push({ name: 'Review', ms: c.gate_review_ms, result: c.review_result as Phase['result'] })
  } else if (c.test_result === 'pass' && isVerifying) {
    phases.push({ name: 'Review', result: 'current' })
  }

  // Smoke
  if (c.smoke_result) {
    phases.push({ name: 'Smoke', ms: c.gate_verify_ms, result: c.smoke_result as Phase['result'] })
  } else if (c.review_result && isVerifying) {
    phases.push({ name: 'Smoke', result: 'current' })
  }

  // E2E
  if (c.e2e_result) {
    phases.push({ name: 'E2E', ms: c.gate_e2e_ms, result: c.e2e_result as Phase['result'] })
  } else if ((c.smoke_result || c.review_result) && isVerifying) {
    phases.push({ name: 'E2E', result: 'current' })
  }

  // Merge
  if (isDone) {
    phases.push({ name: 'Merge', result: 'pass' })
  }

  return phases
}

export default function ChangeTimeline({ change }: Props) {
  const phases = derivePhases(change)

  if (phases.length === 0) {
    return <div className="px-4 py-2 text-sm text-neutral-600">No timeline data</div>
  }

  // Calculate total for proportional widths
  const totalMs = phases.reduce((s, p) => s + (p.ms ?? 0), 0)

  return (
    <div className="px-4 py-2">
      <div className="flex gap-px h-5 rounded overflow-hidden">
        {phases.map((p) => {
          // Use proportional width if we have timing, otherwise equal
          const widthStyle = totalMs > 0 && p.ms
            ? { flexGrow: p.ms / totalMs }
            : { flexGrow: 1 }

          return (
            <div
              key={p.name}
              className={`relative flex items-center justify-center min-w-[40px] ${phaseColors[p.result ?? 'pending']}`}
              style={widthStyle}
              title={`${p.name}${p.ms ? ': ' + formatMs(p.ms) : ''}`}
            >
              <span className={`text-sm font-medium ${phaseLabelColors[p.result ?? 'pending']}`}>
                {p.name}
                {p.ms ? <span className="ml-0.5 opacity-70">{formatMs(p.ms)}</span> : null}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
