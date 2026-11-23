/**
 * Automatic answers — the header control and its floating panel (fleet-auto-answer, D13).
 *
 * Asked for by the user (2026-11-23): *„felületen is kell rá gomb és kis felület mint az új
 * relation map"*. One control beside the question-relay switch: on/off, and the count of
 * proposals that will be WRITTEN unless somebody answers first — a thing that will act, so
 * it is counted on the closed control. It opens a panel built like the relation map's:
 * `fixed`, above the fleet, its own close control, nothing under it moves.
 *
 * Inside: the switch, the pending proposals (agent, question, proposed answer, tier, the
 * checked references, a countdown, cancel), and the newest decision-log records. The log
 * holds the operator's own answer next to each proposal, so "did it guess right" is
 * visible per row — the live measurement D14 asks for.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Bot, X } from 'lucide-react'

import { age } from '../lib/fleetAge'
import {
  autoMode, autoTitle, countdown, matched, outcomeLabel, parseAutoAnswerState, parseDecisions,
  publishPending, tierLabel, usePendingFor,
  type AutoAnswerState, type DecisionRecord, type PendingProposal,
} from '../lib/fleetAutoAnswer'

/** The window is 60 s by default; a 5 s read keeps the count honest on the closed control. */
const READ_INTERVAL_MS = 5_000
const LOG_INTERVAL_MS = 10_000

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!active) return
    const t = window.setInterval(() => setNow(Date.now()), 1_000)
    return () => window.clearInterval(t)
  }, [active])
  return now
}

function Refs({ refs }: { refs: PendingProposal['references'] }) {
  if (refs.length === 0) return <span className="text-fg-ghost">no checked source</span>
  return (
    <ul className="mt-0.5 space-y-0.5">
      {refs.slice(0, 3).map((r, i) => (
        <li key={i} className="text-fg-muted" data-fleet-auto-ref={r.kind}>
          <span className="text-fg-strong">{r.kind === 'operator' ? 'your words' : r.path}</span>
          {': '}<span className="italic">“{r.quote.length > 160 ? `${r.quote.slice(0, 159)}…` : r.quote}”</span>
        </li>
      ))}
    </ul>
  )
}

export function FleetAutoAnswerPanel({ state, decisions, readAt, busy, error, onToggle, onCancel, onClose }: {
  state: AutoAnswerState | null
  decisions: DecisionRecord[] | null
  readAt: number
  busy: boolean
  error: string | null
  onToggle: () => void
  onCancel: (id: string) => void
  onClose: () => void
}) {
  const now = useNow(true)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  const mode = autoMode(state)
  const elapsed = (now - readAt) / 1000
  return (
    <div className="fixed z-40 top-14 right-2 w-[min(640px,calc(100vw-5rem))] max-h-[75vh] flex flex-col
                    rounded border border-surface-strong bg-surface-page shadow-2xl text-xs"
         role="dialog" aria-label="Automatic answers" data-fleet-auto-panel={mode}>
      <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-line">
        <Bot size={14} strokeWidth={1.75} aria-hidden />
        <span className="font-semibold text-fg-loud">Automatic answers</span>
        {state && (
          <button type="button" disabled={busy} onClick={onToggle} aria-pressed={state.enabled}
                  data-fleet-auto-switch={state.enabled ? 'on' : 'off'}
                  className={`px-1.5 rounded border ${state.enabled
                    ? 'border-sky-400/60 bg-sky-400/10 text-sky-300' : 'border-surface-line text-fg-muted hover:text-fg-strong'}`}
                  title={state.enabled ? 'Turn automatic answers off — every relayed question waits for you'
                    : 'Turn automatic answers on — allowed proposals are written after the window'}>
            {state.enabled ? 'on' : 'off'}
          </button>
        )}
        {state && <span className="text-fg-muted">window {state.window_s}s · bar {state.likely_min.toFixed(2)}</span>}
        <button type="button" onClick={onClose} aria-label="Close the automatic answers panel"
                className="ml-auto text-fg-muted hover:text-fg-strong" data-fleet-auto-close>
          <X size={14} strokeWidth={1.75} aria-hidden />
        </button>
      </div>

      <div className="overflow-auto px-3 py-2 space-y-3">
        {error && <p className="text-red-400" data-fleet-auto-error>{error}</p>}
        {mode === 'on-not-wired' && (
          <div className="text-amber-400" data-fleet-auto-not-wired>
            <p>The switch is on, but the question relay does not run the decider, so nothing is decided. Wire it:</p>
            <pre className="mt-1 whitespace-pre-wrap break-all text-fg-strong bg-surface-panel rounded px-2 py-1">
              {'set-config set auto_answer.forward_command "<the current question_relay.command>"\nset-config set question_relay.command set-auto-answer'}
            </pre>
          </div>
        )}

        <section>
          <h3 className="text-fg-strong font-semibold">Pending — written unless you answer or cancel</h3>
          {!state ? <p className="text-fg-ghost">reading…</p>
            : state.pending.length === 0 ? <p className="text-fg-muted" data-fleet-auto-pending="0">Nothing pending.</p>
            : (
              <ul className="divide-y divide-surface-line/60" data-fleet-auto-pending={state.pending.length}>
                {state.pending.map(p => (
                  <li key={`${p.id}:${p.key}`} className="py-1.5" data-fleet-auto-row={p.id}>
                    <div className="flex items-center gap-2">
                      <span className="text-fg-strong truncate">{p.agent ?? p.project ?? 'unknown agent'}</span>
                      <span className="text-fg-muted">{tierLabel(p.tier, p.confidence)}</span>
                      <span className="ml-auto tabular-nums text-amber-400" data-fleet-auto-countdown>
                        in {countdown(p.seconds_left === null ? null : p.seconds_left - elapsed)}
                      </span>
                      <button type="button" disabled={busy} onClick={() => onCancel(p.id)}
                              className="underline decoration-dotted text-fg-muted hover:text-fg-strong"
                              title="Do not write it: the question keeps waiting for your answer"
                              data-fleet-auto-cancel={p.id}>
                        cancel
                      </button>
                    </div>
                    <p className="mt-0.5 text-fg-muted line-clamp-2">{p.question}</p>
                    <p className="mt-0.5">→ <span className="text-fg-loud font-semibold">{p.choice}</span></p>
                    <Refs refs={p.references} />
                  </li>
                ))}
              </ul>
            )}
        </section>

        <section>
          <h3 className="text-fg-strong font-semibold">Recent decisions</h3>
          {decisions === null ? <p className="text-fg-ghost">reading…</p>
            : decisions.length === 0 ? <p className="text-fg-muted" data-fleet-auto-decisions="0">No decision logged yet.</p>
            : (
              <table className="w-full table-fixed" data-fleet-auto-decisions={decisions.length}>
                <tbody className="divide-y divide-surface-line/60">
                  {decisions.map(d => {
                    const o = outcomeLabel(d.outcome)
                    const m = matched(d)
                    return (
                      <tr key={`${d.id}:${d.key}:${d.ts}`} className="align-top" data-fleet-auto-decision={d.outcome ?? '?'}>
                        <td className="w-12 py-1 text-fg-ghost tabular-nums">{age(Date.now() / 1000 - d.ts)}</td>
                        <td className="py-1 pr-2">
                          <span className="text-fg-strong">{d.agent ?? '?'}</span>
                          <p className="text-fg-muted line-clamp-1" title={d.question}>{d.question}</p>
                        </td>
                        <td className="w-40 py-1 pr-2 truncate" title={d.choice ?? ''}>
                          {d.choice ?? <span className="text-fg-ghost">—</span>}
                          <p className="text-fg-muted">{tierLabel(d.tier, d.confidence)}</p>
                        </td>
                        <td className="w-36 py-1">
                          <span className={o.tone === 'loud' ? 'text-sky-300' : o.tone === 'warn' ? 'text-amber-400' : 'text-fg-muted'}>
                            {o.text}
                          </span>
                          {d.human_answer !== null && (
                            <p className={m ? 'text-emerald-400' : 'text-fg-muted'} title={d.human_answer}
                               data-fleet-auto-match={m ? 'yes' : 'no'}>
                              {m ? 'matched your answer' : `you: ${d.human_answer.slice(0, 40)}`}
                            </p>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
        </section>
      </div>
    </div>
  )
}

/** The header control: on/off and the pending count while closed, the panel while open. */
export default function FleetAutoAnswer() {
  const [state, setState] = useState<AutoAnswerState | null>(null)
  const [decisions, setDecisions] = useState<DecisionRecord[] | null>(null)
  const [readAt, setReadAt] = useState(() => Date.now())
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])

  const accept = useCallback((d: unknown) => {
    const parsed = parseAutoAnswerState(d)
    if (!parsed) throw new Error('unexpected answer shape')
    if (!alive.current) return
    setState(parsed)
    setReadAt(Date.now())
    setError(null)
    publishPending(parsed.pending)
  }, [])

  const read = useCallback(() => {
    fetch('/api/fleet/auto-answer')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(accept)
      .catch(e => { if (alive.current) setError(String(e?.message ?? e)) })
  }, [accept])

  useEffect(() => {
    read()
    const t = window.setInterval(read, READ_INTERVAL_MS)
    return () => window.clearInterval(t)
  }, [read])

  useEffect(() => {
    if (!open) return
    const readLog = () => {
      fetch('/api/fleet/auto-answer/decisions?limit=30')
        .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then(d => { if (alive.current) setDecisions(parseDecisions(d) ?? []) })
        .catch(e => { if (alive.current) setError(String(e?.message ?? e)) })
    }
    readLog()
    const t = window.setInterval(readLog, LOG_INTERVAL_MS)
    return () => window.clearInterval(t)
  }, [open])

  const post = (url: string, body?: unknown) => {
    setBusy(true)
    fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
      .then(async r => {
        const d = await r.json().catch(() => null)
        if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`)
        accept(d)
      })
      .catch(e => { if (alive.current) setError(String(e?.message ?? e)) })
      .finally(() => { if (alive.current) setBusy(false) })
  }

  const mode = autoMode(state)
  const pending = state?.pending.length ?? 0
  const tone = mode === 'on' ? 'border-sky-400/60 bg-sky-400/10 text-sky-300'
    : mode === 'on-not-wired' ? 'border-amber-400/60 text-amber-400'
      : mode === 'unread' ? 'border-transparent text-fg-ghost'
        : 'border-transparent text-fg-muted hover:text-fg-strong'
  return (
    <>
      <button type="button" onClick={() => setOpen(o => !o)} aria-expanded={open}
              aria-label={autoTitle(state, error)} title={autoTitle(state, error)}
              data-fleet-auto-toggle={mode} data-fleet-auto-count={pending}
              className={`inline-flex items-center gap-1 rounded px-1 border text-xs tabular-nums shrink-0 ${tone}`}>
        <Bot size={13} strokeWidth={1.75} aria-hidden />
        {mode === 'unread' && <span aria-hidden>?</span>}
        {pending > 0 && <span className="text-amber-400" data-fleet-auto-pending-count={pending}>{pending}</span>}
      </button>
      {open && (
        <FleetAutoAnswerPanel state={state} decisions={decisions} readAt={readAt} busy={busy} error={error}
                              onToggle={() => state && post('/api/fleet/auto-answer', { enabled: !state.enabled })}
                              onCancel={id => post(`/api/fleet/auto-answer/${encodeURIComponent(id)}/cancel`)}
                              onClose={() => setOpen(false)} />
      )}
    </>
  )
}

/** The mark on the asking agent's tile: what will be written for it, and when. */
export function FleetAutoAnswerMark({ sessionId }: { sessionId: string | null | undefined }) {
  const p = usePendingFor(sessionId)
  if (!p) return null
  return (
    <span className="inline-flex items-center gap-1 text-xs text-amber-400 whitespace-nowrap"
          data-fleet-auto-mark={p.id}
          title={`An automatic answer will be written unless you answer first: “${p.choice}” (${tierLabel(p.tier, p.confidence)}). Cancel it from the header's automatic-answers panel.`}>
      <Bot size={12} strokeWidth={1.75} aria-hidden />
      auto «{p.choice.length > 24 ? `${p.choice.slice(0, 23)}…` : p.choice}» in {countdown(p.seconds_left)}
    </span>
  )
}
