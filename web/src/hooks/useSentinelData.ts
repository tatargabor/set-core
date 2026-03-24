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

  const failsRef = useRef(0)

  const poll = useCallback(async () => {
    if (!project) return false

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
      failsRef.current = 0
      return true
    } catch {
      failsRef.current++
      return false
    }
  }, [project])

  useEffect(() => {
    if (!project) return
    // Reset on project change
    setEvents([])
    setFindings({ findings: [], assessments: [] })
    setStatus({ active: false, is_active: false })
    lastEpochRef.current = 0
    failsRef.current = 0

    let timer: ReturnType<typeof setTimeout>
    let cancelled = false
    const loop = async () => {
      const ok = await poll()
      if (cancelled) return
      const delay = ok ? POLL_INTERVAL : Math.min(POLL_INTERVAL * Math.pow(2, failsRef.current), 30000)
      timer = setTimeout(loop, delay)
    }
    loop()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [project, poll])

  const hasSentinel = status.active || status.member != null || events.length > 0

  return { events, findings, status, hasSentinel }
}
