import { useState, useEffect } from 'react'
import { getLearnings, type LearningsData, type ReviewFindingEntry, type ReflectionEntry, type GateStatEntry } from '../lib/api'

type Section = 'all' | 'reflections' | 'review' | 'gates' | 'sentinel'

interface Props {
  project: string
}

const SEV_STYLE: Record<string, string> = {
  CRITICAL: 'bg-red-900/50 text-red-300 border-red-700',
  HIGH: 'bg-orange-900/50 text-orange-300 border-orange-700',
  MEDIUM: 'bg-yellow-900/50 text-yellow-300 border-yellow-700',
}

const FINDING_STATUS_STYLE: Record<string, string> = {
  open: 'text-yellow-400',
  fixed: 'text-green-400',
  dismissed: 'text-neutral-500',
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export default function LearningsPanel({ project }: Props) {
  const [data, setData] = useState<LearningsData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [section, setSection] = useState<Section>('all')

  useEffect(() => {
    let cancelled = false
    const load = () => {
      getLearnings(project)
        .then(d => { if (!cancelled) { setData(d); setError(null) } })
        .catch(e => { if (!cancelled) setError(e.message) })
    }
    load()
    const iv = setInterval(load, 15000)
    return () => { cancelled = true; clearInterval(iv) }
  }, [project])

  if (error) {
    return <div className="p-4 text-red-400 text-sm">{error}</div>
  }
  if (!data) {
    return <div className="p-4 text-neutral-500 text-sm">Loading learnings...</div>
  }

  const reflCount = data.reflections.with_reflection
  const reviewCount = data.review_findings.entries.length
  const sentinelCount = data.sentinel_findings.findings?.length ?? 0
  const hasGates = Object.keys(data.gate_stats.per_gate).length > 0

  const sections: { id: Section; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'reflections', label: `Reflections (${reflCount})` },
    { id: 'review', label: `Review (${reviewCount})` },
    { id: 'gates', label: 'Gates' },
    { id: 'sentinel', label: `Sentinel (${sentinelCount})` },
  ]

  const show = (s: Section) => section === 'all' || section === s

  return (
    <div className="p-4 space-y-6 max-w-4xl">
      {/* Section selector */}
      <div className="flex gap-1 flex-wrap">
        {sections.map(s => (
          <button
            key={s.id}
            onClick={() => setSection(s.id)}
            className={`px-3 py-1 text-sm rounded transition-colors ${
              section === s.id
                ? 'bg-neutral-700 text-neutral-200'
                : 'text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Reflections */}
      {show('reflections') && (
        <SectionBlock title="Agent Reflections" count={reflCount}>
          {reflCount === 0 ? (
            <Empty>No agent reflections yet</Empty>
          ) : (
            data.reflections.reflections.map(r => (
              <ReflectionRow key={r.branch} reflection={r} />
            ))
          )}
        </SectionBlock>
      )}

      {/* Review Findings */}
      {show('review') && (
        <SectionBlock title="Review Findings" count={reviewCount}>
          {data.review_findings.recurring_patterns.length > 0 && (
            <div className="mb-3 p-2 bg-neutral-900/50 border border-neutral-800 rounded">
              <div className="text-sm font-medium text-neutral-400 mb-1">Recurring Patterns</div>
              {data.review_findings.recurring_patterns.map((p, i) => (
                <div key={i} className="text-sm text-neutral-300">
                  <span className="text-neutral-500">{p.count}x</span> {p.pattern}
                </div>
              ))}
            </div>
          )}
          {reviewCount === 0 ? (
            <Empty>No review findings</Empty>
          ) : (
            <ReviewFindings entries={data.review_findings.entries} />
          )}
        </SectionBlock>
      )}

      {/* Gate Performance */}
      {show('gates') && (
        <SectionBlock title="Gate Performance" count={hasGates ? Object.keys(data.gate_stats.per_gate).length : 0}>
          {!hasGates ? (
            <Empty>No gate data yet</Empty>
          ) : (
            <GatePerformance stats={data.gate_stats.per_gate} retry={data.gate_stats.retry_summary} />
          )}
        </SectionBlock>
      )}

      {/* Sentinel Findings */}
      {show('sentinel') && (
        <SectionBlock title="Sentinel Findings" count={sentinelCount}>
          {sentinelCount === 0 ? (
            <Empty>No sentinel findings</Empty>
          ) : (
            <div className="space-y-1.5">
              {data.sentinel_findings.findings.map((f: { id: string; severity: string; change: string; summary: string; status: string }) => (
                <div key={f.id} className={`text-sm rounded border px-2 py-1.5 ${SEV_STYLE[f.severity] ?? 'bg-neutral-900 text-neutral-300 border-neutral-700'}`}>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{f.id}</span>
                    <span className="opacity-70">{f.change}</span>
                    <span className={`ml-auto ${FINDING_STATUS_STYLE[f.status] ?? 'text-neutral-400'}`}>{f.status}</span>
                  </div>
                  <div className="mt-0.5 opacity-90">{f.summary}</div>
                </div>
              ))}
            </div>
          )}
        </SectionBlock>
      )}
    </div>
  )
}

// ─── Sub-components ───────────────────────────────────────────────

function SectionBlock({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider mb-2">
        {title} {count > 0 && <span className="text-neutral-500">({count})</span>}
      </h3>
      {children}
    </div>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="text-sm text-neutral-600 py-2">{children}</div>
}

function ReflectionRow({ reflection }: { reflection: ReflectionEntry }) {
  const [expanded, setExpanded] = useState(false)
  const preview = reflection.content.split('\n').find(l => l.trim().startsWith('-'))?.trim() ?? reflection.content.slice(0, 80)

  return (
    <div className="border border-neutral-800 rounded mb-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-neutral-800/50 text-left"
      >
        <span className="text-neutral-500">{expanded ? '▾' : '▸'}</span>
        <span className="font-medium text-neutral-300">{reflection.change}</span>
        {!expanded && <span className="text-neutral-500 truncate flex-1">{preview}</span>}
      </button>
      {expanded && (
        <div className="px-3 pb-2 max-h-64 overflow-auto">
          <pre className="text-sm text-neutral-400 whitespace-pre-wrap leading-relaxed">{reflection.content}</pre>
        </div>
      )}
    </div>
  )
}

function ReviewFindings({ entries }: { entries: ReviewFindingEntry[] }) {
  // Flatten issues across entries, deduplicate
  const seen = new Set<string>()
  const issues: (ReviewFindingEntry['issues'][0] & { change: string; attempt: number })[] = []
  for (const entry of entries) {
    for (const issue of entry.issues) {
      const key = `${entry.change}:${issue.summary.slice(0, 60)}`
      if (!seen.has(key)) {
        seen.add(key)
        issues.push({ ...issue, change: entry.change, attempt: entry.attempt })
      }
    }
  }

  // Sort: CRITICAL first, then HIGH, then MEDIUM
  const sevOrder: Record<string, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2 }
  issues.sort((a, b) => (sevOrder[a.severity] ?? 3) - (sevOrder[b.severity] ?? 3))

  return (
    <div className="space-y-1">
      {issues.map((issue, i) => (
        <FindingRow key={i} issue={issue} />
      ))}
    </div>
  )
}

function FindingRow({ issue }: { issue: { severity: string; summary: string; file?: string; line?: string; fix?: string; change: string; attempt: number } }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="border border-neutral-800 rounded">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-neutral-800/50 text-left"
      >
        <span className="text-neutral-500">{expanded ? '▾' : '▸'}</span>
        <span className={`px-1.5 py-0.5 rounded text-xs border ${SEV_STYLE[issue.severity] ?? 'bg-neutral-800 text-neutral-400 border-neutral-700'}`}>
          {issue.severity}
        </span>
        <span className="text-neutral-300 truncate flex-1">{issue.summary}</span>
        <span className="text-neutral-600 shrink-0">{issue.change}</span>
      </button>
      {expanded && (
        <div className="px-3 pb-2 text-sm space-y-1">
          {issue.file && (
            <div className="text-neutral-500">
              File: <span className="text-neutral-400">{issue.file}</span>
              {issue.line && <span> L{issue.line}</span>}
            </div>
          )}
          {issue.fix && (
            <div className="text-neutral-500">
              Fix: <span className="text-neutral-400">{issue.fix}</span>
            </div>
          )}
          <div className="text-neutral-600">Attempt {issue.attempt}</div>
        </div>
      )}
    </div>
  )
}

function GatePerformance({ stats, retry }: { stats: Record<string, GateStatEntry>; retry: { total_retries: number; total_gate_ms: number; retry_pct: number; most_retried_gate: string; most_retried_change: string } }) {
  const [showBreakdown, setShowBreakdown] = useState(false)
  const gates = Object.entries(stats)

  return (
    <div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-neutral-500 text-left">
            <th className="pb-1 font-medium">Gate</th>
            <th className="pb-1 font-medium">Pass Rate</th>
            <th className="pb-1 font-medium">Avg Time</th>
            <th className="pb-1 font-medium">Fails</th>
          </tr>
        </thead>
        <tbody>
          {gates.map(([name, s]) => {
            const pct = Math.round(s.pass_rate * 100)
            const barColor = pct >= 90 ? 'bg-green-600' : pct >= 70 ? 'bg-yellow-600' : 'bg-red-600'
            return (
              <tr key={name} className="border-t border-neutral-800/50">
                <td className="py-1 text-neutral-300 font-medium">{name}</td>
                <td className="py-1">
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-neutral-800 rounded overflow-hidden">
                      <div className={`h-full ${barColor} rounded`} style={{ width: `${pct}%` }} />
                    </div>
                    <span className="text-neutral-400">{pct}%</span>
                    <span className="text-neutral-600">({s.pass}/{s.pass + s.fail})</span>
                  </div>
                </td>
                <td className="py-1 text-neutral-500">{formatMs(s.avg_ms)}</td>
                <td className="py-1 text-neutral-500">{s.fail}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      {retry.total_retries > 0 && (
        <div className="mt-2 text-sm text-neutral-500">
          Total gate time: {formatMs(retry.total_gate_ms)}
          {' · '}{retry.total_retries} retries ({retry.retry_pct}% of changes)
          {retry.most_retried_gate && <span> · Most retried: {retry.most_retried_gate}</span>}
        </div>
      )}

      {gates.length > 0 && (
        <button
          onClick={() => setShowBreakdown(!showBreakdown)}
          className="mt-1 text-sm text-neutral-600 hover:text-neutral-400"
        >
          {showBreakdown ? '▾ Hide' : '▸ Per change type breakdown'}
        </button>
      )}
    </div>
  )
}
