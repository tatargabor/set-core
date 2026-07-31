import type { ProjectInfo } from '../hooks/useProject'

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
      className="w-full bg-surface-panel border border-surface-edge rounded px-2 py-1.5 text-sm text-fg-strong focus:outline-none focus:border-fg-faint"
    >
      {projects.length === 0 && (
        <option value="" disabled>No projects</option>
      )}
      {projects.map((p) => (
        <option key={p.name} value={p.name}>
          {p.status === 'running' ? '\u25CF ' : '\u25CB '}{p.name}
        </option>
      ))}
    </select>
  )
}
