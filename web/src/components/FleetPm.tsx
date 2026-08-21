import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, X } from 'lucide-react'

import { age } from '../lib/fleetAge'
import { COUNTDOWN_MS, secondsSinceInput } from '../lib/fleetPm'
import type { PmSnapshot } from '../lib/fleetPm'

/**
 * PM mode — a STRIP that drives the fleet screen, not a screen of its own.
 *
 * ## The correction this file exists because of
 *
 * The first build made this a full-screen overlay. Rejected by the user on
 * 2026-08-20, looking at it: *"azt hittem ugyanúgy meghagyja a felületet, csak
 * az agent view-ba teszi be az aktuálisat. ehelyett full screen használhatatlant
 * csinált."*
 *
 * They were right, and the reason is worth keeping: the overlay threw away the
 * project column, the agent tabs, the instruct box, the terminal controls and
 * the docks — every affordance that makes an agent workable — in order to show
 * one terminal. For an agent the framework holds no terminal for, what was left
 * was three lines of text on an otherwise blank page.
 *
 * So this mode selects; it does not replace. The queue decides WHICH agent the
 * fleet screen is showing, and the fleet screen stays the fleet screen.
 *
 * ## What the strip must carry, and why it cannot be smaller
 *
 * Everything the reader would otherwise have to go looking for: what is queued
 * behind this item, what is merely idle, whether this cycle's judgement could be
 * made at all, and the way out. The mode names itself for the same reason — the
 * toggle that switched it on is elsewhere on the screen, and a ✕ alone reads as
 * "close this", not "leave the mode".
 */

const POLL_MS = 4000

function Count({ n, label, tone, title, counted }: {
  n: number; label: string; tone?: string; title?: string; counted?: boolean
}) {
  // Before the first cycle completes there is no measurement, and `0 waiting`
  // would be a zero nobody produced.
  const shown = counted === false ? '—' : n
  return (
    <span className={`text-xs whitespace-nowrap ${tone ?? 'text-fg-muted'}`}
          title={counted === false ? 'Not counted yet — the first cycle has not finished.' : title}>
      <span className="tabular-nums font-semibold">{shown}</span> {label}
    </span>
  )
}

export default function FleetPm({ onPresent, onExit, lastInputAt }: {
  /** Called when the queue changes which agent should be on screen. */
  onPresent: (pid: number) => void
  onExit: () => void
  /** When the reader last typed anywhere in the fleet panel, or null. */
  lastInputAt: number | null
}) {
  const [snap, setSnap] = useState<PmSnapshot | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [countdownLeft, setCountdownLeft] = useState<number | null>(null)
  const countdownFor = useRef<number | null>(null)
  const presentedRef = useRef<number | null>(null)
  const inputRef = useRef<number | null>(lastInputAt)
  inputRef.current = lastInputAt

  const load = useCallback(async () => {
    // Read through a ref rather than a dependency: `lastInputAt` changes on
    // every keystroke, and a poll that restarts on each one would hammer the
    // endpoint exactly while the reader is busy.
    const since = secondsSinceInput(inputRef.current, Date.now())
    const q = since === null ? '' : `?seconds_since_input=${since.toFixed(1)}`
    try {
      const res = await fetch(`/api/fleet/pm${q}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSnap(await res.json())
      setError(null)
    } catch (e) {
      setError(String((e as Error)?.message ?? e))
    }
  }, [])

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

  // Drive the fleet screen. Only on a CHANGE — asking the page to jump to the
  // agent it is already showing on every poll would fight the reader's own
  // navigation four times a minute.
  const presented = snap?.presented ?? null
  useEffect(() => {
    if (!presented) return
    if (presentedRef.current === presented.pid) return
    presentedRef.current = presented.pid
    onPresent(presented.pid)
  }, [presented, onPresent])

  const pending = snap?.pending_switch ?? null

  // A keystroke cancels a running countdown at once rather than waiting for the
  // next poll to agree: the poll is seconds away and the switch is not.
  useEffect(() => {
    if (lastInputAt === null) return
    setCountdownLeft(null)
    countdownFor.current = null
  }, [lastInputAt])

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

  const counts = snap?.counts

  return (
    <div className="shrink-0 border-b border-surface-line" data-fleet-pm="on">
      <div className="flex items-center gap-2 flex-wrap px-4 md:px-6 py-1.5">
        <span
          className="text-xs text-sky-300 border border-sky-400/40 rounded px-1.5 py-0.5 shrink-0"
          data-fleet-pm-label
          title="PM mode is on. The queue decides which agent this screen is showing."
        >
          PM mode
        </span>

        <button
          onClick={() => void post('/back')}
          disabled={!snap?.can_go_back}
          data-fleet-pm-back
          className="text-fg-muted hover:text-fg-strong disabled:opacity-30 disabled:hover:text-fg-muted"
          title="Back to what was presented before. Marks nothing as dealt with."
        >
          <ChevronLeft size={14} />
        </button>
        <button
          onClick={() => void post('/forward')}
          disabled={!snap?.can_go_forward}
          data-fleet-pm-forward
          className="text-fg-muted hover:text-fg-strong disabled:opacity-30 disabled:hover:text-fg-muted"
          title="Forward, as far as the item the queue currently presents."
        >
          <ChevronRight size={14} />
        </button>

        <span className="text-xs text-fg-strong truncate max-w-[20rem]" data-fleet-pm-presented={presented?.pid}>
          {presented
            ? <>{presented.project} <span className="text-fg-muted">/ {presented.label ?? presented.pid}</span></>
            : snap === null
              ? <span className="text-fg-muted">reading PM mode…</span>
              : snap.cycling
                ? <span className="text-fg-muted">looking at the fleet…</span>
                : counts && counts.judgment_measured
                  ? <span className="text-fg-muted">nothing is waiting on you</span>
                  : <span className="text-fg-muted">nothing is presented</span>}
        </span>
        {presented && (
          <>
            <span
              className="text-xs text-fg-ghost shrink-0"
              title={presented.source === 'structural'
                ? 'Measured from the session log — a question tool is open.'
                : 'Judged from the last turn. An opinion, not a measurement.'}
            >
              {presented.source === 'structural' ? 'measured' : 'judged'}
            </span>
            <span className="text-xs text-fg-ghost shrink-0">
              blocked {age(Math.max(0, Date.now() / 1000 - presented.blocked_since))} ago
              {presented.presented_count > 1 && ` · shown ${presented.presented_count}×`}
            </span>
          </>
        )}

        <span className="ml-auto flex items-center gap-3 flex-wrap">
          {counts && (
            <>
              <Count n={counts.queued} label="waiting" counted={counts.counted}
                     tone={counts.queued > 0 ? 'text-sky-300' : undefined}
                     title="Agents queued behind this one." />
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
          {presented && (
            <>
              <button onClick={() => void post('/advance')} data-fleet-pm-advance
                      className="text-xs text-fg-muted hover:text-fg-strong"
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
            </>
          )}
          <button onClick={onExit} data-fleet-pm-exit
                  className="text-xs text-fg-muted hover:text-fg-strong inline-flex items-center gap-1 shrink-0"
                  title="Leave PM mode. The screen stays exactly as it is; no agent is touched.">
            <X size={14} />
            exit
          </button>
        </span>
      </div>

      {/* We could not look. NEVER rendered as an empty queue. */}
      {counts && !counts.judgment_measured && (
        <div className="px-4 md:px-6 pb-1.5 text-xs text-amber-400" data-fleet-pm-unmeasured>
          ⚠ the judgement for this cycle is unmeasured
          {counts.judgment_reason ? ` — ${counts.judgment_reason}` : ''}. This is not “nothing is
          waiting”: the screen below shows whatever the previous cycle knew.
        </div>
      )}

      {error && (
        <div className="px-4 md:px-6 pb-1.5 text-xs text-red-400" data-fleet-pm-error>
          PM mode could not be read: {error}
        </div>
      )}

      {/*
        The announced switch, IN THE MIDDLE OF THE SCREEN — moved there
        2026-08-21: *"a csík a képernyő közepén kellene legyen, én nem láttam
        még"*.

        It lived in this strip, at the top of the window, as one line of small
        text and a 4 px bar. That is where the PM controls are, so it looked
        like the right place — and it is the wrong one for the same reason the
        bar exists at all: the reader is looking at the AGENT, in the middle of
        the screen, and a warning at the edge of the field of view is a warning
        nobody sees. The user had never once seen it.

        So it is placed over what is being looked at, and only while it is
        running: it appears for the announced seconds and leaves. Nothing about
        the screen underneath changes, and `pointer-events-none` on the backdrop
        means a click aimed past it lands where it was aimed — which is also
        what cancels the switch, since the panel counts a press as the reader
        being here.

        ⚠ It COVERS things while it is up, which `ui-quality.md` says a compact
        layout may never do to a failure. The reason it is allowed: this is not
        compaction, it is a five-second announcement of something that will
        take the whole screen anyway, and the thing it covers is exactly what
        the reader is about to lose. It is also the only element on this screen
        that gets to sit in the middle — if a second one is ever added, this
        argument stops working for both.
      */}
      {pending && countdownLeft !== null && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
          data-fleet-pm-countdown={pending.pid}
        >
          <div
            /* The card itself takes the pointer, so the "stay here" button is
               clickable — and a press anywhere on it means the same thing as a
               press anywhere else on the panel: the reader is here. */
            className="pointer-events-auto rounded-lg border border-sky-400/50 bg-surface-raised/95 shadow-xl px-5 py-4 w-[22rem] max-w-[90vw] backdrop-blur-sm"
            onPointerDown={() => { countdownFor.current = null; setCountdownLeft(null); void post(`/refuse/${pending.pid}`) }}
          >
            {/*
              BOTH names, and the agent's is the loud one — asked for
              2026-08-21: *"ne csak a projektet írja ki hova vált hanem az agent
              nevét is"*.

              The agent's label was already here and it was `text-xs
              text-fg-muted` under a semibold project, so it read as a caption
              on the project rather than as the thing being switched to — the
              reader saw a project name and nothing else. The project answers
              *where*, the label answers *which one*, and the second is the
              identity everything else on this screen is keyed by (the tab, the
              dock, the terminal). It gets the weight.

              `label ?? pid` because an agent the framework holds no terminal
              for has no label, and a blank line where a name belongs reads as
              a missing agent rather than as an unnamed one.
            */}
            <div className="text-xs text-fg-muted">
              switching to <span className="text-fg-strong">{pending.project}</span>
            </div>
            <div className="text-base font-semibold text-sky-300 truncate" title={String(pending.label ?? pending.pid)}>
              {pending.label ?? `pid ${pending.pid}`}
            </div>
            <div className="mt-3 flex items-end gap-3">
              {/* The number stays with the bar, and it is the big thing now:
                  a bar says "soon", only a number says HOW soon. One visual
                  weight per meaning — the seconds are the fact, the bar is
                  the movement. */}
              <span className="text-3xl leading-none tabular-nums text-sky-300">
                {Math.ceil(countdownLeft / 1000)}<span className="text-base">s</span>
              </span>
              <div className="flex-1 pb-1">
                {/*
                  The bar that runs out — asked for 2026-08-21: *"csak kell bele
                  a csík ami megy vissza"*.

                  Driven off the SAME `countdownLeft` the switch fires on, so it
                  cannot show time the timer does not have. A second source (a
                  CSS animation with its own duration) would be a copy of the
                  deadline, and it would drift exactly when a keystroke cancels
                  the switch — the bar would keep running down toward a switch
                  nobody is going to make.
                */}
                <div
                  className="h-1.5 bg-sky-400/20 rounded-full overflow-hidden"
                  role="progressbar"
                  aria-label="time left before the screen switches"
                  aria-valuemin={0}
                  aria-valuemax={Math.round(COUNTDOWN_MS / 1000)}
                  aria-valuenow={Math.ceil(countdownLeft / 1000)}
                  data-fleet-pm-countdown-bar={Math.max(0, Math.round((countdownLeft / COUNTDOWN_MS) * 100))}
                >
                  <div
                    className="h-full bg-sky-400 transition-[width] duration-200 ease-linear"
                    style={{ width: `${Math.max(0, Math.min(100, (countdownLeft / COUNTDOWN_MS) * 100))}%` }}
                  />
                </div>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2">
              <span className="text-xs text-fg-ghost">type or click anything to stay</span>
              <button
                onClick={() => { countdownFor.current = null; setCountdownLeft(null); void post(`/refuse/${pending.pid}`) }}
                data-fleet-pm-refuse={pending.pid}
                className="ml-auto text-xs text-fg-muted hover:text-fg-strong border border-surface-line rounded px-2 py-1"
              >
                stay here
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
