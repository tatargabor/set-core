import { useEffect, useState } from 'react'

interface PlanFile {
  filename: string
  size: number
  mtime: string
}

interface PlanChange {
  name: string
  scope?: string
  complexity?: string
  change_type?: string
  dependencies?: string[]
}

interface PlanData {
  changes?: PlanChange[]
  [key: string]: unknown
}

interface Props {
  project: string
}

const complexityColor: Record<string, string> = {
  S: 'text-green-400',
  M: 'text-yellow-400',
  L: 'text-red-400',
}

const typeColor: Record<string, string> = {
  infrastructure: 'text-purple-400',
  schema: 'text-cyan-400',
  foundational: 'text-blue-400',
  feature: 'text-green-400',
  'cleanup-before': 'text-neutral-500',
  'cleanup-after': 'text-neutral-500',
}

export default function PlanViewer({ project }: Props) {
  const [plans, setPlans] = useState<PlanFile[]>([])
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [planData, setPlanData] = useState<PlanData | null>(null)
  const [loading, setLoading] = useState(true)

  // Fetch plan list
  useEffect(() => {
    setLoading(true)
    fetch(`/api/${project}/plans`)
      .then(r => r.json())
      .then((data: { plans: PlanFile[] }) => {
        setPlans(data.plans ?? [])
        // Auto-select latest plan
        if (data.plans?.length > 0) {
          const latest = data.plans[data.plans.length - 1].filename
          setSelectedPlan(latest)
        }
      })
      .catch(() => setPlans([]))
      .finally(() => setLoading(false))
  }, [project])

  // Fetch selected plan data
  useEffect(() => {
    if (!selectedPlan) {
      setPlanData(null)
      return
    }
    fetch(`/api/${project}/plans/${selectedPlan}`)
      .then(r => r.json())
      .then(setPlanData)
      .catch(() => setPlanData(null))
  }, [project, selectedPlan])

  if (loading) {
    return <div className="p-4 text-xs text-neutral-500">Loading plans...</div>
  }

  if (plans.length === 0) {
    return <div className="p-4 text-xs text-neutral-500">No plans found</div>
  }

  const changes = planData?.changes ?? []

  return (
    <div className="space-y-3">
      {/* Plan selector */}
      {plans.length > 1 && (
        <div className="px-4 pt-3 flex items-center gap-2">
          <label className="text-xs text-neutral-500">Plan:</label>
          <select
            value={selectedPlan ?? ''}
            onChange={e => setSelectedPlan(e.target.value)}
            className="bg-neutral-800 text-neutral-300 text-xs rounded px-2 py-1 border border-neutral-700"
          >
            {plans.map(p => (
              <option key={p.filename} value={p.filename}>
                {p.filename.replace('.json', '')}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Changes table */}
      {changes.length > 0 ? (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-neutral-500 border-b border-neutral-800">
              <th className="text-left px-4 py-1.5 font-medium">#</th>
              <th className="text-left px-2 py-1.5 font-medium">Name</th>
              <th className="text-center px-2 py-1.5 font-medium">Size</th>
              <th className="text-left px-2 py-1.5 font-medium">Type</th>
              <th className="text-left px-2 py-1.5 font-medium">Dependencies</th>
              <th className="text-left px-2 py-1.5 font-medium">Scope</th>
            </tr>
          </thead>
          <tbody>
            {changes.map((c, i) => (
              <tr key={c.name} className="border-b border-neutral-800/30 hover:bg-neutral-900/50">
                <td className="px-4 py-1.5 text-neutral-600">{i + 1}</td>
                <td className="px-2 py-1.5 text-neutral-200">{c.name}</td>
                <td className={`px-2 py-1.5 text-center font-medium ${complexityColor[c.complexity ?? ''] ?? 'text-neutral-500'}`}>
                  {c.complexity ?? '?'}
                </td>
                <td className={`px-2 py-1.5 ${typeColor[c.change_type ?? ''] ?? 'text-neutral-500'}`}>
                  {c.change_type ?? ''}
                </td>
                <td className="px-2 py-1.5 text-neutral-500">
                  {c.dependencies?.length ? c.dependencies.join(', ') : '—'}
                </td>
                <td className="px-2 py-1.5 text-neutral-500 max-w-[300px] truncate" title={c.scope}>
                  {c.scope ? (c.scope.length > 60 ? c.scope.slice(0, 60) + '...' : c.scope) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="px-4 py-2 text-xs text-neutral-500">
          {planData ? 'Plan has no changes array' : 'Loading plan data...'}
        </div>
      )}
    </div>
  )
}
