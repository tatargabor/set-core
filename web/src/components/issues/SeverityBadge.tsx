import { SEVERITY_STYLES } from './styles'

export function SeverityBadge({ severity }: { severity: string }) {
  const s = SEVERITY_STYLES[severity] || SEVERITY_STYLES.unknown
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${s.color} ${s.bg}`}>
      {s.label}
    </span>
  )
}
