import { useState, useCallback } from 'react'
import { sendIssueMessage } from '../lib/api'

export interface ChatMessage {
  id: string
  timestamp: string
  role: 'user' | 'agent'
  content: string
}

export function useIssueChat(project: string | null, issueId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [connected] = useState(true) // Simplified — uses REST, not WS for now

  const send = useCallback(async (content: string) => {
    if (!project || !issueId || !content.trim()) return

    const msg: ChatMessage = {
      id: `user-${Date.now()}`,
      timestamp: new Date().toISOString(),
      role: 'user',
      content: content.trim(),
    }
    setMessages(prev => [...prev, msg])

    try {
      await sendIssueMessage(project, issueId, content.trim())
    } catch {
      // Message already shown optimistically
    }
  }, [project, issueId])

  return { messages, send, connected }
}
