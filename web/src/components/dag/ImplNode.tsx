import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { AttemptNode } from '../../lib/dag/types'

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

function shortModel(model?: string): string {
  if (!model) return ''
  const m = model.toLowerCase()
  if (m.includes('opus')) return 'opus'
  if (m.includes('sonnet')) return 'sonnet'
  if (m.includes('haiku')) return 'haiku'
  return model
}

export default function ImplNode({ data, selected }: Props) {
  // Fixed-size node with a ring on selection; see GateNode for the
  // rationale behind dropping the hover-expand.
  const isRunning = data.result === 'running'
  const hasTokens = (data.inputTokens ?? 0) + (data.outputTokens ?? 0) > 0
  const model = shortModel(data.model)

  return (
    <div
      className={`relative rounded-md border bg-neutral-900/80 border-violet-500/40 w-[150px] h-[100px] px-2 py-1.5 ${
        selected ? 'ring-2 ring-violet-500/60' : ''
      }`}
    >
      <Handle type="target" position={Position.Left} id="top" style={{ background: '#404040' }} />
      <Handle type="target" position={Position.Top} id="topRetry" style={{ background: '#404040' }} />
      <Handle type="source" position={Position.Right} style={{ background: '#404040' }} />
      <div className="flex items-center gap-1.5">
        <span className={`text-sm text-violet-300 ${isRunning ? 'animate-pulse' : ''}`}>✎</span>
        <span className="text-xs font-medium text-neutral-200 flex-1 truncate">impl</span>
        <span className="text-[10px] text-neutral-400 bg-neutral-800 px-1 rounded">
          #{data.attempt}
        </span>
      </div>
      <div className="mt-0.5 text-[11px] text-neutral-500">{formatMs(data.ms)}</div>
      <div className="mt-0.5 text-[10px] text-neutral-600 flex items-center gap-1.5">
        <span>#{data.attempt}</span>
        <span className="text-neutral-700">·</span>
        <span>{formatTime(data.startedAt)}</span>
      </div>
      {(model || hasTokens) && (
        <div className="mt-0.5 text-[10px] text-neutral-600 flex items-center gap-1.5">
          {model && <span className="text-neutral-400">{model}</span>}
          {model && hasTokens && <span className="text-neutral-700">·</span>}
          {hasTokens && (
            <span>
              <span className="text-neutral-500">{formatTokens(data.inputTokens)}</span>
              <span className="text-neutral-700">/</span>
              <span className="text-neutral-500">{formatTokens(data.outputTokens)}</span>
            </span>
          )}
        </div>
      )}
    </div>
  )
}
