import { useState } from 'react'
import type { ChangeInfo } from '../lib/api'

interface Props {
  change: ChangeInfo
}

interface GateSection {
  name: string
  label: string
  result?: string
  output?: string
  ms?: number
}

const resultStyle: Record<string, string> = {
  pass: 'text-green-400',
  fail: 'text-red-400',
  critical: 'text-red-500 font-semibold',
  skip: 'text-neutral-500',
}

export default function GateDetail({ change }: Props) {
  const gates: GateSection[] = [
    { name: 'build', label: 'Build', result: change.build_result, output: change.build_output, ms: change.gate_build_ms },
    { name: 'test', label: 'Test', result: change.test_result, output: change.test_output, ms: change.gate_test_ms },
    { name: 'review', label: 'Review', result: change.review_result, output: change.review_output, ms: change.gate_review_ms },
    { name: 'smoke', label: 'Smoke', result: change.smoke_result, output: change.smoke_output, ms: change.gate_verify_ms },
    { name: 'e2e', label: 'E2E', result: change.e2e_result, output: change.e2e_output, ms: change.gate_e2e_ms },
    { name: 'spec_coverage', label: 'Spec Coverage',
      result: change.spec_coverage_result === 'timeout' ? 'skip' : change.spec_coverage_result,
      output: change.spec_coverage_result === 'timeout' ? 'Spec coverage check timed out (non-blocking)' : undefined },
  ].filter(g => g.result)

  // Auto-expand first failing gate, or none
  const firstFail = gates.findIndex(g => g.result === 'fail' || g.result === 'critical')
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    return firstFail >= 0 ? new Set([gates[firstFail].name]) : new Set()
  })

  const toggle = (name: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  if (gates.length === 0) {
    return <div className="px-4 py-2 text-neutral-500 text-sm">No gate results</div>
  }

  return (
    <div className="px-4 py-2 space-y-1">
      {gates.map(g => (
        <div key={g.name} className="border border-neutral-800 rounded">
          <button
            onClick={() => toggle(g.name)}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-neutral-800/50"
          >
            <span className="text-neutral-500">{expanded.has(g.name) ? '▾' : '▸'}</span>
            <span className="font-medium text-neutral-300">{g.label}</span>
            <span className={resultStyle[g.result!] ?? 'text-neutral-400'}>{g.result}</span>
            {g.ms != null && (
              <span className="ml-auto text-neutral-500">{(g.ms / 1000).toFixed(1)}s</span>
            )}
          </button>
          {expanded.has(g.name) && (
            <div className="px-3 pb-2 max-h-64 overflow-auto">
              {g.output ? (
                <pre className="text-sm text-neutral-400 whitespace-pre-wrap leading-relaxed">{g.output}</pre>
              ) : (
                <span className="text-sm text-neutral-600">No output</span>
              )}
            </div>
          )}
        </div>
      ))}
      {change.gate_total_ms != null && (
        <div className="text-sm text-neutral-500 pt-1">
          Total gate time: {(change.gate_total_ms / 1000).toFixed(1)}s
        </div>
      )}
    </div>
  )
}
