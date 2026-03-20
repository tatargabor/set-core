import type { ProjectInfo } from '../lib/api'

interface Props {
  projects: ProjectInfo[]
  current: string | null
  onChange: (name: string) => void
}


export default function ProjectSelector({ projects, current, onChange }: Props) {
  return (
    <select
      value={current ?? ''}
      onChange={(e) => onChange(e.target.value)}
      className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1.5 text-sm text-neutral-200 focus:outline-none focus:border-neutral-500"
    >
      {projects.length === 0 && (
        <option value="" disabled>No projects</option>
      )}
      {projects.map((p) => (
        <option key={p.name} value={p.name}>
          {p.status ? `● ` : ''}{p.name}
        </option>
      ))}
    </select>
  )
}

export function ProjectDot({ status }: { status?: string }) {
  const s = status ?? 'idle'
  const colorMap: Record<string, string> = {
    running: 'text-green-400', planning: 'text-cyan-400', checkpoint: 'text-yellow-400',
    done: 'text-blue-400', completed: 'text-blue-400', failed: 'text-red-400', error: 'text-red-400',
  }
  const charMap: Record<string, string> = {
    running: '\u25C9', planning: '\u25C9', checkpoint: '\u25C9',
    done: '\u25CF', completed: '\u25CF', failed: '\u2715', error: '\u2715',
  }
  return <span className={colorMap[s] ?? 'text-neutral-600'}>{charMap[s] ?? '\u25CB'}</span>
}
