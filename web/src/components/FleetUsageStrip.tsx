/**
 * The account quota, on the fleet header — one row per account, two stripes per
 * window.
 *
 * The cache-heat marks on the tabs below say what a keystroke costs. This says
 * how much is left to spend at all, and until now it existed only in a separate
 * desktop window that nobody has open while watching the fleet. Measured
 * 2026-08-27: one account stood at 96 % of its 7-day window, labelled `critical`
 * by the service itself, and nothing on this screen could have said so.
 *
 * ## It fetches its own data, and that is deliberate
 *
 * The header must render whether or not this measurement arrives. Holding the
 * snapshot here rather than in the page means a slow or failing usage request
 * cannot delay the counts, the project column, or the agent grid — the strip
 * simply says it has nothing yet.
 *
 * ## Collapsing must not hide a red account
 *
 * Any layout that hides something creates a place a broken thing can sit while
 * the screen looks calm. So the collapsed strip keeps the critical count where
 * the reader is standing; only the detail folds away.
 */

import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Gauge, TriangleAlert } from 'lucide-react'

import { stripState, type AccountRow, type UsageSnapshot, type WindowMark } from '../lib/fleetUsageBars'

/** Every 30 s. The server polls its own upstream once a minute; this only reads. */
const READ_INTERVAL_MS = 30_000

/**
 * One window: the consumed stripe above, the elapsed stripe below.
 *
 * The pair is the measurement. 60 % consumed one hour into a five-hour window is
 * a problem and 60 % four hours in is not, and no single bar can say which.
 */
function WindowBar({ mark }: { mark: WindowMark }) {
  if (mark.kind === 'unmeasured') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-400 shrink-0"
            data-fleet-usage-window="unmeasured" title={mark.title}>
        {mark.label} ?
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 shrink-0"
          data-fleet-usage-window="measured"
          data-fleet-usage-critical={mark.critical ? 'yes' : undefined}
          data-fleet-usage-consumed={mark.consumed.toFixed(3)}
          data-fleet-usage-elapsed={mark.elapsed === null ? 'unknown' : mark.elapsed.toFixed(3)}
          title={mark.title}>
      <span className="text-xs text-fg-muted tabular-nums">{mark.label}</span>
      {/* 4 px stripes with a 1 px gap inside an 11 px box. The first build drew
          them 3 px tall inside 9 px and they read on screen as ONE bar — the pair
          IS the measurement, so a reader who cannot see two stripes is left with
          the single-bar reading this strip exists to replace. Found by looking at
          it; no assertion about fractions could have. */}
      <span className="relative inline-block h-[11px] w-20 border border-surface-line align-middle">
        {/* Consumed — the stripe whose colour the SERVICE chose. */}
        <span className={`absolute left-0 top-0 h-[4px] ${mark.tone}`}
              style={{ width: `${mark.consumed * 100}%` }} />
        {/* Elapsed — the only figure computed in the browser, because it moves
            every second and would otherwise be as stale as the last poll. */}
        {mark.elapsed !== null && (
          <span className="absolute left-0 top-[5px] h-[4px] bg-fg-ghost"
                style={{ width: `${mark.elapsed * 100}%` }} />
        )}
      </span>
      <span className="text-xs text-fg-muted tabular-nums">
        {Math.round(mark.consumed * 100)}%
      </span>
    </span>
  )
}

function Row({ row }: { row: AccountRow }) {
  return (
    <div className="flex items-center gap-3 flex-wrap"
         data-fleet-usage-account={row.name}
         data-fleet-usage-state={row.state}>
      <span className="text-xs text-fg-muted truncate max-w-[14rem]" title={row.name}>
        {row.active ? '● ' : ''}{row.name}
      </span>
      {row.windows.map((w, i) => <WindowBar key={i} mark={w} />)}
      {row.note && (
        <span className="text-xs text-amber-400" data-fleet-usage-note={row.state}>
          {row.note}
        </span>
      )}
    </div>
  )
}

export default function FleetUsageStrip() {
  const [snapshot, setSnapshot] = useState<UsageSnapshot | null>(null)
  const [open, setOpen] = useState(true)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    let cancelled = false
    const read = () => {
      fetch('/api/usage/accounts')
        .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then(d => { if (!cancelled) { setSnapshot(d); setNow(Date.now()) } })
        // A failed read leaves the last snapshot standing: a true-but-old
        // measurement beats none, and its age is what the strip reports.
        .catch(() => { if (!cancelled) setNow(Date.now()) })
    }
    read()
    const t = setInterval(read, READ_INTERVAL_MS)
    return () => { cancelled = true; clearInterval(t) }
  }, [])

  const state = stripState(snapshot, now)

  if (state.kind !== 'ready') {
    return (
      <div className="px-4 md:px-6 py-1 border-b border-surface-line shrink-0 flex items-center gap-2"
           data-fleet-usage={state.kind}>
        <Gauge size={13} strokeWidth={1.75} className="text-fg-ghost" aria-hidden />
        <span className="text-xs text-fg-ghost">{state.note}</span>
      </div>
    )
  }

  // Split before rendering: an account that ANSWERED gets a row, and the ones
  // that did not share a single line. Rows are what carry figures; a row with no
  // figure and no possibility of one is a sentence, not a row.
  const answering = state.rows.filter(r => r.state !== 'unreachable')
  const silent = state.rows.filter(r => r.state === 'unreachable')

  return (
    <div className="px-4 md:px-6 py-1 border-b border-surface-line shrink-0"
         data-fleet-usage="ready"
         data-fleet-usage-rows={state.rows.length}
         data-fleet-usage-open={open ? 'open' : 'collapsed'}>
      <div className="flex items-center gap-2 flex-wrap">
        <button type="button"
                onClick={() => setOpen(!open)}
                aria-pressed={open}
                aria-label={`account usage ${open ? 'shown' : 'collapsed'}`}
                title="Account quota — how much of each rolling window is spent."
                className="inline-flex items-center gap-1 text-xs text-fg-muted hover:text-fg-strong shrink-0"
                data-fleet-usage-toggle={open ? 'open' : 'collapsed'}>
          {open
            ? <ChevronDown size={13} strokeWidth={1.75} aria-hidden />
            : <ChevronRight size={13} strokeWidth={1.75} aria-hidden />}
          <Gauge size={13} strokeWidth={1.75} aria-hidden />
          <span className="tabular-nums">{state.rows.length}</span>
        </button>

        {/* Survives the collapse, because a hidden failure is the one thing
            compacting must never produce. */}
        {state.criticalCount > 0 && (
          <span className="inline-flex items-center gap-1 text-xs text-red-400 shrink-0"
                data-fleet-usage-critical-count={state.criticalCount}
                title={`${state.criticalCount} window(s) the service calls critical`}
                aria-label={`${state.criticalCount} critical usage window(s)`}>
            <TriangleAlert size={13} strokeWidth={1.75} aria-hidden />
            {state.criticalCount}
          </span>
        )}

        {/* A stale screen is readable only if the reader can see how stale. */}
        {state.stale && (
          <span className="text-xs text-amber-400 shrink-0"
                data-fleet-usage-stale={state.measuredAt}
                title={`This is the state measured at ${new Date(state.measuredAt).toLocaleString()}, not now.`}>
            {new Date(state.measuredAt).toLocaleTimeString()}
          </span>
        )}

        {open && answering.length === 1 && <Row row={answering[0]} />}
      </div>

      {open && answering.length > 1 && (
        <div className="mt-0.5 flex flex-col gap-0.5">
          {answering.map(row => <Row key={`${row.kind}:${row.name}`} row={row} />)}
        </div>
      )}

      {/* ONE cause, named once — the same lesson the header's owner chip already
          carries. Three expired credentials rendered as three identical
          sentences, which is three copies of one fact taking three rows on the
          landing screen. Found by looking at the built screen. */}
      {open && silent.length > 0 && (
        <div className="text-xs text-amber-400 mt-0.5"
             data-fleet-usage-silent={silent.length}
             title={`${silent.map(r => r.name).join('\n')}\n\nEach answered nothing — the stored credential has most likely expired.`}>
          {silent.length} account{silent.length > 1 ? 's' : ''} did not answer — the credentials have most likely expired
        </div>
      )}
    </div>
  )
}
