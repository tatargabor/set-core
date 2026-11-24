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
 * place a relayed question is visible at all, and "to terminal" (formerly "answer here instead", renamed 2026-11-24: the owner read it as
 * "let it through" and pulled six questions off the channel at once) is the only way
 * back to the terminal short of turning the whole relay off.
 *
 * The detail floats under the header and pushes nothing; it closes on its own control,
 * Escape and an outside click.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Hourglass, Send, TriangleAlert, X } from 'lucide-react'

import { age } from '../lib/fleetAge'
import {
  canFlip, orderWaiting, parseRelayState, relayMode, relayTitle, setupCommands, sendable, showUnwired, verdictLine, type RelayState,
} from '../lib/fleetRelay'
import { agentName, kindLabel, useAgentNames } from '../lib/fleetAutoAnswer'
import FleetRelayCall from './FleetRelayCall'

/** Waiting questions come and go on the scale of seconds; the hook polls every 3 s. */
const READ_INTERVAL_MS = 5_000

export default function FleetRelay() {
  useAgentNames()
  const [state, setState] = useState<RelayState | null>(null)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  /** fleet-relay-teach: the call opened over the panel, and how. */
  const [call, setCall] = useState<{ id: string; mode: 'details' | 'teach' } | null>(null)
  const closeCall = useCallback(() => setCall(null), [])
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

  // A call opened over the panel goes with the panel.
  useEffect(() => { if (!open) setCall(null) }, [open])

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

  /** The send route answers with the auto-answer state, not the relay's: re-read after. */
  const send = (id: string) => {
    setBusy(true)
    fetch(`/api/fleet/auto-answer/${encodeURIComponent(id)}/send`, { method: 'POST' })
      .then(async r => {
        if (!r.ok) {
          const d = await r.json().catch(() => null)
          throw new Error(d?.detail ?? `HTTP ${r.status}`)
        }
        setError(null)
        read()
      })
      .catch(e => { setError(`not sent: ${String(e?.message ?? e)}`); setOpen(true) })
      .finally(() => setBusy(false))
  }

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

      {/* B-182: a project whose settings never wired the hook keeps its questions in the
          terminal while the switch says on. That is a fact, so it is marked where the reader
          stands — the closed header — not only inside the detail. */}
      {showUnwired(state) && (
        <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
                className="inline-flex items-center gap-0.5 text-xs tabular-nums text-amber-400 hover:underline underline-offset-2"
                title={`${state.unwired.length} project(s) not wired to the relay — their questions stay in the terminal. Click for the list.`}
                aria-label={`${state.unwired.length} project(s) not wired to the question relay`}
                data-fleet-relay-unwired={state.unwired.length}>
          <TriangleAlert size={12} strokeWidth={1.75} aria-hidden />{state.unwired.length}
        </button>
      )}

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
        <div className="absolute left-2 md:left-6 top-full mt-1 z-30 w-[min(42rem,calc(100vw-1rem))]
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

          {state.unwired.length > 0 && (
            <div className="mt-1.5" data-fleet-relay-unwired-list>
              <p className={state.enabled ? 'text-amber-400' : 'text-fg-muted'}>
                Not wired — questions from {state.unwired.length === 1 ? 'this project' : 'these projects'} stay in the terminal:
              </p>
              <ul className="mt-0.5">
                {state.unwired.map(u => (
                  <li key={u.project} className="flex items-center gap-2 py-0.5" data-fleet-relay-unwired-row={u.project}>
                    <span className="text-fg-strong truncate">{u.project}</span>
                    <span className="text-fg-muted truncate">missing {u.missing.join(', ')}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {waiting.length === 0
            ? <p className="mt-1.5 text-fg-muted">No question is waiting on the channel.</p>
            : (
              <ul className="mt-1 divide-y divide-surface-line/60">
                {waiting.map(w => {
                  const n = agentName(w.session_id, w.project ? `${w.project} · ${w.session_id.slice(0, 8)}` : null, w.project)
                  const v = verdictLine(w.auto_answer)
                  const snd = sendable(w)
                  return (
                  <li key={w.session_id} className="py-1.5" data-fleet-relay-row={w.session_id}>
                    <div className="flex items-center gap-2">
                      <span className="min-w-0 truncate" data-fleet-relay-agent={n.live ? 'live' : 'gone'}
                            title={`${n.project ?? ''} · ${n.label ?? ''} — session ${w.session_id.slice(0, 8)}`}>
                        {n.project && <span className="text-fg-muted">{n.project} · </span>}
                        <span className={n.live ? 'text-fg-loud font-semibold' : 'text-fg-strong'}>{n.label ?? 'unknown agent'}</span>
                      </span>
                      <span className="text-fg-muted whitespace-nowrap">{kindLabel(w.kind === 'question' ? 'ask' : w.kind ?? 'ask')} · {age(w.seconds)}</span>
                      {w.id && (
                        <span className="ml-auto flex items-center gap-2 whitespace-nowrap">
                          <button type="button" onClick={() => setCall({ id: w.id as string, mode: 'details' })}
                                  className="underline decoration-dotted text-fg-muted hover:text-fg-strong"
                                  title="What is asked, its options, what the decider did with it, and what the call waits for"
                                  data-fleet-relay-details={w.id}>
                            details
                          </button>
                          {w.kind !== 'permission' && (w.questions ?? 1) === 1 && (
                            <button type="button" onClick={() => setCall({ id: w.id as string, mode: 'teach' })}
                                    className="underline decoration-dotted text-sky-300/80 hover:text-sky-300"
                                    title="Answer it now AND teach the project the answer for next time, with an optional condition — committed in the project"
                                    data-fleet-relay-teach={w.id}>
                              teach
                            </button>
                          )}
                        </span>
                      )}
                      {w.release_requested
                        ? <span className={`${w.id ? '' : 'ml-auto '}text-fg-muted`}>releasing…</span>
                        : (
                          <button type="button" disabled={busy}
                                  onClick={() => post(`/api/fleet/question-relay/release/${encodeURIComponent(w.session_id)}`)}
                                  className={`${w.id ? '' : 'ml-auto '}whitespace-nowrap underline decoration-dotted text-fg-muted hover:text-fg-strong`}
                                  title="Takes the question OFF the channel: it then waits at the agent's terminal for an answer typed there. It does not answer or approve anything — use it only when you are at the machine."
                                  data-fleet-relay-release={w.session_id}>
                            to terminal ↩
                          </button>
                        )}
                    </div>
                    {v && (
                      <div className="mt-0.5 flex items-center gap-2 min-w-0">
                        <p className={`min-w-0 truncate ${v.tone === 'due' ? 'text-amber-300' : v.tone === 'held' ? 'text-amber-400/80' : 'text-fg-muted'}`}
                           title={v.text} data-fleet-relay-auto={w.auto_answer?.outcome ?? 'none'}>
                          {v.text}
                        </p>
                        {snd && (
                          <button type="button" disabled={busy} onClick={() => send(snd.id)}
                                  className="ml-auto shrink-0 rounded border border-sky-400/50 px-1.5 text-sky-300 hover:bg-sky-400/10"
                                  title={`Answer with «${snd.choice}» as YOUR answer, now — the agent gets it at once`}
                                  data-fleet-relay-send={snd.id}>
                            {snd.label}
                          </button>
                        )}
                      </div>
                    )}
                  </li>
                  )
                })}
              </ul>
            )}
          {call && (
            <FleetRelayCall id={call.id} mode={call.mode} onMode={m => setCall({ id: call.id, mode: m })}
                            onClose={closeCall} onSaved={read} />
          )}
        </div>
      )}
    </span>
  )
}
