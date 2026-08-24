import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { AttemptNode } from '../../lib/dag/types'
import { displayModel } from '../../lib/formatModel'

type Props = NodeProps & { data: AttemptNode }

function formatMs(ms: number | null): string {
  if (ms == null) return ''
  if (ms < 1000) return `${ms}ms`
  const secs = ms / 1000
  if (secs < 60) return `${secs.toFixed(0)}s`
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
    return ''
  }
}

function formatTokens(n?: number): string {
  if (!n) return ''
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

export default function ImplNode({ data, selected }: Props) {
  // Fixed-size node with a ring on selection; see GateNode for the
  // rationale behind dropping the hover-expand.
  const isRunning = data.result === 'running'
  const hasTokens = (data.inputTokens ?? 0) + (data.outputTokens ?? 0) > 0
  const model = displayModel(data.model)

  return (
    <div
      className={`relative rounded-md border bg-surface-panel/80 border-violet-500/40 w-[150px] h-[100px] px-2 py-1.5 ${
        selected ? 'ring-2 ring-violet-500/60' : ''
      }`}
    >
      <Handle type="target" position={Position.Left} id="top" style={{ background: '#464b57' }} />
      <Handle type="target" position={Position.Top} id="topRetry" style={{ background: '#464b57' }} />
      <Handle type="source" position={Position.Right} style={{ background: '#464b57' }} />
      <div className="flex items-center gap-1.5">
        <span className={`text-sm text-violet-300 ${isRunning ? 'animate-pulse' : ''}`}>✎</span>
        <span className="text-xs font-medium text-fg-strong flex-1 truncate">impl</span>
        <span className="text-xs text-fg-muted bg-surface-raised px-1 rounded">
          #{data.attempt}
        </span>
      </div>
      <div className="mt-0.5 text-xs text-fg-faint">{formatMs(data.ms)}</div>
      <div className="mt-0.5 text-xs text-fg-ghost flex items-center gap-1.5">
        <span>#{data.attempt}</span>
        <span className="text-fg-dim">·</span>
        <span>{formatTime(data.startedAt)}</span>
      </div>
      {(model || hasTokens) && (
        <div className="mt-0.5 text-xs text-fg-ghost flex items-center gap-1.5">
          {model && <span className="text-fg-muted">{model}</span>}
          {model && hasTokens && <span className="text-fg-dim">·</span>}
          {hasTokens && (
            <span>
              <span className="text-fg-faint">{formatTokens(data.inputTokens)}</span>
              <span className="text-fg-dim">/</span>
              <span className="text-fg-faint">{formatTokens(data.outputTokens)}</span>
            </span>
          )}
        </div>
      )}
    </div>
  )
}
