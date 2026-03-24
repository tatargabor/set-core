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

function TimelineEntryView({ entry }: { entry: TimelineEntry }) {
  const time = new Date(entry.timestamp).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })

  if (entry.type === 'system') {
    return (
      <div className="text-center text-xs text-neutral-600 py-0.5">
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5">
          <span>{entry.icon || '●'}</span>
          <span>{time}</span>
          <span className="text-neutral-500">{entry.content}</span>
        </span>
      </div>
    )
  }

  if (entry.type === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%]">
          <div className="text-xs text-neutral-600 text-right mb-0.5">{time}</div>
          <div className="bg-blue-600/20 text-blue-200 rounded-lg rounded-br-sm px-3 py-2 text-sm">
            {entry.content}
          </div>
        </div>
      </div>
    )
  }

  // agent
  return (
    <div className="flex justify-start">
      <div className="max-w-[80%]">
        <div className="text-xs text-neutral-600 mb-0.5 flex items-center gap-1">
          <span>🤖</span> <span>{time}</span>
        </div>
        <div className="bg-neutral-800 text-neutral-300 rounded-lg rounded-bl-sm px-3 py-2 text-sm">
          {entry.content}
        </div>
      </div>
    </div>
  )
}
