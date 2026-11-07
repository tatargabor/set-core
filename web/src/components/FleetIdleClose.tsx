/**
 * The daily auto-close of long-idle agents, on the fleet header.
 *
 * Asked for by the user (2026-11-07): agents nobody has typed into for two days are closed every
 * night so they stop spending tokens, and they can be brought back. The closing itself is done by
 * `set-fleet-idle-close` on a systemd timer; this control shows it and steers it:
 *
 * - closed: one switch-like icon, lit when the timer is on, with the number of agents the next run
 *   will close riding on it — that number is the only place the coming closes are visible;
 * - open: on/off, the threshold, the next run, who goes next, and who went — each closed one with
 *   "bring back", which restores it from the roster.
 *
 * The detail floats under the header and pushes nothing; it closes on its own control, Escape and
 * an outside click.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { MoonStar, TriangleAlert, X } from 'lucide-react'

import {
  THRESHOLD_CHOICES, canBringBack, idleMode, idleTitle, parseIdleClose, thresholdLabel, whenLabel,
  type IdleCloseState,
} from '../lib/fleetIdleClose'

/** Idle hours change by the hour; a minute is plenty. */
const READ_INTERVAL_MS = 60_000

export default function FleetIdleClose() {
  const [state, setState] = useState<IdleCloseState | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [restored, setRestored] = useState<Record<string, string>>({})
  const rootRef = useRef<HTMLSpanElement>(null)

  const read = useCallback(() => {
    fetch('/api/fleet/idle-close')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(d => {
        const parsed = parseIdleClose(d)
        if (parsed) { setState(parsed); setError(null) } else setError('unexpected answer shape')
      })
      .catch(e => setError(String(e?.message ?? e)))
  }, [])

  useEffect(() => {
    read()
    const t = setInterval(read, READ_INTERVAL_MS)
    return () => clearInterval(t)
  }, [read])

  useEffect(() => {
    if (!open) return
    read()
    const onKey = (e: KeyboardEvent) => {
      // Escape belongs to the open panel: it must never also reach a focused agent terminal,
      // where it would interrupt the agent.
      if (e.key !== 'Escape') return
      e.preventDefault()
      e.stopPropagation()
      setOpen(false)
    }
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    // Capture phase: a focused terminal swallows Escape before it bubbles to the document.
    document.addEventListener('keydown', onKey, true)
    document.addEventListener('pointerdown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [open, read])

  const change = (body: { enabled?: boolean; hours?: number }) => {
    setBusy(true)
    fetch('/api/fleet/idle-close', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    })
      .then(async r => {
        const d = await r.json().catch(() => null)
        if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`)
        const parsed = parseIdleClose(d)
        if (parsed) { setState(parsed); setError(null) } else setError('unexpected answer shape')
      })
      .catch(e => setError(String(e?.message ?? e)))
      .finally(() => setBusy(false))
  }

  const bringBack = (project: string, sessionId: string) => {
    setBusy(true)
    fetch(`/api/fleet/roster/${encodeURIComponent(project)}/restore`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ keys: [sessionId] }),
    })
      .then(async r => {
        const d = await r.json().catch(() => null)
        if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`)
        setRestored(m => ({ ...m, [sessionId]: 'starting…' }))
        read()
      })
      .catch(e => setRestored(m => ({ ...m, [sessionId]: `failed: ${String(e?.message ?? e)}` })))
      .finally(() => setBusy(false))
  }

  if (!state) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-fg-ghost shrink-0"
            data-fleet-idle="unknown" title={error ? `Auto-close unreadable: ${error}` : 'Auto-close: reading…'}>
        <MoonStar size={13} strokeWidth={1.75} aria-hidden />?
      </span>
    )
  }

  const mode = idleMode(state)
  const upcoming = state.upcoming
  const tone = mode === 'on'
    ? 'border-violet-400/60 bg-violet-400/10 text-violet-300'
    : mode === 'unknown'
      ? 'border-amber-400/60 text-amber-400'
      : 'border-transparent text-fg-muted hover:text-fg-strong'
  const choices = THRESHOLD_CHOICES.includes(state.threshold_hours)
    ? THRESHOLD_CHOICES : [...THRESHOLD_CHOICES, state.threshold_hours].sort((a, b) => a - b)

  return (
    <span ref={rootRef} className="inline-flex items-center gap-1 shrink-0" data-fleet-idle={mode}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
              aria-label={idleTitle(state)} title={idleTitle(state)}
              className={`inline-flex items-center gap-1 rounded px-1 border text-xs tabular-nums ${tone}`}
              data-fleet-idle-toggle={mode}>
        <MoonStar size={13} strokeWidth={1.75} aria-hidden />
        {mode === 'unknown' && <TriangleAlert size={12} strokeWidth={1.75} aria-hidden />}
        {mode === 'on' && upcoming.length > 0 && <span data-fleet-idle-upcoming={upcoming.length}>{upcoming.length}</span>}
      </button>

      {open && (
        <div className="absolute left-2 md:left-6 top-full mt-1 z-30 w-[min(36rem,calc(100vw-1rem))]
                        rounded border border-surface-line bg-surface-raised px-3 py-2 shadow-lg text-xs"
             role="dialog" aria-label="Auto-close idle agents" data-fleet-idle-detail={mode}>
          <div className="flex items-center gap-2 pb-1.5 border-b border-surface-line">
            <span className="font-semibold text-fg-loud">Auto-close idle agents</span>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close the auto-close detail"
                    className="ml-auto text-fg-muted hover:text-fg-strong" data-fleet-idle-close>
              <X size={14} strokeWidth={1.75} aria-hidden />
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-1.5">
            <label className="inline-flex items-center gap-1.5 text-fg-strong cursor-pointer">
              <input type="checkbox" checked={state.timer.enabled === true} disabled={busy || mode === 'unknown'}
                     onChange={e => change({ enabled: e.target.checked })} data-fleet-idle-switch />
              daily at night
            </label>
            <label className="inline-flex items-center gap-1.5 text-fg-muted">
              after
              <select value={state.threshold_hours} disabled={busy}
                      onChange={e => change({ hours: Number(e.target.value) })}
                      className="rounded border border-surface-line bg-surface-panel px-1 py-0.5 text-xs text-fg-strong"
                      data-fleet-idle-hours>
                {choices.map(h => <option key={h} value={h}>{thresholdLabel(h)}</option>)}
              </select>
              without your input
            </label>
            <span className="text-fg-muted tabular-nums" data-fleet-idle-next>
              {mode === 'on' ? `next run ${whenLabel(state.timer.next_run)}` : mode === 'off' ? 'not scheduled' : 'timer unreadable'}
            </span>
          </div>

          {(error || state.threshold_error) && (
            <p className="text-red-400 pb-1" data-fleet-idle-error>{error ?? state.threshold_error}</p>
          )}

          <p className="text-fg-muted pt-1 border-t border-surface-line">
            {mode === 'on' ? 'At the next run' : 'Past the threshold now'}
            {' · '}{upcoming.length === 0 ? 'nothing to close' : `${upcoming.length} agent${upcoming.length === 1 ? '' : 's'}`}
          </p>
          {upcoming.length > 0 && (
            <ul className="mt-0.5 mb-1 divide-y divide-surface-line/60" data-fleet-idle-upcoming-list>
              {upcoming.map(r => (
                <li key={r.session_id} className="flex items-center gap-2 py-1" data-fleet-idle-row={r.session_id}>
                  <span className="text-fg-strong truncate">{r.label ?? r.session_id.slice(0, 8)}</span>
                  <span className="text-fg-muted truncate">{r.project ?? ''}</span>
                  <span className="ml-auto text-fg-muted tabular-nums shrink-0">
                    {r.idle_hours !== null ? `${Math.round(r.idle_hours)} h idle` : ''}
                    {r.busy ? ' · busy now, skipped if still busy' : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <p className="text-fg-muted pt-1 border-t border-surface-line">
            Closed{state.closed.length ? ` · ${state.closed.length} most recent` : ' · none yet'}
          </p>
          {state.closed.length > 0 && (
            <ul className="mt-0.5 max-h-60 overflow-y-auto divide-y divide-surface-line/60" data-fleet-idle-closed-list>
              {state.closed.map((r, i) => {
                const note = restored[r.session_id]
                return (
                  <li key={`${r.session_id}-${i}`} className="flex items-center gap-2 py-1" data-fleet-idle-closed={r.session_id}>
                    <span className="text-fg-strong truncate">{r.label ?? r.session_id.slice(0, 8)}</span>
                    <span className="text-fg-muted truncate">{r.project ?? ''}</span>
                    <span className="text-fg-ghost tabular-nums shrink-0">
                      {r.ts ? new Date(r.ts).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                      {r.manual ? ' · by hand' : ''}
                    </span>
                    <span className="ml-auto shrink-0">
                      {note
                        ? <span className={note.startsWith('failed') ? 'text-red-400' : 'text-fg-muted'}>{note}</span>
                        : r.running === true
                          ? <span className="text-fg-muted">running again</span>
                          : canBringBack(r)
                            ? (
                              <button type="button" disabled={busy}
                                      onClick={() => bringBack(r.project as string, r.session_id)}
                                      className="underline decoration-dotted text-fg-muted hover:text-fg-strong"
                                      title="Resume this session in a new fleet terminal, from the roster"
                                      data-fleet-idle-bring-back={r.session_id}>
                                bring back
                              </button>
                            )
                            : <span className="text-fg-ghost" title="Whether it is running could not be checked">?</span>}
                    </span>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      )}
    </span>
  )
}
