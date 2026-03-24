import { useState, useEffect, useRef } from 'react'
import { getIssues, getIssueGroups, getIssueStats, type Issue, type IssueGroup, type IssueStats } from '../lib/api'

export function useIssueData(project: string | null) {
  const [issues, setIssues] = useState<Issue[]>([])
  const [groups, setGroups] = useState<IssueGroup[]>([])
  const [stats, setStats] = useState<IssueStats>({ by_state: {}, by_severity: {}, total_open: 0, total_resolved: 0, nearest_timeout: null })
  const [loading, setLoading] = useState(true)
  const jsonRef = useRef('')

  useEffect(() => {
    if (!project) return
    const poll = () => {
      Promise.all([
        getIssues(project).catch(() => [] as Issue[]),
        getIssueGroups(project).catch(() => [] as IssueGroup[]),
        getIssueStats(project).catch(() => stats),
      ]).then(([iss, grp, st]) => {
        const json = JSON.stringify({ iss, grp, st })
        if (json !== jsonRef.current) {
          jsonRef.current = json
          setIssues(iss)
          setGroups(grp)
          setStats(st)
        }
        setLoading(false)
      })
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [project])

  return { issues, groups, stats, loading }
}
