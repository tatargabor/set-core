/**
 * The watchdog on the fleet header — a badge and its floating panel (fleet-watchdog, D6).
 *
 * Asked for by the user (2026-11-24): *„a Fleet-be a UI-on … lássuk valamilyen ikonban,
 * számban, bármiben, hogy hiba van"*. The closed badge carries the fact: the open count, red
 * when any is a fail, and a distinct STALE state when the timer stopped — the "a gap is not
 * a zero" rule. The panel floats (`fixed`, own close control, Escape), and nothing under it
 * moves.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Stethoscope, X } from 'lucide-react'

import { age } from '../lib/fleetAge'
import {
  canDispatch, dispatchLabel, parseWatchdog, verdictLabel, watchdogTitle,
  type WatchdogFinding, type WatchdogState,
} from '../lib/fleetWatchdog'

const READ_INTERVAL_MS = 30_000

function Row({ f, now, busy, onMute, onDispatch }: {
  f: WatchdogFinding; now: number; busy: boolean
  onMute?: (fp: string, days: number) => void; onDispatch?: (fp: string) => void
}) {
  return (
    <li className="px-3 py-1.5 border-b border-surface-line last:border-b-0" data-fleet-watchdog-row={f.fp}>
      <div className="flex items-center gap-2 min-w-0">
        <span className={`shrink-0 uppercase text-xs font-semibold ${f.severity === 'fail' ? 'text-red-400' : 'text-amber-400'}`}>
          {f.severity}
        </span>
        <span className="shrink-0 text-fg-muted">{f.probe}</span>
        <span className="min-w-0 truncate text-fg-strong" title={f.subject}>{f.subject}</span>
        <span className="ml-auto shrink-0 text-fg-ghost tabular-nums" title="first seen">
          {age(now - f.first_seen)}
        </span>
      </div>
      <div className="text-fg-muted">{f.summary}</div>
      <div className="flex items-center gap-2 mt-0.5">
        <span className={f.triage ? 'text-fg-strong' : 'text-amber-400'} data-fleet-watchdog-verdict={verdictLabel(f)}>
          {verdictLabel(f)}
        </span>
        {f.triage?.owner && <span className="text-fg-muted">owner {f.triage.owner}</span>}
        <span className="text-fg-muted">{dispatchLabel(f)}</span>
        <span className="ml-auto flex gap-1">
          {onDispatch && canDispatch(f) && (
            <button type="button" disabled={busy} onClick={() => onDispatch(f.fp)} data-fleet-watchdog-dispatch={f.fp}
                    className="px-1.5 rounded border border-surface-line text-fg-muted hover:text-fg-strong">dispatch now</button>
          )}
          {onMute && [1, 7].map(d => (
            <button key={d} type="button" disabled={busy} onClick={() => onMute(f.fp, d)} data-fleet-watchdog-mute={`${f.fp}:${d}`}
                    className="px-1.5 rounded border border-surface-line text-fg-muted hover:text-fg-strong">mute {d}d</button>
          ))}
        </span>
      </div>
      {f.triage?.brief && <div className="text-fg-ghost italic mt-0.5">{f.triage.brief}</div>}
    </li>
  )
}

export function FleetWatchdogPanel({ state, busy, error, onMute, onDispatch, onClose }: {
  state: WatchdogState | null; busy: boolean; error: string | null
  onMute: (fp: string, days: number) => void; onDispatch: (fp: string) => void; onClose: () => void
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  const now = Date.now() / 1000
  return (
    <div className="fixed z-40 top-14 right-2 w-[min(680px,calc(100vw-5rem))] max-h-[75vh] flex flex-col
                    rounded border border-surface-strong bg-surface-page shadow-2xl text-xs"
         role="dialog" aria-label="Watchdog" data-fleet-watchdog-panel={state?.badge ?? 'unread'}>
      <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-line">
        <Stethoscope size={14} strokeWidth={1.75} aria-hidden />
        <span className="font-semibold text-fg-loud">Watchdog</span>
        {state && (
          <span className={state.badge === 'stale' ? 'text-amber-400' : 'text-fg-muted'} data-fleet-watchdog-tick>
            {state.last_tick_at === null ? 'never ticked' : `last tick ${age(state.last_tick_age_s)} ago`}
            {' · every '}{Math.round(state.interval_s / 60)} min{!state.enabled && ' · disabled'}
          </span>
        )}
        <button type="button" onClick={onClose} aria-label="Close" className="ml-auto text-fg-muted hover:text-fg-strong">
          <X size={14} />
        </button>
      </div>
      {error && <div className="px-3 py-1 text-red-400">{error}</div>}
      <div className="overflow-y-auto">
        {!state ? <div className="px-3 py-2 text-fg-ghost">not read yet</div> : (
          <>
            <div className="px-3 py-1 text-fg-muted border-b border-surface-line">
              open {state.counts.open} · fail {state.counts.fail} · warn {state.counts.warn} · untriaged{' '}
              {state.counts.untriaged} · dispatched {state.counts.dispatched} · resolved 24h {state.counts.resolved_24h}
            </div>
            {state.open.length === 0
              ? <div className="px-3 py-2 text-fg-muted">Nothing open.</div>
              : <ul>{state.open.map(f => <Row key={f.fp} f={f} now={now} busy={busy} onMute={onMute} onDispatch={onDispatch} />)}</ul>}
            {state.muted.length > 0 && (
              <>
                <div className="px-3 py-1 text-fg-ghost border-y border-surface-line">muted ({state.muted.length})</div>
                <ul>{state.muted.map(f => <Row key={f.fp} f={f} now={now} busy={busy} />)}</ul>
              </>
            )}
            {state.resolved.length > 0 && (
              <>
                <div className="px-3 py-1 text-fg-ghost border-y border-surface-line">resolved in 24 h ({state.resolved.length})</div>
                <ul>{state.resolved.slice(0, 10).map(f => <Row key={f.fp} f={f} now={now} busy={busy} />)}</ul>
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function FleetWatchdog() {
  const [state, setState] = useState<WatchdogState | null>(null)
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const alive = useRef(true)
  useEffect(() => () => { alive.current = false }, [])

  const read = useCallback(() => {
    fetch('/api/fleet/watchdog')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(d => {
        const parsed = parseWatchdog(d)
        if (!parsed) throw new Error('unexpected answer shape')
        if (alive.current) { setState(parsed); setError(null) }
      })
      .catch(e => { if (alive.current) { setState(null); setError(String(e?.message ?? e)) } })
  }, [])

  useEffect(() => {
    read()
    const t = window.setInterval(read, READ_INTERVAL_MS)
    return () => window.clearInterval(t)
  }, [read])

  const post = (url: string, body?: unknown) => {
    setBusy(true)
    fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
      .then(async r => {
        const d = await r.json().catch(() => null)
        if (!r.ok) throw new Error(d?.detail ?? `HTTP ${r.status}`)
        if (d && d.ok === false && d.reason) throw new Error(d.reason)
      })
      .catch(e => { if (alive.current) setError(String(e?.message ?? e)) })
      .finally(() => { if (alive.current) { setBusy(false); read() } })
  }

  const badge = state?.badge ?? 'unread'
  const tone = badge === 'red' ? 'border-red-400/60 bg-red-400/10 text-red-300'
    : badge === 'count' ? 'border-amber-400/60 text-amber-400'
      : badge === 'stale' ? 'border-dashed border-fg-ghost text-fg-ghost'
        : badge === 'unread' ? 'border-transparent text-fg-ghost'
          : 'border-transparent text-fg-muted hover:text-fg-strong'
  const title = watchdogTitle(state, error, age(state?.last_tick_age_s))
  return (
    <>
      <button type="button" onClick={() => setOpen(o => !o)} aria-expanded={open} aria-label={title} title={title}
              data-fleet-watchdog-badge={badge} data-fleet-watchdog-count={state?.counts.open ?? 0}
              className={`inline-flex items-center gap-1 rounded px-1 border text-xs tabular-nums shrink-0 ${tone}`}>
        <Stethoscope size={13} strokeWidth={1.75} aria-hidden />
        {(badge === 'unread') && <span aria-hidden>?</span>}
        {badge === 'stale' && <span data-fleet-watchdog-stale>stale</span>}
        {(badge === 'red' || badge === 'count') && <span data-fleet-watchdog-open>{state!.counts.open}</span>}
      </button>
      {open && (
        <FleetWatchdogPanel state={state} busy={busy} error={error}
                            onMute={(fp, days) => post(`/api/fleet/watchdog/${fp}/mute`, { days })}
                            onDispatch={fp => post(`/api/fleet/watchdog/${fp}/dispatch`)}
                            onClose={() => setOpen(false)} />
      )}
    </>
  )
}
