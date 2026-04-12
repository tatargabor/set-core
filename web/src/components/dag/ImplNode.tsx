import { useState } from 'react'
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

export default function ImplNode({ data, selected }: Props) {
  const [hovered, setHovered] = useState(false)
  const expanded = hovered
  const isRunning = data.result === 'running'

  return (
    <div
      className={`relative rounded-md border bg-neutral-900/80 border-violet-500/40 transition-all duration-150 ${
        expanded ? 'w-[260px] min-h-[150px] p-2.5' : 'w-[150px] h-[80px] px-2 py-1.5'
      } ${selected ? 'ring-2 ring-violet-500/60' : ''}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
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
    </div>
  )
}
