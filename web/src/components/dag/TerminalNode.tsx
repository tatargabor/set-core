import { Handle, Position, type NodeProps } from '@xyflow/react'

interface TerminalData {
  terminal: 'merged' | 'failed'
  attemptNumber?: number
  totalMs?: number
  reason?: string
}

type Props = NodeProps & { data: TerminalData }

function formatMs(ms: number | undefined): string {
  if (!ms) return ''
  const secs = ms / 1000
  if (secs < 60) return `${secs.toFixed(0)}s`
  const mins = Math.floor(secs / 60)
  const rem = Math.floor(secs % 60)
  return `${mins}m${rem > 0 ? ` ${rem}s` : ''}`
}

export default function TerminalNode({ data }: Props) {
  const merged = data.terminal === 'merged'
  const icon = merged ? '✓' : '✗'
  const label = merged ? 'MERGED' : 'FAILED'
  const baseClasses = merged
    ? 'bg-green-900/60 border-green-500/60 text-green-300'
    : 'bg-red-900/60 border-red-500/60 text-red-300'

  return (
    <div
      className={`relative rounded-lg border-2 px-3 py-2 w-[150px] h-[60px] flex flex-col items-center justify-center ${baseClasses}`}
    >
      <Handle type="target" position={Position.Left} style={{ background: '#404040' }} />
      <div className="flex items-center gap-1.5">
        <span className="text-xl font-bold">{icon}</span>
        <span className="text-sm font-bold tracking-wide">{label}</span>
      </div>
      <div className="text-[10px] opacity-80">
        {merged && data.attemptNumber ? `attempt #${data.attemptNumber}` : null}
        {!merged && data.reason ? data.reason : null}
        {data.totalMs ? ` · ${formatMs(data.totalMs)}` : null}
      </div>
    </div>
  )
}
