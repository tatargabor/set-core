import { useState, useEffect, useRef } from 'react'
import { getAllIssueStats, getManagerStatus, type IssueStats } from '../lib/api'

interface SidebarStats {
  /** Per-project issue stats */
  issueStats: Record<string, IssueStats>
  /** Total open issues across all projects */
  totalOpen: number
  /** Manager service is reachable */
  managerOnline: boolean
}

export function useSidebarStats(): SidebarStats {
  const [issueStats, setIssueStats] = useState<Record<string, IssueStats>>({})
  const [managerOnline, setManagerOnline] = useState(false)
  const jsonRef = useRef('')

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    let fails = 0
    const poll = () => {
      Promise.all([
        getAllIssueStats().catch(() => null),
        getManagerStatus().catch(() => null),
      ]).then(([stats, status]) => {
        if (stats) {
          const json = JSON.stringify(stats)
          if (json !== jsonRef.current) {
            jsonRef.current = json
            setIssueStats(stats)
          }
        }
        const online = status !== null
        setManagerOnline(online)
        fails = online ? 0 : fails + 1
        timer = setTimeout(poll, online ? 5000 : Math.min(5000 * Math.pow(2, fails - 1), 30000))
      })
    }
    poll()
    return () => clearTimeout(timer)
  }, [])

  const totalOpen = Object.values(issueStats).reduce((sum, s) => sum + (s.total_open || 0), 0)

  return { issueStats, totalOpen, managerOnline }
}
