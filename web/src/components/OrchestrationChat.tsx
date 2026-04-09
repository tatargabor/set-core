import { useState, useCallback, useRef, useEffect } from 'react'
import { useChatWebSocket, type ChatEvent } from '../hooks/useChatWebSocket'
import { useSonioxAvailable } from '../hooks/useSonioxAvailable'
import VoiceInput from './VoiceInput'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  toolBlocks?: ToolBlock[]
  timestamp: number
  cost_usd?: number
  duration_ms?: number
}

interface ToolBlock {
  id: string
  tool: string
  input: string
  output?: string
  collapsed: boolean
}

type AgentStatus = 'idle' | 'thinking' | 'responding' | 'stopped'

interface OrchState {
  status: string
  total: number
  done: number
  by_status: Record<string, number>
}

interface Props {
  project: string
}

export default function OrchestrationChat({ project }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [orchState, setOrchState] = useState<OrchState | null>(null)
  const [agentStatus, setAgentStatus] = useState<AgentStatus>('idle')
  const [autoScroll, setAutoScroll] = useState(true)

  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const pendingTextRef = useRef('')
  const pendingToolsRef = useRef<ToolBlock[]>([])
  const msgIdRef = useRef(0)

  const nextId = () => String(++msgIdRef.current)

  const onEvent = useCallback((event: ChatEvent) => {
    switch (event.type) {
      case 'history_replay': {
        // Replay server-side history on connect/reconnect
        const msgs = event.messages ?? []
        setMessages(msgs.map((m: any, i: number) => ({
          id: 'hist-' + i,
          role: m.role === 'assistant' ? 'assistant' : m.role === 'user' ? 'user' : 'system',
          content: m.content || '',
          toolBlocks: (m.tool_blocks ?? []).map((t: any, j: number) => ({
            id: `hist-tool-${i}-${j}`,
            tool: t.tool || 'unknown',
            input: t.input || '',
            collapsed: true,
          })),
          timestamp: m.timestamp || Date.now(),
          cost_usd: m.cost_usd,
          duration_ms: m.duration_ms,
        })))
        msgIdRef.current = msgs.length
        pendingTextRef.current = ''
        pendingToolsRef.current = []
        if (event.status === 'running') {
          setAgentStatus('thinking')
        } else {
          setAgentStatus('idle')
        }
        break
      }

      case 'session_cleared':
        setMessages([])
        setAgentStatus('idle')
        pendingTextRef.current = ''
        pendingToolsRef.current = []
        msgIdRef.current = 0
        break

      case 'state_update':
        setOrchState({
          status: event.status ?? 'unknown',
          total: (event as any).total ?? 0,
          done: (event as any).done ?? 0,
          by_status: (event as any).by_status ?? {},
        })
        break

      case 'status':
        if (event.status === 'thinking') {
          setAgentStatus('thinking')
          pendingTextRef.current = ''
          pendingToolsRef.current = []
        } else if (event.status === 'idle') {
          setAgentStatus('idle')
        } else if (event.status === 'stopped') {
          setAgentStatus('stopped')
        } else {
          setAgentStatus(event.status as AgentStatus)
        }
        break

      case 'assistant_text':
        setAgentStatus('responding')
        pendingTextRef.current += event.content ?? ''
        // Update or create the current assistant message
        setMessages(prev => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant' && last.id.startsWith('stream-')) {
            return [
              ...prev.slice(0, -1),
              { ...last, content: pendingTextRef.current, toolBlocks: [...pendingToolsRef.current] },
            ]
          }
          return [
            ...prev,
            {
              id: 'stream-' + nextId(),
              role: 'assistant',
              content: pendingTextRef.current,
              toolBlocks: [...pendingToolsRef.current],
              timestamp: Date.now(),
            },
          ]
        })
        break

      case 'tool_use':
        pendingToolsRef.current.push({
          id: event.tool_use_id ?? nextId(),
          tool: event.tool ?? 'unknown',
          input: event.input ?? '',
          collapsed: true,
        })
        setMessages(prev => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant' && last.id.startsWith('stream-')) {
            return [
              ...prev.slice(0, -1),
              { ...last, toolBlocks: [...pendingToolsRef.current] },
            ]
          }
          return prev
        })
        setAgentStatus('thinking')
        break

      case 'tool_result':
        if (event.tool_use_id) {
          const tool = pendingToolsRef.current.find(t => t.id === event.tool_use_id)
          if (tool) tool.output = event.output
          setMessages(prev => {
            const last = prev[prev.length - 1]
            if (last?.role === 'assistant' && last.id.startsWith('stream-')) {
              return [
                ...prev.slice(0, -1),
                { ...last, toolBlocks: [...pendingToolsRef.current] },
              ]
            }
            return prev
          })
        }
        break

      case 'assistant_done':
        setAgentStatus('idle')
        // Finalize the stream message ID
        setMessages(prev => {
          const last = prev[prev.length - 1]
          if (last?.role === 'assistant' && last.id.startsWith('stream-')) {
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                id: 'done-' + nextId(),
                cost_usd: event.cost_usd,
                duration_ms: event.duration_ms,
              },
            ]
          }
          return prev
        })
        pendingTextRef.current = ''
        pendingToolsRef.current = []
        break

      case 'error':
        setMessages(prev => [
          ...prev,
          {
            id: nextId(),
            role: 'system',
            content: event.message ?? 'Unknown error',
            timestamp: Date.now(),
          },
        ])
        setAgentStatus('idle')
        break
    }
  }, [])

  const { connected, sendMessage, startSession, newSession } = useChatWebSocket({ project, onEvent })
  const { hasKey: hasSonioxKey, micSupported } = useSonioxAvailable()

  // Splash state: true when no chat history AND user hasn't initiated voice entry yet
  const [voiceEntryMode, setVoiceEntryMode] = useState(false)

  // Auto-scroll
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, autoScroll])

  const handleScroll = () => {
    if (!scrollRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
    setAutoScroll(scrollHeight - scrollTop - clientHeight < 50)
  }

  const handleSend = () => {
    const text = input.trim()
    if (!text || !isInputEnabled) return

    setMessages(prev => [
      ...prev,
      { id: nextId(), role: 'user', content: text, timestamp: Date.now() },
    ])
    sendMessage(text)
    setInput('')
    setAutoScroll(true)

    // Refocus input
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewSession = () => {
    if (!connected) return
    setMessages([])
    setAgentStatus('idle')
    pendingTextRef.current = ''
    pendingToolsRef.current = []
    msgIdRef.current = 0
    newSession()
  }

  const toggleToolBlock = (msgId: string, toolId: string) => {
    setMessages(prev =>
      prev.map(m =>
        m.id === msgId
          ? {
              ...m,
              toolBlocks: m.toolBlocks?.map(t =>
                t.id === toolId ? { ...t, collapsed: !t.collapsed } : t
              ),
            }
          : m
      )
    )
  }

  const isProcessing = agentStatus === 'thinking' || agentStatus === 'responding'
  const isInputEnabled = connected && !isProcessing

  // Splash shows when no messages and agent is idle. After the server starts
  // streaming, agentStatus flips to thinking/responding and splash hides. After
  // New Session (messages cleared + status idle), splash reappears.
  const showSplash = messages.length === 0 && agentStatus === 'idle' && !voiceEntryMode

  const handleDiscussClick = () => {
    if (!connected || isProcessing) return
    startSession()
  }

  const handleVoiceEntryClick = () => {
    if (!connected || isProcessing) return
    setVoiceEntryMode(true)
  }

  const handleVoiceTranscript = (text: string) => {
    const trimmed = text.trim()
    setVoiceEntryMode(false)
    if (!trimmed) return
    setMessages(prev => [
      ...prev,
      { id: nextId(), role: 'user', content: trimmed, timestamp: Date.now() },
    ])
    sendMessage(trimmed)
    setAutoScroll(true)
  }

  return (
    <div className="flex flex-col h-full max-h-[100dvh] bg-neutral-950 overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between px-3 py-2 border-b border-neutral-800">
        <div className="flex items-center gap-2">
          <span className="text-sm text-neutral-300 font-medium">Agent Chat</span>
          {/* Connection indicator */}
          <span
            className={connected ? 'text-green-500' : 'text-red-500'}
            title={connected ? 'Connected' : 'Disconnected'}
          >{connected ? '\u25CF' : '\u25CB'}</span>
          {/* Live orchestration state */}
          {orchState && orchState.total > 0 && (
            <span className="text-sm text-neutral-500" title={Object.entries(orchState.by_status).map(([k, v]) => `${v} ${k}`).join(', ')}>
              {orchState.done}/{orchState.total}
            </span>
          )}
          {/* Agent status */}
          {agentStatus === 'thinking' && (
            <span className="text-sm text-yellow-400 animate-pulse">Thinking...</span>
          )}
          {agentStatus === 'responding' && (
            <span className="text-sm text-blue-400 animate-pulse">Responding...</span>
          )}
        </div>
        <button
          onClick={handleNewSession}
          disabled={!connected || isProcessing}
          className="px-2 py-1 min-h-[44px] md:min-h-0 text-sm text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          New Session
        </button>
      </div>

      {/* Splash screen — big DISCUSS WITH AGENT button, optional voice entry */}
      {showSplash && (
        <div className="flex-1 flex flex-col items-center justify-center gap-6 px-6 py-8 min-h-0">
          <button
            onClick={handleDiscussClick}
            disabled={!connected || isProcessing}
            className="px-8 py-6 text-xl md:text-2xl font-semibold tracking-wide bg-blue-600 hover:bg-blue-500 active:bg-blue-700 disabled:bg-neutral-700 disabled:text-neutral-500 disabled:cursor-not-allowed text-white rounded-2xl shadow-lg transition-colors min-h-[88px] min-w-[280px]"
          >
            DISCUSS WITH AGENT
          </button>
          {hasSonioxKey && micSupported && (
            <button
              onClick={handleVoiceEntryClick}
              disabled={!connected || isProcessing}
              title="Start with voice input"
              className="flex items-center justify-center gap-2 px-5 py-3 min-h-[56px] min-w-[200px] bg-neutral-800 hover:bg-neutral-700 active:bg-neutral-900 disabled:opacity-50 disabled:cursor-not-allowed text-neutral-200 rounded-xl border border-neutral-700 transition-colors"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
                <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
                <line x1="12" y1="19" x2="12" y2="23" />
                <line x1="8" y1="23" x2="16" y2="23" />
              </svg>
              <span className="text-sm font-medium">Speak to agent</span>
            </button>
          )}
          <p className="text-xs text-neutral-600 text-center max-w-xs">
            No agent subprocess is running. Click above to start a conversation.
          </p>
        </div>
      )}

      {/* Voice entry mode — show recorder in the center while capturing first utterance */}
      {voiceEntryMode && (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 py-8 min-h-0">
          <div className="text-neutral-300 text-sm">Listening… speak your message</div>
          <VoiceInput
            onTranscript={handleVoiceTranscript}
            onPartial={() => {}}
            autoStart
          />
          <button
            onClick={() => setVoiceEntryMode(false)}
            className="text-xs text-neutral-500 hover:text-neutral-300 underline"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Messages (hidden while splash or voice entry is active) */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className={`flex-1 overflow-auto overflow-x-hidden px-3 py-2 space-y-3 min-h-0 ${showSplash || voiceEntryMode ? 'hidden' : ''}`}
      >
        {messages.length === 0 && !showSplash && !voiceEntryMode && (
          <div className="flex items-center justify-center h-full text-neutral-600 text-sm">
            Send a message to start a conversation with the agent
          </div>
        )}

        {messages.map(msg => (
          <div
            key={msg.id}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] md:max-w-[70%] rounded-lg px-3 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-blue-600/30 text-neutral-200'
                  : msg.role === 'system'
                  ? 'bg-red-900/30 text-red-300 border border-red-800/50'
                  : 'bg-neutral-800/50 text-neutral-300'
              }`}
            >
              {/* Message text */}
              <div className="whitespace-pre-wrap break-words overflow-hidden">{msg.content}</div>

              {/* Tool blocks */}
              {msg.toolBlocks?.map(tool => (
                <div key={tool.id} className="mt-2 border border-neutral-700 rounded overflow-hidden">
                  <button
                    onClick={() => toggleToolBlock(msg.id, tool.id)}
                    className="w-full flex items-center gap-2 px-2 py-1 text-sm bg-neutral-800/80 hover:bg-neutral-700/80 transition-colors text-left"
                  >
                    <span className={`transition-transform ${tool.collapsed ? '' : 'rotate-90'}`}>
                      ▶
                    </span>
                    <span className="text-cyan-400">{tool.tool}</span>
                    <span className="text-neutral-500 truncate flex-1">
                      {tool.input.slice(0, 60)}
                    </span>
                    {tool.output !== undefined && (
                      <span className="text-green-500 text-sm">done</span>
                    )}
                  </button>
                  {!tool.collapsed && (
                    <div className="px-2 py-1 text-sm bg-neutral-900/50 max-h-40 overflow-auto">
                      <div className="text-neutral-400 mb-1">Input:</div>
                      <pre className="text-neutral-300 whitespace-pre-wrap break-all">{tool.input}</pre>
                      {tool.output !== undefined && (
                        <>
                          <div className="text-neutral-400 mt-2 mb-1">Output:</div>
                          <pre className="text-neutral-300 whitespace-pre-wrap">{tool.output}</pre>
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}

              {/* Cost info */}
              {msg.cost_usd !== undefined && (
                <div className="mt-1 text-sm text-neutral-600">
                  ${msg.cost_usd.toFixed(4)} · {((msg.duration_ms ?? 0) / 1000).toFixed(1)}s
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Jump to bottom */}
        {!autoScroll && (
          <button
            onClick={() => {
              setAutoScroll(true)
              scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
            }}
            className="sticky bottom-2 ml-auto mr-2 px-3 py-1 bg-neutral-800 text-neutral-300 text-sm rounded-full shadow-lg hover:bg-neutral-700 transition-colors z-10"
          >
            Jump to bottom
          </button>
        )}
      </div>

      {/* Input area — hidden while splash or voice entry mode is active */}
      <div className={`flex-shrink-0 border-t border-neutral-800 p-2 ${showSplash || voiceEntryMode ? 'hidden' : ''}`}>
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              !connected
                ? 'Connecting...'
                : isProcessing
                ? 'Agent is processing...'
                : 'Type a message or use voice input...'
            }
            disabled={!isInputEnabled}
            rows={1}
            className="flex-1 bg-neutral-900 text-neutral-200 text-base md:text-sm rounded-lg px-3 py-2 min-h-[44px] max-h-32 resize-none border border-neutral-700 focus:border-blue-500 focus:outline-none disabled:opacity-50 placeholder-neutral-600"
            onInput={e => {
              const target = e.target as HTMLTextAreaElement
              target.style.height = 'auto'
              target.style.height = Math.min(target.scrollHeight, 128) + 'px'
            }}
          />

          <VoiceInput
            onTranscript={(text) => setInput(prev => prev ? prev + ' ' + text : text)}
            onPartial={() => {}}
            disabled={!isInputEnabled}
          />

          <button
            onClick={handleSend}
            disabled={!isInputEnabled || !input.trim()}
            className="px-3 min-h-[44px] bg-blue-600 hover:bg-blue-500 disabled:bg-neutral-700 disabled:text-neutral-500 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
