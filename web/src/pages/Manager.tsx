import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { getManagerProjects, type ManagerProjectStatus } from '../lib/api'

export default function Manager() {
  const [projects, setProjects] = useState<ManagerProjectStatus[]>([])
  const [loading, setLoading] = useState(true)
  const jsonRef = useRef('')

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>
    let fails = 0
    const poll = () => {
      getManagerProjects()
        .then(data => {
          fails = 0
          const json = JSON.stringify(data)
          if (json !== jsonRef.current) {
            jsonRef.current = json
            setProjects(data)
          }
          setLoading(false)
          timer = setTimeout(poll, 5000)
        })
        .catch(() => {
          fails++
          setLoading(false)
          timer = setTimeout(poll, Math.min(5000 * Math.pow(2, fails), 30000))
        })
    }
    poll()
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <h1 className="text-lg font-semibold text-neutral-100">Projects</h1>

      {loading && projects.length === 0 && (
        <div className="text-sm text-neutral-500">Loading...</div>
      )}

      {!loading && projects.length === 0 && (
        <div className="p-4 rounded-lg bg-neutral-900 border border-neutral-800 text-sm text-neutral-400">
          No projects found. Register one with: <code className="px-1 py-0.5 bg-neutral-800 rounded text-xs">set-project init</code>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {projects.map(p => {
          const sentinelAlive = p.sentinel?.alive
          const orchAlive = p.orchestrator?.alive
          const status = sentinelAlive ? 'running' : orchAlive ? 'running' : 'idle'
          return (
            <Link
              key={p.name}
              to={`/p/${p.name}/orch`}
              className="block p-4 rounded-lg border border-neutral-800 bg-neutral-900/50 hover:bg-neutral-800/50 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-neutral-200">{p.name}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  status === 'running' ? 'bg-green-900/50 text-green-300' :
                  'bg-neutral-800 text-neutral-400'
                }`}>
                  {status}
                </span>
              </div>
              <div className="text-xs text-neutral-500 font-mono truncate">{p.path}</div>
              <div className="flex gap-2 mt-1.5 text-xs text-neutral-600">
                {sentinelAlive && <span className="text-green-500/70">Sentinel active</span>}
                {p.mode && <span>{p.mode}</span>}
              </div>
            </Link>
          )
        })}
      </div>
    </div>
  )
}
