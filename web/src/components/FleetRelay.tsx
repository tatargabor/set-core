/**
 * The question relay's switch, on the fleet header.
 *
 * Asked for by the user (2026-10-10, confirmed 2026-10-11): one switch, and while it is
 * on every agent's blocking question goes to the chat channel and the answer comes back.
 * The relaying is done by a hook in every session (`set-hook-question-relay`); this
 * control only flips the machine's switch and shows what is waiting.
 *
 * Why the waiting count matters more than the switch: while the hook waits, the agent's
 * terminal shows "running PreToolUse hook" and the fleet sees it as busy — the question is
 * not in its transcript yet (measured). So the count on the CLOSED control is the only
 * place a relayed question is visible at all, and "answer here instead" is the only way
 * back to the terminal short of turning the whole relay off.
 *
 * The detail floats under the header and pushes nothing; it closes on its own control,
 * Escape and an outside click.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Hourglass, Send, TriangleAlert, X } from 'lucide-react'

import { age } from '../lib/fleetAge'
import {
  canFlip, orderWaiting, parseRelayState, relayMode, relayTitle, setupCommands, type RelayState,
} from '../lib/fleetRelay'

/** Waiting questions come and go on the scale of seconds; the hook polls every 3 s. */
const READ_INTERVAL_MS = 5_000

export default function FleetRelay() {
  const [state, setState] = useState<RelayState | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const rootRef = useRef<HTMLSpanElement>(null)

  const read = useCallback(() => {
    fetch('/api/fleet/question-relay')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(d => {
        const parsed = parseRelayState(d)
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
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [open])

  const post = (url: string, body?: unknown) => {
    setBusy(true)
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
      .then(async r => {
        const d = await r.json().catch(() => null)
        if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`)
        const parsed = parseRelayState(d)
        if (parsed) { setState(parsed); setError(null) } else setError('unexpected answer shape')
      })
      .catch(e => { setError(String(e?.message ?? e)); setOpen(true) })
      .finally(() => setBusy(false))
  }

  if (!state) {
    // Not measured yet, or the route failed before ever answering: a muted mark, and the
    // reason on the title — never a switch that looks off when nobody asked.
    return (
      <span className="inline-flex items-center gap-1 text-xs text-fg-ghost shrink-0"
            data-fleet-relay="unknown" title={error ? `Question relay unreadable: ${error}` : 'Question relay: reading…'}>
        <Send size={13} strokeWidth={1.75} aria-hidden />?
      </span>
    )
  }

  const mode = relayMode(state)
  const waiting = orderWaiting(state.waiting)
  const toggleTone = mode === 'on'
    ? 'border-sky-400/60 bg-sky-400/10 text-sky-300'
    : mode === 'on-not-ready'
      ? 'border-amber-400/60 text-amber-400'
      : mode === 'not-ready'
        ? 'border-transparent text-fg-ghost hover:text-fg-strong'
        : 'border-transparent text-fg-muted hover:text-fg-strong'

  return (
    <span ref={rootRef} className="inline-flex items-center gap-1 shrink-0" data-fleet-relay={mode}>
      <button type="button" disabled={busy}
              onClick={() => (canFlip(state)
                ? post('/api/fleet/question-relay', { enabled: !state.enabled })
                : setOpen(true))}
              aria-pressed={state.enabled}
              aria-label={relayTitle(state)} title={relayTitle(state)}
              className={`inline-flex items-center gap-1 rounded px-1 border text-xs ${toggleTone}`}
              data-fleet-relay-toggle={state.enabled ? 'on' : 'off'}>
        <Send size={13} strokeWidth={1.75} aria-hidden />
        {mode === 'on-not-ready' && <TriangleAlert size={12} strokeWidth={1.75} aria-hidden />}
      </button>

      {/* The waiting count rides on the CLOSED header: a relayed question is invisible
          everywhere else on this screen while the hook holds it. */}
      {(waiting.length > 0 || mode === 'not-ready' || mode === 'on-not-ready' || error) && (
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
                className={`inline-flex items-center gap-0.5 text-xs tabular-nums ${
                  waiting.length > 0 ? 'text-amber-400' : 'text-fg-muted'} hover:underline underline-offset-2`}
                title={waiting.length > 0
                  ? `${waiting.length} question(s) waiting on the chat channel — click to answer one here instead`
                  : 'Question relay detail'}
                aria-label={waiting.length > 0 ? `${waiting.length} question(s) waiting on the channel` : 'question relay detail'}
                data-fleet-relay-waiting={waiting.length}>
          {waiting.length > 0
            ? <><Hourglass size={12} strokeWidth={1.75} aria-hidden />{waiting.length}</>
            : <span aria-hidden>…</span>}
        </button>
      )}

      {open && (
        <div className="absolute left-2 md:left-6 top-full mt-1 z-30 w-[min(34rem,calc(100vw-1rem))]
                        rounded border border-surface-line bg-surface-raised px-3 py-2 shadow-lg text-xs"
             role="dialog" aria-label="Question relay" data-fleet-relay-detail={mode}>
          <div className="flex items-center gap-2 pb-1 border-b border-surface-line">
            <span className="font-semibold text-fg-loud">Question relay</span>
            <span className="text-fg-muted">{mode === 'on' ? 'on' : mode === 'off' ? 'off' : 'not configured'}
              {state.target ? ` · ${state.target}` : ''}</span>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close the question relay detail"
                    className="ml-auto text-fg-muted hover:text-fg-strong" data-fleet-relay-close>
              <X size={14} strokeWidth={1.75} aria-hidden />
            </button>
          </div>

          {error && <p className="mt-1 text-red-400" data-fleet-relay-error>{error}</p>}

          {state.missing.length > 0 && (
            <div className="mt-1.5" data-fleet-relay-missing={state.missing.join(' ')}>
              <p className="text-fg-muted">This machine's relay is missing {state.missing.join(', ')}. Set it in a terminal:</p>
              <pre className="mt-1 whitespace-pre-wrap break-all text-fg-strong bg-surface-panel rounded px-2 py-1">
                {setupCommands(state).join('\n')}
              </pre>
            </div>
          )}

          {waiting.length === 0
            ? <p className="mt-1.5 text-fg-muted">No question is waiting on the channel.</p>
            : (
              <ul className="mt-1 divide-y divide-surface-line/60">
                {waiting.map(w => (
                  <li key={w.session_id} className="flex items-center gap-2 py-1.5"
                      data-fleet-relay-row={w.session_id}>
                    <span className="text-fg-strong truncate">{w.project ?? 'unknown project'}</span>
                    <span className="text-fg-muted tabular-nums">{w.session_id.slice(0, 8)}</span>
                    <span className="text-fg-muted tabular-nums">
                      {w.questions ?? '?'} question{w.questions === 1 ? '' : 's'} · {age(w.seconds)}
                    </span>
                    {w.release_requested
                      ? <span className="ml-auto text-fg-muted">releasing…</span>
                      : (
                        <button type="button" disabled={busy}
                                onClick={() => post(`/api/fleet/question-relay/release/${encodeURIComponent(w.session_id)}`)}
                                className="ml-auto underline decoration-dotted text-fg-muted hover:text-fg-strong"
                                title="Stop waiting on the channel: the question appears at the agent's terminal within a few seconds"
                                data-fleet-relay-release={w.session_id}>
                          answer here instead
                        </button>
                      )}
                  </li>
                ))}
              </ul>
            )}
        </div>
      )}
    </span>
  )
}
