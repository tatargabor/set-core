import { useState, useEffect, useMemo } from 'react'
import { getIssue, getIssueAudit, type Issue, type IssueAuditEntry, type TimelineEntry } from '../lib/api'

const AUDIT_ICONS: Record<string, string> = {
  registered: '●', 'transition:investigating': '🔍', 'transition:diagnosed': '◆',
  'transition:awaiting_approval': '⏱', 'transition:fixing': '🔧', 'transition:verifying': '✓',
  'transition:deploying': '🚀', 'transition:resolved': '✓', 'transition:failed': '✗',
  'transition:cancelled': '⊘', 'transition:skipped': '→', 'transition:dismissed': '✕',
  'transition:muted': '🔇', 'transition:new': '●',
  timeout_auto_approved: '⏱', timeout_extended: '⏰', investigation_spawned: '🔍',
  fix_spawned: '🔧', fix_failed: '✗', auto_retry: '↻', duplicate_suppressed: '≡',
  investigation_timeout: '⏱', deploy_started: '🚀', deploy_complete: '✓',
  user_message: '💬', skipped: '→',
}

function formatAuditAction(entry: IssueAuditEntry): string {
  const action = entry.action || ''
  if (action.startsWith('transition:')) {
    const to = action.replace('transition:', '')
    return `${to}${entry.from_state ? ` (from ${entry.from_state})` : ''}`
  }
  if (action === 'user_message') return entry.content as string || 'message'
  if (action === 'timeout_auto_approved') return `auto-approved after ${entry.waited_seconds || '?'}s`
  if (action === 'fix_failed') return `fix failed (retry ${entry.retry_count}/${entry.max_retries})`
  return action.replace(/_/g, ' ')
}

export function useIssueDetail(project: string | null, issueId: string | null) {
  const [issue, setIssue] = useState<Issue | null>(null)
  const [audit, setAudit] = useState<IssueAuditEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!project || !issueId) { setLoading(false); return }
    const poll = () => {
      Promise.all([
        getIssue(project, issueId).catch(() => null),
        getIssueAudit(project, { issue_id: issueId, limit: 100 }).catch(() => []),
      ]).then(([iss, aud]) => {
        if (iss) setIssue(iss)
        setAudit(aud)
        setLoading(false)
      })
    }
    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [project, issueId])

  const timeline = useMemo((): TimelineEntry[] => {
    // Audit entries (newest first from API, reverse to chronological)
    const reversed = [...audit].reverse()
    return reversed.map((a, i) => ({
      id: `audit-${i}`,
      timestamp: a.ts,
      type: (a.action === 'user_message' ? 'user' : 'system') as 'system' | 'user' | 'agent',
      content: formatAuditAction(a),
      action: a.action,
      icon: AUDIT_ICONS[a.action] || '●',
    }))
  }, [audit])

  return { issue, timeline, loading }
}
