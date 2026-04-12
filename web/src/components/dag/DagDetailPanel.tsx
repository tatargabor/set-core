import { useEffect } from 'react'
import type { AttemptNode } from '../../lib/dag/types'

interface Props {
  node: AttemptNode | null
  onClose: () => void
}

function formatMs(ms: number | null): string {
  if (ms == null) return '–'
  if (ms < 1000) return `${ms}ms`
  const secs = ms / 1000
  if (secs < 60) return `${secs.toFixed(1)}s`
  const mins = Math.floor(secs / 60)
  const rem = Math.floor(secs % 60)
  return `${mins}m${rem > 0 ? ` ${rem}s` : ''}`
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ts
  }
}

export default function DagDetailPanel({ node, onClose }: Props) {
  useEffect(() => {
    if (!node) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [node, onClose])

  if (!node) {
    return (
      <div className="border-t border-neutral-800 bg-neutral-900/70 p-3 text-xs text-neutral-600">
        Click a gate node to inspect its run.
      </div>
    )
  }

  return (
    <div className="border-t border-neutral-800 bg-neutral-900/70 p-3 text-xs text-neutral-300">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold capitalize">
            {node.kind.replace('_', ' ')}
          </span>
          <span className="text-neutral-500">
            attempt <span className="text-neutral-300">#{node.attempt}</span>
          </span>
          {node.runIndexForKind > 1 && (
            <span className="text-neutral-500">
              run <span className="text-neutral-300">#{node.runIndexForKind}</span>
            </span>
          )}
          <span className="text-neutral-500">
            started <span className="text-neutral-300">{formatTime(node.startedAt)}</span>
          </span>
          <span className="text-neutral-500">
            duration <span className="text-neutral-300">{formatMs(node.ms)}</span>
          </span>
          {node.verdictSource && (
            <span className="text-neutral-500">
              source <span className="text-neutral-300">{node.verdictSource}</span>
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-neutral-500 hover:text-neutral-300 text-sm"
          aria-label="Close detail panel"
        >
          ×
        </button>
      </div>
      {node.downgrades && node.downgrades.length > 0 && (
        <div className="mb-2 border border-amber-700/40 bg-amber-900/20 rounded p-2">
          <div className="text-amber-400 font-medium mb-1">Classifier downgrades</div>
          <table className="w-full text-[11px]">
            <tbody>
              {node.downgrades.map((d, i) => (
                <tr key={i} className="border-t border-amber-800/30">
                  <td className="py-0.5 pr-2 text-neutral-400">{d.from}</td>
                  <td className="py-0.5 pr-2">→</td>
                  <td className="py-0.5 pr-2 text-neutral-400">{d.to}</td>
                  <td className="py-0.5 text-neutral-500">{d.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {node.issueRefs && node.issueRefs.length > 0 && (
        <div className="mb-2 text-neutral-500">
          issues:{' '}
          {node.issueRefs.map((id) => (
            <span key={id} className="text-blue-400 mx-1">
              {id}
            </span>
          ))}
        </div>
      )}
      {node.output ? (
        <pre className="max-h-64 overflow-auto bg-neutral-950/60 border border-neutral-800 rounded p-2 text-[11px] text-neutral-400 whitespace-pre-wrap">
          {node.output}
        </pre>
      ) : node.kind === 'impl' ? (
        <div className="text-neutral-500 italic text-[11px] leading-relaxed">
          Implementation phase — the agent's work window for this attempt.
          No gate output is captured here; switch to the Log tab for the
          session log of the ralph iterations that ran during this window.
        </div>
      ) : (
        <div className="text-neutral-500 italic text-[11px] leading-relaxed">
          Gate completed with no captured output. This usually means the gate
          was fast or cached and wrote nothing to stdout. Check the Log tab
          for the full gate command output if needed.
        </div>
      )}
    </div>
  )
}
