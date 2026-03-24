import { SentinelControl } from '../components/manager/SentinelControl'
import { useProjectDetail } from '../hooks/useProjectDetail'
import { useSentinelData } from '../hooks/useSentinelData'
import SentinelPanel from '../components/SentinelPanel'

interface Props {
  project: string | null
}

export default function SentinelPage({ project }: Props) {
  const { project: status, specPaths, loading } = useProjectDetail(project || undefined)
  const sentinelData = useSentinelData(project)

  if (!project) {
    return <div className="flex items-center justify-center h-full text-neutral-500">Select a project</div>
  }

  if (loading) {
    return <div className="p-6 text-sm text-neutral-500">Loading...</div>
  }

  return (
    <div className="flex flex-col h-full">
      {/* Sentinel control */}
      <div className="p-6 border-b border-neutral-800">
        <SentinelControl
          project={project}
          alive={status?.sentinel.alive ?? false}
          startedAt={status?.sentinel.started_at}
          crashCount={status?.sentinel.crash_count}
          activeSpec={status?.sentinel.spec}
          specPaths={specPaths}
        />
      </div>

      {/* Sentinel events panel */}
      <div className="flex-1 min-h-0">
        {sentinelData.hasSentinel ? (
          <SentinelPanel
            project={project}
            events={sentinelData.events}
            findings={sentinelData.findings}
            status={sentinelData.status}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-neutral-600 text-sm">
            Start the sentinel to see events here
          </div>
        )}
      </div>
    </div>
  )
}
