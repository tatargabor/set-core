import { Handle, Position, type NodeProps } from '@xyflow/react'
import type { AttemptNode, GateResult } from '../../lib/dag/types'
import { displayModel } from '../../lib/formatModel'

type Props = NodeProps & { data: AttemptNode }

const RESULT_ICON: Record<string, string> = {
  pass: '✓',
  fail: '✗',
  warn: '⚠',
  skip: '–',
  running: '●',
}

const RESULT_TEXT: Record<string, string> = {
  pass: 'text-green-400',
  fail: 'text-red-400',
  warn: 'text-amber-400',
  skip: 'text-neutral-500',
  running: 'text-blue-400',
}

const RESULT_BORDER: Record<string, string> = {
  pass: 'border-green-500/40',
  fail: 'border-red-500/50',
  warn: 'border-amber-500/40',
  skip: 'border-neutral-700',
  running: 'border-blue-500/50',
}

function iconFor(result: GateResult): string {
  if (!result) return '○'
  return RESULT_ICON[result] ?? '○'
}

function colorFor(result: GateResult): string {
  if (!result) return 'text-neutral-600'
  return RESULT_TEXT[result] ?? 'text-neutral-600'
}

function borderFor(result: GateResult): string {
  if (!result) return 'border-neutral-700'
  return RESULT_BORDER[result] ?? 'border-neutral-700'
}

function formatMs(ms: number | null): string {
  if (ms == null) return ''
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
    return ''
  }
}

function formatTokens(n?: number): string {
  if (!n) return ''
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

export default function GateNode({ data, selected }: Props) {
  // Node is fixed-size. Click/selection just adds a blue ring; all the
  // drill-down info (verdict source, downgrades, issue refs, captured
  // output) lives in DagDetailPanel under the canvas. An earlier version
  // grew the node on hover to show those fields inline, but that caused
  // the DAG to visually shift on any mouse movement and duplicated the
  // detail panel.
  const icon = iconFor(data.result)
  const color = colorFor(data.result)
  const border = borderFor(data.result)
  const isRunning = data.result === 'running'
  const hasDowngrade =
    (data.downgrades && data.downgrades.length > 0) || data.verdictSource === 'classifier_downgrade'
  const showRunBadge = data.runIndexForKind > 1

  const hasTokens = (data.inputTokens ?? 0) + (data.outputTokens ?? 0) > 0
  const model = displayModel(data.model)

  return (
    <div
      className={`relative rounded-md border bg-neutral-900/80 w-[150px] h-[100px] px-2 py-1.5 ${border} ${
        selected ? 'ring-2 ring-blue-500/60' : ''
      }`}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#404040' }} />
      <Handle type="source" position={Position.Right} style={{ background: '#404040' }} />
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        style={{ background: '#404040' }}
      />
      <div className="flex items-center gap-1.5">
        <span className={`text-sm font-medium ${color} ${isRunning ? 'animate-pulse' : ''}`}>
          {icon}
        </span>
        <span className="text-xs font-medium text-neutral-200 capitalize flex-1 truncate">
          {data.kind.replace('_', ' ')}
        </span>
        {showRunBadge && (
          <span className="text-[10px] text-neutral-400 bg-neutral-800 px-1 rounded">
            ⟳{data.runIndexForKind}
          </span>
        )}
        {hasDowngrade && <span className="text-[11px] text-amber-400">⚖</span>}
      </div>
      <div className="mt-0.5 text-[11px] text-neutral-500">
        {formatMs(data.ms)}
      </div>
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
