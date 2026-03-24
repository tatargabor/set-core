import { MODE_STYLES } from '../issues/styles'

export function ModeBadge({ mode }: { mode: string }) {
  const s = MODE_STYLES[mode] || MODE_STYLES.development
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold ${s.color} ${s.bg}`}>
      {s.label}
    </span>
  )
}
