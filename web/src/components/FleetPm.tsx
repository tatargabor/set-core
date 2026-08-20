import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'

import FleetInstruct from './FleetInstruct'
import FleetTerminal from './FleetTerminal'
import { age } from '../lib/fleetAge'
import { COUNTDOWN_MS, latestInput, secondsSinceInput } from '../lib/fleetPm'
import type { PmSnapshot } from '../lib/fleetPm'
import type { FleetAgent } from '../lib/fleetTypes'

/**
 * PM mode — one agent at a time, chosen for the reader.
 *
 * ## The frame is not decoration, it is the price of the freeze
 *
 * A full-screen presentation is the strongest hiding this surface does:
 * everything else is off screen, and a queue that silently grows behind it
 * looks exactly like a fleet with nothing left to do. So the always-visible bar
 * carries what is queued, what is idle, and whether the judgement for this
 * cycle could be made at all — the last of which is a DIFFERENT fact from an
 * empty queue and is rendered as one.
 *
 * ## Typing is the guard; the countdown is a courtesy
 *
 * While the reader has typed recently nothing switches and no countdown is
 * shown. The decision is the server's — `seconds_since_input` is sent and the
 * server answers with a `pending_switch` or null — so a client that forgets to
 * send it cannot disable the guard. The countdown here is the announcement of
 * a decision already made, and ANY input cancels it, because typing is the
 * evidence of engagement and nobody should have to remember which key rescues
 * them.
 *
 * ## Both input paths count
 *
 * The terminal and the instruct box. The second is the one that gets
 * forgotten, and for an agent the framework holds no terminal for it is the
 * ONLY way to answer — so a guard watching the terminal alone would protect
 * nothing on exactly those items.
 */

const POLL_MS = 4000

function Count({ n, label, tone, title, counted }: {
  n: number; label: string; tone?: string; title?: string; counted?: boolean
}) {
  // Before the first cycle completes there is no measurement, and `0 waiting`
  // would be a zero nobody produced — the same rule the unmeasured-judgement
  // banner applies, one step earlier and at a glance.
  const shown = counted === false ? '—' : n
  return (
    <span className={`text-xs whitespace-nowrap ${tone ?? 'text-fg-muted'}`}
          title={counted === false ? 'Not counted yet — the first cycle has not finished.' : title}>
      <span className="tabular-nums font-semibold">{shown}</span> {label}
    </span>
  )
}

export default function FleetPm({ agents, onExit }: { agents: FleetAgent[]; onExit: () => void }) {
  const [snap, setSnap] = useState<PmSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [terminalAt, setTerminalAt] = useState<number | null>(null)
  const [instructAt, setInstructAt] = useState<number | null>(null)
  const [countdownLeft, setCountdownLeft] = useState<number | null>(null)
  const countdownFor = useRef<number | null>(null)

  const lastInputAt = latestInput(terminalAt, instructAt)

  const load = useCallback(async () => {
    const since = secondsSinceInput(lastInputAt, Date.now())
    const q = since === null ? '' : `?seconds_since_input=${since.toFixed(1)}`
    try {
      const res = await fetch(`/api/fleet/pm${q}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSnap(await res.json())
      setError(null)
    } catch (e) {
      setError(String((e as Error)?.message ?? e))
    }
  }, [lastInputAt])

  useEffect(() => {
    void load()
    const t = setInterval(() => void load(), POLL_MS)
    return () => clearInterval(t)
  }, [load])

  const post = useCallback(async (path: string) => {
    try {
      const res = await fetch(`/api/fleet/pm${path}`, { method: 'POST' })
      if (res.ok) setSnap(await res.json())
    } catch { /* the next poll reports it */ }
  }, [])

  // A keystroke is the evidence of engagement. It cancels a running countdown
  // immediately rather than waiting for the next poll to agree — the poll is
  // seconds away and the switch is not.
  const noteInput = useCallback((where: 'terminal' | 'instruct') => {
    const at = Date.now()
    if (where === 'terminal') setTerminalAt(at)
    else setInstructAt(at)
    setCountdownLeft(null)
    countdownFor.current = null
  }, [])

  const pending = snap?.pending_switch ?? null

  useEffect(() => {
    if (!pending) {
      setCountdownLeft(null)
      countdownFor.current = null
      return
    }
    if (countdownFor.current === pending.pid) return
    countdownFor.current = pending.pid
    setCountdownLeft(COUNTDOWN_MS)
  }, [pending])

  useEffect(() => {
    if (countdownLeft === null) return
    if (countdownLeft <= 0) {
      const pid = countdownFor.current
      countdownFor.current = null
      setCountdownLeft(null)
      if (pid !== null) void post(`/present/${pid}`)
      return
    }
    const t = setTimeout(() => setCountdownLeft(v => (v === null ? null : v - 250)), 250)
    return () => clearTimeout(t)
  }, [countdownLeft, post])

  const presented = snap?.presented ?? null
  const agent = presented ? agents.find(a => a.pid === presented.pid) ?? null : null
  const counts = snap?.counts

  return (
    /* z-[60], not z-40 — MEASURED in the browser, not reasoned about. The app
       shell's sidebar is `z-50`, so at z-40 it sat ON TOP of this overlay and
       clipped the first ~45px of every terminal line (`r event:` for
       `for event:`) while also covering the back/forward controls. Full screen
       has to mean above the shell, or it is not full screen. */
    <div className="fixed inset-0 z-[60] flex flex-col bg-surface-page" data-fleet-pm="on">
      {/* The always-visible bar. Nothing here may scroll away — it is what
          makes the pile behind a full-screen view countable. */}
      <div className="shrink-0 flex items-center gap-3 flex-wrap px-3 py-2 border-b border-surface-line">
        <button
          onClick={() => void post('/back')}
          disabled={!snap?.can_go_back}
          data-fleet-pm-back
          className="text-fg-muted hover:text-fg-strong disabled:opacity-30 disabled:hover:text-fg-muted"
          title="Back to what was presented before. Marks nothing as dealt with."
        >
          <ChevronLeft size={16} />
        </button>
        <button
          onClick={() => void post('/forward')}
          disabled={!snap?.can_go_forward}
          data-fleet-pm-forward
          className="text-fg-muted hover:text-fg-strong disabled:opacity-30 disabled:hover:text-fg-muted"
          title="Forward, as far as the item the queue currently presents."
        >
          <ChevronRight size={16} />
        </button>

        <span className="text-sm text-fg-strong truncate max-w-[22rem]" data-fleet-pm-presented={presented?.pid}>
          {presented
            ? <>{presented.project} <span className="text-fg-muted">/ {presented.label ?? presented.pid}</span></>
            : <span className="text-fg-muted">nothing is presented</span>}
        </span>
        {presented && (
          <span
            className="text-xs text-fg-ghost"
            title={presented.source === 'structural'
              ? 'Measured from the session log — a question tool is open.'
              : 'Judged from the last turn. An opinion, not a measurement.'}
          >
            {presented.source === 'structural' ? 'measured' : 'judged'}
          </span>
        )}

        <span className="ml-auto flex items-center gap-3 flex-wrap">
          {counts && (
            <>
              <Count n={counts.queued} label="waiting" counted={counts.counted} tone={counts.queued > 0 ? 'text-sky-300' : undefined}
                     title="Agents queued behind this one. They do not go away while this screen is frozen." />
              <Count n={counts.idle} label="idle" counted={counts.counted}
                     title="Finished their turn and asked nothing. Counted, never queued." />
              {counts.unclassified > 0 && (
                <Count n={counts.unclassified} label="unclassified" tone="text-amber-400"
                       title="The judgement could not name a class for these. They are not queued, and that is why they are counted here." />
              )}
              {counts.dismissed > 0 && (
                <Count n={counts.dismissed} label="dismissed"
                       title="Dropped without being answered. Counted so a dismissal is not the same as never having been queued." />
              )}
              {counts.not_covered > 0 && (
                <Count n={counts.not_covered} label="not covered" tone="text-amber-400"
                       title="More candidates than one pass may carry. Named rather than truncated silently." />
              )}
            </>
          )}
          <button onClick={onExit} data-fleet-pm-exit
                  className="text-fg-muted hover:text-fg-strong"
                  title="Leave PM mode. No agent is touched.">
            <X size={16} />
          </button>
        </span>
      </div>

      {/* We could not look. NEVER rendered as an empty queue. */}
      {counts && !counts.judgment_measured && (
        <div className="shrink-0 px-3 py-1.5 text-xs text-amber-400 border-b border-surface-line"
             data-fleet-pm-unmeasured>
          ⚠ the judgement for this cycle is unmeasured
          {counts.judgment_reason ? ` — ${counts.judgment_reason}` : ''}. This is not “nothing is
          waiting”: what is on the screen is whatever the previous cycle knew.
        </div>
      )}

      {error && (
        <div className="shrink-0 px-3 py-1.5 text-xs text-red-400 border-b border-surface-line"
             data-fleet-pm-error>
          PM mode could not be read: {error}
        </div>
      )}

      {/* The announced switch. Never shown while the typing window holds —
          the server withholds `pending_switch` in that case. */}
      {pending && countdownLeft !== null && (
        <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 text-xs text-sky-300 border-b border-surface-line"
             data-fleet-pm-countdown={pending.pid}>
          <span>
            switching to <span className="font-semibold">{pending.project}</span>
            {' / '}{pending.label ?? pending.pid} in{' '}
            <span className="tabular-nums">{Math.ceil(countdownLeft / 1000)}s</span>
          </span>
          <span className="text-fg-ghost">— type anything to stay</span>
          <button
            onClick={() => { countdownFor.current = null; setCountdownLeft(null); void post(`/refuse/${pending.pid}`) }}
            data-fleet-pm-refuse={pending.pid}
            className="ml-auto text-fg-muted hover:text-fg-strong"
          >
            stay here
          </button>
        </div>
      )}

      <div className="flex-1 min-h-0 flex flex-col">
        {presented === null ? (
          <div className="flex-1 grid place-items-center text-sm text-fg-muted" data-fleet-pm-empty>
            {/* FOUR states, not three. Caught by looking at the running
                screen: before the first response arrives `counts` is
                undefined, which fell through to the unmeasured branch — so
                the screen said "the judgement is unmeasured — see above"
                with nothing above it. Two fields contradicting each other,
                which is the one thing a passing test suite never notices. */}
            {snap === null
              ? 'Reading PM mode…'
              : snap.cycling
                ? 'Looking at the fleet…'
                : counts && counts.judgment_measured
                  ? 'Nothing is waiting on you.'
                  : 'Nothing is on the screen, and the judgement is unmeasured — see above.'}
          </div>
        ) : agent?.terminal_label ? (
          <FleetTerminal
            key={agent.terminal_label}
            label={agent.terminal_label}
            full
            /* NOT onExit. `FleetTerminal` calls this after it stops an
               agent, and stopping one agent must not end the mode — the
               reader would lose the whole queue as a side effect of an
               action about a single item. Setting it aside is the honest
               mapping: the item stays queued and the mode stays on. */
            onClose={() => void post('/defer')}
            onInput={() => noteInput('terminal')}
          />
        ) : (
          /* No terminal the framework holds. Say so, and offer what does
             exist — an empty frame here would read as "this agent has
             nothing to show" rather than "this surface cannot show it". */
          <div className="flex-1 min-h-0 overflow-auto p-4 space-y-3" data-fleet-pm-no-terminal={presented.pid}>
            <div className="text-sm text-fg-strong">
              {presented.project} / {presented.label ?? presented.pid}
              <span className="text-fg-muted"> · pid {presented.pid}</span>
            </div>
            <div className="text-xs text-amber-400">
              The framework holds no terminal for this agent, so it cannot be shown here. That is a
              limit of this surface, not of the agent — it is running, and it is waiting on you.
            </div>
            {agent
              ? <div onKeyDownCapture={() => noteInput('instruct')}>
                  <FleetInstruct agent={agent} terminalOpen={false} />
                </div>
              : <div className="text-xs text-fg-muted">
                  This agent is queued but was not in the last fleet listing, so there is nothing to
                  address it with right now.
                </div>}
          </div>
        )}
      </div>

      {presented && (
        <div className="shrink-0 flex items-center gap-3 px-3 py-1.5 border-t border-surface-line">
          <span className="text-xs text-fg-ghost">
            blocked {age(Math.max(0, Date.now() / 1000 - presented.blocked_since))} ago
            {presented.presented_count > 1 && ` · shown ${presented.presented_count}×`}
          </span>
          <button onClick={() => void post('/advance')} data-fleet-pm-advance
                  className="ml-auto text-xs text-fg-muted hover:text-fg-strong"
                  title="Move on if this agent has resumed. It will not move on otherwise — an interrupt is not an answer.">
            next if answered
          </button>
          <button onClick={() => void post('/defer')} data-fleet-pm-defer
                  className="text-xs text-fg-muted hover:text-fg-strong"
                  title="Set this aside. It stays queued and comes back lower down.">
            later
          </button>
          <button onClick={() => void post(`/dismiss/${presented.pid}`)} data-fleet-pm-dismiss={presented.pid}
                  className="text-xs text-fg-muted hover:text-red-400"
                  title="Drop this without answering. It is counted, not forgotten.">
            dismiss
          </button>
        </div>
      )}
    </div>
  )
}
