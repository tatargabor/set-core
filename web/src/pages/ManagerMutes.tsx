import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getMutePatterns, addMutePattern, deleteMutePattern, type MutePattern } from '../lib/api'

export default function ManagerMutes() {
  const { project } = useParams<{ project: string }>()
  const [mutes, setMutes] = useState<MutePattern[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [newPattern, setNewPattern] = useState('')
  const [newReason, setNewReason] = useState('')

  const load = () => {
    if (project) getMutePatterns(project).then(setMutes).catch(() => {})
  }

  useEffect(load, [project])

  const handleAdd = async () => {
    if (!project || !newPattern.trim()) return
    await addMutePattern(project, newPattern.trim(), newReason.trim())
    setNewPattern(''); setNewReason(''); setShowAdd(false)
    load()
  }

  const handleDelete = async (id: string) => {
    if (!project || !window.confirm('Delete this mute pattern?')) return
    await deleteMutePattern(project, id)
    load()
  }

  return (
    <div className="p-6 space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link to="/manager" className="text-neutral-500 hover:text-neutral-300 text-sm">Manager</Link>
          <span className="text-neutral-700">/</span>
          <span className="text-sm text-neutral-200">{project}</span>
          <span className="text-neutral-700">/</span>
          <span className="text-sm text-neutral-100 font-medium">Mute Patterns</span>
        </div>
        <button onClick={() => setShowAdd(true)}
          className="px-3 py-1.5 text-xs rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30">
          + Add Mute
        </button>
      </div>

      {showAdd && (
        <div className="p-4 rounded-lg bg-neutral-900 border border-neutral-800 space-y-3">
          <input value={newPattern} onChange={e => setNewPattern(e.target.value)} placeholder="Regex pattern"
            className="w-full bg-neutral-800 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-200 placeholder-neutral-600" />
          <input value={newReason} onChange={e => setNewReason(e.target.value)} placeholder="Reason"
            className="w-full bg-neutral-800 border border-neutral-700 rounded px-3 py-2 text-sm text-neutral-200 placeholder-neutral-600" />
          <div className="flex gap-2">
            <button onClick={handleAdd} className="px-3 py-1.5 text-xs rounded bg-blue-600/20 text-blue-400">Add</button>
            <button onClick={() => setShowAdd(false)} className="px-3 py-1.5 text-xs rounded bg-neutral-700 text-neutral-400">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {mutes.length === 0 && <div className="text-sm text-neutral-500">No mute patterns</div>}
        {mutes.map(m => (
          <div key={m.id} className="p-3 rounded-lg bg-neutral-900 border border-neutral-800">
            <div className="flex items-start justify-between gap-2">
              <div className="space-y-1 min-w-0">
                <code className="text-xs text-neutral-300 font-mono break-all">{m.pattern}</code>
                <p className="text-xs text-neutral-500">{m.reason}</p>
                <div className="flex gap-3 text-xs text-neutral-600">
                  <span>Suppressed: {m.match_count}x</span>
                  {m.last_matched_at && <span>Last: {new Date(m.last_matched_at).toLocaleString()}</span>}
                  {m.expires_at ? <span>Expires: {new Date(m.expires_at).toLocaleDateString()}</span> : <span>No expiry</span>}
                </div>
              </div>
              <button onClick={() => handleDelete(m.id)}
                className="text-xs px-2 py-1 rounded bg-red-950/30 text-red-400 hover:bg-red-950/50 shrink-0">
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
