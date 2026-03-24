import { useState, useMemo } from 'react'
import type { Issue, IssueGroup } from '../../lib/api'
import { IssueRow } from './IssueRow'
import { ATTENTION_STATES, IN_PROGRESS_STATES, DONE_STATES } from './styles'

interface Props {
  issues: Issue[]
  groups: IssueGroup[]
  selectedId: string | null
  onSelect: (id: string) => void
  showEnv?: boolean
}

export function IssueList({ issues, groups, selectedId, onSelect, showEnv }: Props) {
  const [checked, setChecked] = useState<Set<string>>(new Set())
  const [stateFilter, setStateFilter] = useState<string>('')
  const [severityFilter, setSeverityFilter] = useState<string>('')
  const [doneExpanded, setDoneExpanded] = useState(false)

  const filtered = useMemo(() => {
    return issues.filter(i => {
      if (stateFilter && i.state !== stateFilter) return false
      if (severityFilter && i.severity !== severityFilter) return false
      return true
    })
  }, [issues, stateFilter, severityFilter])

  const attention = filtered.filter(i => (ATTENTION_STATES as string[]).includes(i.state))
  const inProgress = filtered.filter(i => (IN_PROGRESS_STATES as string[]).includes(i.state))
  const done = filtered.filter(i => (DONE_STATES as string[]).includes(i.state))

  const handleCheck = (id: string, isChecked: boolean) => {
    setChecked(prev => {
      const next = new Set(prev)
      isChecked ? next.add(id) : next.delete(id)
      return next
    })
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-2">
        <select value={stateFilter} onChange={e => setStateFilter(e.target.value)}
          className="text-xs bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-neutral-300">
          <option value="">All States</option>
          {['new','investigating','diagnosed','awaiting_approval','fixing','verifying','deploying','resolved','dismissed','muted','failed','skipped','cancelled'].map(s =>
            <option key={s} value={s}>{s}</option>
          )}
        </select>
        <select value={severityFilter} onChange={e => setSeverityFilter(e.target.value)}
          className="text-xs bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-neutral-300">
          <option value="">All Severity</option>
          {['unknown','low','medium','high','critical'].map(s =>
            <option key={s} value={s}>{s}</option>
          )}
        </select>
      </div>

      {/* Needs Attention */}
      {attention.length > 0 && (
        <Section title="Needs Attention" count={attention.length} color="text-amber-400">
          {attention.map(i => (
            <IssueRow key={i.id} issue={i} selected={selectedId === i.id} onSelect={onSelect}
              checked={checked.has(i.id)} onCheck={handleCheck} showEnv={showEnv} />
          ))}
        </Section>
      )}

      {/* In Progress */}
      {inProgress.length > 0 && (
        <Section title="In Progress" count={inProgress.length} color="text-purple-400">
          {inProgress.map(i => (
            <IssueRow key={i.id} issue={i} selected={selectedId === i.id} onSelect={onSelect}
              checked={checked.has(i.id)} onCheck={handleCheck} showEnv={showEnv} />
          ))}
        </Section>
      )}

      {/* Done (collapsed) */}
      {done.length > 0 && (
        <Section title="Done" count={done.length} color="text-neutral-500"
          collapsed={!doneExpanded} onToggle={() => setDoneExpanded(!doneExpanded)}>
          {doneExpanded && done.map(i => (
            <IssueRow key={i.id} issue={i} selected={selectedId === i.id} onSelect={onSelect}
              checked={checked.has(i.id)} onCheck={handleCheck} showEnv={showEnv} />
          ))}
        </Section>
      )}

      {filtered.length === 0 && (
        <div className="text-sm text-neutral-500 py-4 text-center">No issues</div>
      )}

      {/* Bulk actions */}
      {checked.size > 0 && (
        <div className="flex items-center gap-2 px-3 py-2 bg-neutral-800 rounded">
          <span className="text-xs text-neutral-400">{checked.size} selected</span>
          <button className="text-xs px-2 py-1 rounded bg-neutral-700 text-neutral-300 hover:bg-neutral-600">Group Selected</button>
          <button className="text-xs px-2 py-1 rounded bg-neutral-700 text-neutral-300 hover:bg-neutral-600">Dismiss Selected</button>
        </div>
      )}

      {/* Groups */}
      {groups.length > 0 && (
        <div className="border-t border-neutral-800 pt-3 space-y-1">
          <h3 className="text-xs text-neutral-500 uppercase tracking-wider px-3">Groups</h3>
          {groups.map(g => (
            <div key={g.id} className="flex items-center gap-2 px-3 py-1.5 text-sm text-neutral-400">
              <span className="font-mono text-xs text-neutral-500">{g.id}</span>
              <span className="truncate">{g.name}</span>
              <span className="text-xs text-neutral-600">{g.issue_ids.length} issues</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Section({ title, count, color, collapsed, onToggle, children }: {
  title: string; count: number; color: string; collapsed?: boolean; onToggle?: () => void; children: React.ReactNode
}) {
  return (
    <div>
      <button onClick={onToggle} className={`flex items-center gap-2 px-3 py-1 text-xs uppercase tracking-wider font-medium ${color}`}>
        {collapsed != null && <span>{collapsed ? '▶' : '▼'}</span>}
        {title} ({count})
      </button>
      {children}
    </div>
  )
}
