import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { getProjects, type ProjectInfo } from '../lib/api'

export default function Manager() {
  const [projects, setProjects] = useState<ProjectInfo[]>([])
  const [loading, setLoading] = useState(true)
  const jsonRef = useRef('')

  useEffect(() => {
    const poll = () => {
      getProjects()
        .then(data => {
          const json = JSON.stringify(data)
          if (json !== jsonRef.current) {
            jsonRef.current = json
            setProjects(data)
          }
          setLoading(false)
        })
        .catch(() => setLoading(false))
    }
    poll()
    const iv = setInterval(poll, 5000)
    return () => clearInterval(iv)
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
        {projects.map(p => (
          <Link
            key={p.name}
            to={`/p/${p.name}/orch`}
            className="block p-4 rounded-lg border border-neutral-800 bg-neutral-900/50 hover:bg-neutral-800/50 transition-colors"
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-neutral-200">{p.name}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${
                p.status === 'running' ? 'bg-green-900/50 text-green-300' :
                p.status === 'done' ? 'bg-blue-900/50 text-blue-300' :
                p.status === 'stopped' ? 'bg-amber-900/50 text-amber-300' :
                'bg-neutral-800 text-neutral-400'
              }`}>
                {p.status || 'idle'}
              </span>
            </div>
            <div className="text-xs text-neutral-500 font-mono truncate">{p.path}</div>
            {p.has_orchestration && (
              <div className="mt-1 text-xs text-neutral-600">Orchestration configured</div>
            )}
          </Link>
        ))}
      </div>
    </div>
  )
}
