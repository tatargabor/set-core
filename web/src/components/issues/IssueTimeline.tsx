import { useRef, useEffect, useState } from 'react'
import type { TimelineEntry } from '../../lib/api'

interface Props {
  entries: TimelineEntry[]
  onSendMessage?: (msg: string) => void
}

export function IssueTimeline({ entries, onSendMessage }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [entries.length, autoScroll])

  const handleScroll = () => {
    if (!scrollRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }

  const handleSend = async () => {
    if (!input.trim() || !onSendMessage || sending) return
    setSending(true)
    try {
      onSendMessage(input.trim())
      setInput('')
    } finally { setSending(false) }
  }

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} onScroll={handleScroll} className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5">
        {entries.length === 0 && (
          <div className="text-sm text-neutral-600 text-center py-4">No events yet</div>
        )}
        {entries.map(entry => (
          <TimelineEntryView key={entry.id} entry={entry} />
        ))}
      </div>

      {/* Chat input */}
      {onSendMessage && (
        <div className="border-t border-neutral-800 p-2 flex gap-2">
          <input
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
            placeholder="Message investigation agent..."
            className="flex-1 bg-neutral-800 border border-neutral-700 rounded px-3 py-1.5 text-sm text-neutral-200 placeholder-neutral-600 outline-none focus:border-neutral-600"
          />
          <button onClick={handleSend} disabled={!input.trim() || sending}
            className="px-3 py-1.5 text-sm rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 disabled:opacity-30 disabled:cursor-not-allowed">
            {sending ? 'Sending…' : 'Send'}
          </button>
        </div>
      )}
    </div>
  )
}

function typeLabel(type: string): string {
  if (type === 'user') return 'you'
  if (type === 'agent') return 'agent'
  return 'sys'
}

function actionColor(action?: string): string {
  if (!action) return 'text-neutral-500'
  if (action === 'transition:resolved' || action === 'deploy_complete') return 'text-green-400'
  if (action === 'transition:failed' || action === 'fix_failed') return 'text-red-400'
  if (action === 'transition:cancelled' || action === 'transition:dismissed') return 'text-neutral-500'
  if (action === 'transition:investigating' || action === 'investigation_spawned') return 'text-yellow-400'
  if (action === 'transition:diagnosed') return 'text-orange-400'
  if (action === 'transition:fixing' || action === 'fix_spawned') return 'text-purple-400'
  if (action === 'transition:verifying') return 'text-indigo-400'
  if (action === 'transition:deploying' || action === 'deploy_started') return 'text-cyan-400'
  if (action === 'transition:awaiting_approval' || action.startsWith('timeout')) return 'text-amber-400'
  if (action === 'transition:muted' || action === 'transition:skipped') return 'text-neutral-500'
  if (action === 'auto_retry') return 'text-yellow-300'
  if (action === 'registered' || action === 'transition:new') return 'text-blue-400'
  return 'text-neutral-500'
}

function TimelineEntryView({ entry }: { entry: TimelineEntry }) {
  const time = new Date(entry.timestamp).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  const icon = entry.icon || '●'
  const label = typeLabel(entry.type)
  const color = entry.type === 'user' ? 'text-blue-300' : entry.type === 'agent' ? 'text-green-300' : actionColor(entry.action)

  return (
    <div className="flex items-start gap-0 text-xs font-mono leading-relaxed">
      <span className="text-neutral-600 shrink-0 w-[60px]">{time}</span>
      <span className={`shrink-0 w-[14px] text-center ${color}`}>{icon}</span>
      <span className="text-neutral-600 shrink-0 w-[46px] text-right pr-2">{label}</span>
      <span className={color}>{entry.content}</span>
    </div>
  )
}
