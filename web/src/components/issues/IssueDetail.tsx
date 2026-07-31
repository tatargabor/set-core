import { useState, useEffect, useRef } from 'react'
import type { Issue } from '../../lib/api'
import { getProjectSession } from '../../lib/api'
import { useIssueDetail } from '../../hooks/useIssueDetail'
import { useIssueChat } from '../../hooks/useIssueChat'
import { SeverityBadge } from './SeverityBadge'
import { StateBadge } from './StateBadge'
import { IssueActions } from './IssueActions'
import { IssueTimeline } from './IssueTimeline'

interface Props {
  project: string
  issueId: string
  onClose: () => void
}

type Tab = 'timeline' | 'diagnosis' | 'error' | 'session' | 'related'

export function IssueDetail({ project, issueId, onClose }: Props) {
  const { issue, timeline, loading } = useIssueDetail(project, issueId)
  const { messages, send } = useIssueChat(project, issueId)
  const [tab, setTab] = useState<Tab>('timeline')

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  if (loading || !issue) {
    return (
      <Modal onClose={onClose}>
        <div className="p-6 text-sm text-fg-faint">Loading...</div>
      </Modal>
    )
  }

  // Merge timeline with chat messages
  const chatEntries = messages.map(m => ({
    id: m.id,
    timestamp: m.timestamp,
    type: m.role as 'user' | 'agent',
    content: m.content,
    author: m.role === 'user' ? 'You' : 'Agent',
  }))
  const merged = [...timeline, ...chatEntries].sort((a, b) => a.timestamp.localeCompare(b.timestamp))

  return (
    <Modal onClose={onClose}>
      <div className="flex flex-col h-[80vh]">
        {/* Header */}
        <div className="p-4 border-b border-surface-line space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className=" text-sm text-fg-muted">{issue.id}</span>
              <SeverityBadge severity={issue.severity} />
              <StateBadge state={issue.state} />
            </div>
            <button onClick={onClose} className="text-fg-faint hover:text-fg-normal p-1">✕</button>
          </div>
          <p className="text-sm text-fg-strong">{issue.error_summary}</p>
          <div className="flex items-center gap-2 text-xs text-fg-faint">
            <span>{issue.environment}</span>
            <span>|</span>
            <span>{issue.source}</span>
            {issue.group_id && <><span>|</span><span>{issue.group_id}</span></>}
            {issue.occurrence_count > 1 && <><span>|</span><span>seen {issue.occurrence_count}x</span></>}
          </div>

          {/* Actions */}
          <IssueActions issue={issue} project={project} onAction={() => {}} />
        </div>

        {/* Tabs */}
        <div className="flex border-b border-surface-line">
          {(['timeline', 'diagnosis', 'error', 'session', 'related'] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 text-xs font-medium capitalize ${tab === t ? 'text-fg-loud border-b-2 border-blue-400' : 'text-fg-faint hover:text-fg-normal'}`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-hidden">
          {tab === 'timeline' && (
            <IssueTimeline entries={merged} onSendMessage={send} />
          )}
          {tab === 'diagnosis' && <DiagnosisTab issue={issue} />}
          {tab === 'error' && <ErrorTab issue={issue} />}
          {tab === 'session' && <SessionTab issue={issue} project={project} />}
          {tab === 'related' && <RelatedTab issue={issue} />}
        </div>
      </div>
    </Modal>
  )
}

function Modal({ children, onClose }: { onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60" />
      <div
        className="relative w-full max-w-3xl mx-4 bg-surface-page border border-surface-line rounded-xl shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  )
}

function DiagnosisTab({ issue }: { issue: Issue }) {
  const d = issue.diagnosis
  if (!d) {
    return <div className="p-4 text-sm text-fg-faint">No diagnosis yet — investigation pending or not started.</div>
  }
  return (
    <div className="p-4 space-y-4 overflow-y-auto h-full">
      <div>
        <h4 className="text-xs text-fg-faint uppercase tracking-wider mb-1">Root Cause</h4>
        <p className="text-sm text-fg-strong">{d.root_cause}</p>
      </div>
      <div className="flex gap-4 text-xs">
        <span className="text-fg-muted">Impact: <span className="text-fg-strong">{d.impact}</span></span>
        <span className="text-fg-muted">Confidence: <span className="text-fg-strong">{Math.round(d.confidence * 100)}%</span></span>
        <span className="text-fg-muted">Scope: <span className="text-fg-strong">{d.fix_scope}</span></span>
      </div>
      {d.suggested_fix && (
        <div>
          <h4 className="text-xs text-fg-faint uppercase tracking-wider mb-1">Suggested Fix</h4>
          <p className="text-sm text-fg-normal">{d.suggested_fix}</p>
        </div>
      )}
      {d.affected_files.length > 0 && (
        <div>
          <h4 className="text-xs text-fg-faint uppercase tracking-wider mb-1">Affected Files</h4>
          <ul className="text-sm text-fg-muted space-y-0.5">
            {d.affected_files.map((f, i) => <li key={i} className=" text-xs">{f}</li>)}
          </ul>
        </div>
      )}
      {d.tags.length > 0 && (
        <div className="flex gap-1.5">
          {d.tags.map(t => <span key={t} className="px-1.5 py-0.5 text-xs rounded bg-surface-raised text-fg-muted">{t}</span>)}
        </div>
      )}
    </div>
  )
}

function ErrorTab({ issue }: { issue: Issue }) {
  return (
    <div className="p-4 space-y-3 overflow-y-auto h-full">
      <pre className="text-xs text-fg-normal bg-surface-panel rounded p-3 overflow-x-auto whitespace-pre-wrap max-h-96">
        {issue.error_detail || 'No error detail available.'}
      </pre>
      <div className="flex gap-4 text-xs text-fg-faint">
        <span>Occurrences: {issue.occurrence_count}</span>
        <span>First: {new Date(issue.detected_at).toLocaleString()}</span>
        <span>Last: {new Date(issue.updated_at).toLocaleString()}</span>
      </div>
    </div>
  )
}

function SessionTab({ issue, project }: { issue: Issue; project: string }) {
  const [lines, setLines] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const sessionId = issue.investigation_session
  useEffect(() => {
    if (!sessionId) return
    setLoading(true)
    const load = () => {
      getProjectSession(project, sessionId, 500)
        .then(r => setLines(r.lines))
        .catch(() => {})
        .finally(() => setLoading(false))
    }
    load()
    const interval = setInterval(load, 3000)
    return () => clearInterval(interval)
  }, [project, sessionId])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [lines.length])

  if (!sessionId) {
    return <div className="p-4 text-sm text-fg-faint">No investigation session yet.</div>
  }

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto p-4">
      {loading && lines.length === 0 && <div className="text-sm text-fg-faint">Loading session log...</div>}
      <pre className="text-xs text-fg-muted whitespace-pre-wrap leading-relaxed">
        {lines.join('\n')}
      </pre>
    </div>
  )
}

function RelatedTab({ issue }: { issue: Issue }) {
  if (!issue.group_id && !issue.diagnosis?.suggested_group) {
    return <div className="p-4 text-sm text-fg-faint">Not part of a group. No suggestions.</div>
  }
  return (
    <div className="p-4 space-y-3 overflow-y-auto h-full">
      {issue.group_id && (
        <div>
          <h4 className="text-xs text-fg-faint uppercase tracking-wider mb-1">Group: {issue.group_id}</h4>
          <p className="text-sm text-fg-muted">This issue is part of a group. View group in the issue list.</p>
        </div>
      )}
      {!issue.group_id && issue.diagnosis?.suggested_group && (
        <div className="p-3 rounded bg-amber-950/20 border border-amber-800/30">
          <p className="text-sm text-amber-400">Agent suggests grouping: "{issue.diagnosis.suggested_group}"</p>
          <p className="text-xs text-amber-400/70 mt-1">{issue.diagnosis.group_reason}</p>
        </div>
      )}
    </div>
  )
}
