import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useIssueData } from '../hooks/useIssueData'
import { IssueList } from '../components/issues/IssueList'
import { IssueDetail } from '../components/issues/IssueDetail'

interface Props {
  project?: string | null
}

export default function ManagerIssues({ project }: Props) {
  const { issues, groups, stats, loading } = useIssueData(project || null)
  const [selectedId, setSelectedId] = useState<string | null>(null)

  // Auto-select first issue on initial load only
  const hasAutoSelected = useRef(false)
  useEffect(() => {
    if (!hasAutoSelected.current && issues.length > 0) {
      hasAutoSelected.current = true
      setSelectedId(issues[0].id)
    }
  }, [issues])

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-3 border-b border-neutral-800">
        <Link to="/manager" className="text-neutral-500 hover:text-neutral-300 text-sm">Manager</Link>
        <span className="text-neutral-700">/</span>
        <span className="text-sm text-neutral-200">{project || 'All Projects'}</span>
        <span className="text-neutral-700">/</span>
        <span className="text-sm text-neutral-100 font-medium">Issues</span>
        {stats.total_open > 0 && (
          <span className="px-1.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-400">
            {stats.total_open} open
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading && <div className="text-sm text-neutral-500">Loading issues...</div>}
        {!loading && (
          <IssueList
            issues={issues}
            groups={groups}
            selectedId={selectedId}
            onSelect={setSelectedId}
            showEnv={!project}
          />
        )}
      </div>

      {/* Detail slide-out */}
      {selectedId && project && (
        <IssueDetail
          project={project}
          issueId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  )
}
