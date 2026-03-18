import { useState, useEffect, useRef, useCallback } from 'react'
import {
  getSentinelEvents,
  getSentinelFindings,
  getSentinelStatus,
  type SentinelEvent,
  type SentinelFindingsData,
  type SentinelStatusData,
} from '../lib/api'

const POLL_INTERVAL = 1000

export interface SentinelData {
  events: SentinelEvent[]
  findings: SentinelFindingsData
  status: SentinelStatusData
  hasSentinel: boolean
}

export function useSentinelData(project: string | null): SentinelData {
  const [events, setEvents] = useState<SentinelEvent[]>([])
  const [findings, setFindings] = useState<SentinelFindingsData>({ findings: [], assessments: [] })
  const [status, setStatus] = useState<SentinelStatusData>({ active: false, is_active: false })
  const lastEpochRef = useRef<number>(0)

  const poll = useCallback(async () => {
    if (!project) return

    try {
      const [newEvents, newFindings, newStatus] = await Promise.all([
        getSentinelEvents(project, lastEpochRef.current || undefined),
        getSentinelFindings(project),
        getSentinelStatus(project),
      ])

      if (newEvents.length > 0) {
        setEvents(prev => {
          const merged = [...prev, ...newEvents]
          // Keep last 500 events
          return merged.length > 500 ? merged.slice(-500) : merged
        })
        lastEpochRef.current = newEvents[newEvents.length - 1].epoch
      }

      setFindings(newFindings)
      setStatus(newStatus)
    } catch {
      // Silently fail — endpoint may not exist yet
    }
  }, [project])

  useEffect(() => {
    if (!project) return
    // Reset on project change
    setEvents([])
    setFindings({ findings: [], assessments: [] })
    setStatus({ active: false, is_active: false })
    lastEpochRef.current = 0

    poll()
    const iv = setInterval(poll, POLL_INTERVAL)
    return () => clearInterval(iv)
  }, [project, poll])

  const hasSentinel = status.active || status.member != null || events.length > 0

  return { events, findings, status, hasSentinel }
}
