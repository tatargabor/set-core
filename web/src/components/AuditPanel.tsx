import { useState } from 'react'
import type { AuditResult } from '../lib/api'

interface Props {
  results: AuditResult[]
}

const severityColor = {
  critical: { bg: 'bg-red-900/40', text: 'text-red-400', chip: 'bg-red-900 text-red-300' },
  minor: { bg: 'bg-yellow-900/30', text: 'text-yellow-400', chip: 'bg-yellow-900 text-yellow-300' },
}

function Badge({ result }: { result: AuditResult }) {
  if (result.audit_result === 'clean') {
    return <span className="px-2 py-0.5 rounded text-sm font-semibold bg-green-900/50 text-green-400">Clean</span>
  }
  if (result.audit_result === 'parse_error') {
    return <span className="px-2 py-0.5 rounded text-sm font-semibold bg-yellow-900/50 text-yellow-400">Parse Error</span>
  }
  const gapCount = result.gaps?.length ?? 0
  const critCount = result.gaps?.filter(g => g.severity === 'critical').length ?? 0
  return (
    <span className="px-2 py-0.5 rounded text-sm font-semibold bg-red-900/50 text-red-400">
      {gapCount} gap{gapCount !== 1 ? 's' : ''}{critCount > 0 ? ` (${critCount} critical)` : ''}
    </span>
  )
}

function CycleEntry({ result, defaultOpen }: { result: AuditResult; defaultOpen: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  const durationS = result.duration_ms ? Math.round(result.duration_ms / 1000) : '?'

  return (
    <div className="border border-neutral-800 rounded mb-1">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-neutral-800/50"
      >
        <span className="text-neutral-500">{open ? '▾' : '▸'}</span>
        <span className="text-neutral-300">Cycle {result.cycle}</span>
        <Badge result={result} />
        <span className="text-neutral-600 ml-auto">{result.model} | {durationS}s</span>
      </button>
      {open && (
        <div className="px-3 pb-2">
          {result.summary && (
            <p className="text-sm text-neutral-400 italic mb-1">{result.summary}</p>
          )}
          {result.audit_result === 'clean' && (
            <p className="text-sm text-green-400 font-semibold">All spec sections covered</p>
          )}
          {result.audit_result === 'parse_error' && (
            <p className="text-sm text-yellow-400">Audit output could not be parsed — see debug log</p>
          )}
          {result.audit_result === 'gaps_found' && result.gaps && result.gaps.length > 0 && (
            <table className="w-full text-sm border-collapse mt-1">
              <thead>
                <tr className="text-neutral-500 border-b border-neutral-800">
                  <th className="text-left py-1 pr-2">ID</th>
                  <th className="text-left py-1 pr-2">Severity</th>
                  <th className="text-left py-1 pr-2">Description</th>
                  <th className="text-left py-1 pr-2">Spec Ref</th>
                  <th className="text-left py-1">Suggested Scope</th>
                </tr>
              </thead>
              <tbody>
                {result.gaps.map((gap) => {
                  const sev = severityColor[gap.severity] ?? severityColor.minor
                  return (
                    <tr key={gap.id} className={`${sev.bg} border-b border-neutral-800/50`}>
                      <td className="py-1 pr-2 text-neutral-300">{gap.id}</td>
                      <td className="py-1 pr-2">
                        <span className={`px-1.5 py-0.5 rounded text-sm font-medium ${sev.chip}`}>
                          {gap.severity}
                        </span>
                      </td>
                      <td className={`py-1 pr-2 ${sev.text}`}>{gap.description}</td>
                      <td className="py-1 pr-2 text-neutral-500">{gap.spec_reference ?? '-'}</td>
                      <td className="py-1 text-neutral-400">{gap.suggested_scope ?? '-'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export default function AuditPanel({ results }: Props) {
  if (!results || results.length === 0) return null

  return (
    <div className="px-4 py-2">
      {results.map((r, i) => (
        <CycleEntry key={r.cycle ?? i} result={r} defaultOpen={i === results.length - 1} />
      ))}
    </div>
  )
}
