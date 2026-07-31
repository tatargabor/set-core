import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getMutePatterns, addMutePattern, deleteMutePattern, type MutePattern } from '../lib/api'

interface Props {
  project?: string | null
}

export default function ManagerMutes({ project: projectProp }: Props) {
  const project = projectProp ?? undefined
  const [mutes, setMutes] = useState<MutePattern[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [newPattern, setNewPattern] = useState('')
  const [newReason, setNewReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState<string | null>(null)

  const load = () => {
    if (project) getMutePatterns(project).then(setMutes).catch(() => {})
  }

  useEffect(load, [project])

  const handleAdd = async () => {
    if (!project || !newPattern.trim() || busy) return
    setBusy(true)
    try {
      await addMutePattern(project, newPattern.trim(), newReason.trim())
      setNewPattern(''); setNewReason(''); setShowAdd(false)
      load()
    } finally { setBusy(false) }
  }

  const handleDelete = async (id: string) => {
    if (!project || deleting || !window.confirm('Delete this mute pattern?')) return
    setDeleting(id)
    try {
      await deleteMutePattern(project, id)
      load()
    } finally { setDeleting(null) }
  }

  return (
    <div className="p-6 space-y-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link to="/manager" className="text-fg-faint hover:text-fg-normal text-sm">Manager</Link>
          <span className="text-fg-dim">/</span>
          <span className="text-sm text-fg-strong">{project}</span>
          <span className="text-fg-dim">/</span>
          <span className="text-sm text-fg-loud font-medium">Mute Patterns</span>
        </div>
        <button onClick={() => setShowAdd(true)}
          className="px-3 py-1.5 text-xs rounded bg-blue-600/20 text-blue-400 hover:bg-blue-600/30">
          + Add Mute
        </button>
      </div>

      {showAdd && (
        <div className="p-4 rounded-lg bg-surface-panel border border-surface-line space-y-3">
          <input value={newPattern} onChange={e => setNewPattern(e.target.value)} placeholder="Regex pattern"
            className="w-full bg-surface-raised border border-surface-edge rounded px-3 py-2 text-sm text-fg-strong placeholder-neutral-600" />
          <input value={newReason} onChange={e => setNewReason(e.target.value)} placeholder="Reason"
            className="w-full bg-surface-raised border border-surface-edge rounded px-3 py-2 text-sm text-fg-strong placeholder-neutral-600" />
          <div className="flex gap-2">
            <button onClick={handleAdd} disabled={busy || !newPattern.trim()} className="px-3 py-1.5 text-xs rounded bg-blue-600/20 text-blue-400 disabled:opacity-50 disabled:cursor-not-allowed">{busy ? 'Adding…' : 'Add'}</button>
            <button onClick={() => setShowAdd(false)} disabled={busy} className="px-3 py-1.5 text-xs rounded bg-surface-strong text-fg-muted disabled:opacity-50 disabled:cursor-not-allowed">Cancel</button>
          </div>
        </div>
      )}

      <div className="space-y-2">
        {mutes.length === 0 && <div className="text-sm text-fg-faint">No mute patterns</div>}
        {mutes.map(m => (
          <div key={m.id} className="p-3 rounded-lg bg-surface-panel border border-surface-line">
            <div className="flex items-start justify-between gap-2">
              <div className="space-y-1 min-w-0">
                <code className="text-xs text-fg-normal break-all">{m.pattern}</code>
                <p className="text-xs text-fg-faint">{m.reason}</p>
                <div className="flex gap-3 text-xs text-fg-ghost">
                  <span>Suppressed: {m.match_count}x</span>
                  {m.last_matched_at && <span>Last: {new Date(m.last_matched_at).toLocaleString()}</span>}
                  {m.expires_at ? <span>Expires: {new Date(m.expires_at).toLocaleDateString()}</span> : <span>No expiry</span>}
                </div>
              </div>
              <button onClick={() => handleDelete(m.id)}
                disabled={deleting === m.id}
                className="text-xs px-2 py-1 rounded bg-red-950/30 text-red-400 hover:bg-red-950/50 shrink-0 disabled:opacity-50 disabled:cursor-not-allowed">
                {deleting === m.id ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
