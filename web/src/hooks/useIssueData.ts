import { useState, useEffect, useRef } from 'react'
import { getIssues, getIssueGroups, getIssueStats, getAllIssues, getAllIssueStats, type Issue, type IssueGroup, type IssueStats } from '../lib/api'

export function useIssueData(project: string | null) {
  const [issues, setIssues] = useState<Issue[]>([])
  const [groups, setGroups] = useState<IssueGroup[]>([])
  const [stats, setStats] = useState<IssueStats>({ by_state: {}, by_severity: {}, total_open: 0, total_resolved: 0, nearest_timeout: null })
  const [loading, setLoading] = useState(true)
  const jsonRef = useRef('')

  useEffect(() => {
    const poll = () => {
      const issuesP = project
        ? getIssues(project).catch(() => [] as Issue[])
        : getAllIssues().catch(() => [] as Issue[])
      const groupsP = project
        ? getIssueGroups(project).catch(() => [] as IssueGroup[])
        : Promise.resolve([] as IssueGroup[])
      const statsP = project
        ? getIssueStats(project).catch(() => stats)
        : getAllIssueStats().then(all => {
            // Aggregate cross-project stats
            let total_open = 0, total_resolved = 0
            for (const s of Object.values(all)) {
              total_open += s.total_open || 0
              total_resolved += s.total_resolved || 0
            }
            return { by_state: {}, by_severity: {}, total_open, total_resolved, nearest_timeout: null } as IssueStats
          }).catch(() => stats)

      Promise.all([issuesP, groupsP, statsP]).then(([iss, grp, st]) => {
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
