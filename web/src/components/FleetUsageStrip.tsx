/**
 * The account quota, on the fleet header.
 *
 * The cache-heat marks on the tabs below say what a keystroke costs. This says
 * how much is left to spend at all, and until this shipped it existed only in a
 * separate desktop window that nobody has open while watching the fleet.
 * Measured 2026-08-27: one account stood at 96 % of its 7-day window, labelled
 * `critical` by the service itself, and nothing on this screen could have said
 * so.
 *
 * ## Compact by default — and the reason is a measurement, not taste
 *
 * The first build put a full row per account under the header: names, labels,
 * sentences, 97 px of landing screen for six accounts. The user looked at it and
 * asked for the opposite (*"ez nagyon sok helyet elvisz ki kellene tenni csak a
 * mukodo statusz barokat jobbra felul optimalizalva. szovegek nem kellenek"*) —
 * the same request that turned this header's counts into icons and numbers on
 * 2026-08-19.
 *
 * So the resting state is **bars only**, on the header's own line, pushed right:
 * two stripes per account-wide window, no name, no percentage, no sentence. What
 * the words carried lives on the tooltip, and the detail is one click away.
 *
 * ## What compacting may NOT do, and this is the load-bearing half
 *
 * Every layout that hides something creates a place a broken thing can sit while
 * the screen looks calm. So the three not-a-number states do not vanish with the
 * words — they become icons and counts, which is what the request asked for:
 *
 * - `⚠ n` — windows reported critical (by their service, or banded at
 *   measurement for the source that states none — the screen does not know
 *   which, so it claims neither)
 * - `? n` — accounts that answered and carried no figures (never an empty bar:
 *   that reads as "nothing consumed", which is the opposite of what is known)
 * - `⊘ n` — accounts that did not answer at all, one cause named once
 *
 * ## It fetches its own data
 *
 * The header must render whether or not this measurement arrives, so a slow or
 * failing usage read cannot delay the counts, the project column, or the grid.
 * The same read runs again immediately after a confirmed purge, so the removed
 * rows leave the screen on the act, not on the next poll.
 */

import { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Gauge, TriangleAlert, Unplug } from 'lucide-react'

import {
  headlineWindows, rowTitle, shortLabel, stripState,
  type AccountRow, type UsageSnapshot, type WindowMark,
} from '../lib/fleetUsageBars'

/** Every 30 s. The server polls its own upstream once a minute; this only reads. */
const READ_INTERVAL_MS = 30_000

/**
 * One window: the consumed stripe above, the elapsed stripe below.
 *
 * The pair is the measurement. 60 % consumed one hour into a five-hour window is
 * a problem and 60 % four hours in is not, and no single bar can say which.
 *
 * The stripes are 4 px with a 1 px gap. The first build drew them 3 px inside a
 * 9 px box and they read on screen as ONE bar — which is exactly the single-bar
 * reading this pair exists to replace. Found by looking at it; no assertion
 * about fractions could have.
 */
function WindowBar({ mark, compact }: { mark: WindowMark; compact?: boolean }) {
  if (mark.kind === 'unmeasured') {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-400 shrink-0"
            data-fleet-usage-window="unmeasured" title={mark.title}>
        {mark.label} ?
      </span>
    )
  }
  return (
    <span className={`inline-flex items-center shrink-0 ${compact ? '' : 'gap-1.5'}`}
          data-fleet-usage-window="measured"
          data-fleet-usage-critical={mark.critical ? 'yes' : undefined}
          data-fleet-usage-consumed={mark.consumed.toFixed(3)}
          data-fleet-usage-elapsed={mark.elapsed === null ? 'unknown' : mark.elapsed.toFixed(3)}
          title={mark.title}>
      {!compact && <span className="text-xs text-fg-muted tabular-nums">{mark.label}</span>}
      <span className={`relative inline-block h-[11px] border border-surface-line align-middle ${
        compact ? 'w-11' : 'w-20'}`}>
        {/* Consumed — the stripe whose colour the measurement chose. */}
        <span className={`absolute left-0 top-0 h-[4px] ${mark.tone}`}
              style={{ width: `${mark.consumed * 100}%` }} />
        {/* Elapsed — the only figure computed in the browser, because it moves
            every second and would otherwise be as stale as the last poll. */}
        {mark.elapsed !== null && (
          <span className="absolute left-0 top-[5px] h-[4px] bg-fg-ghost"
                style={{ width: `${mark.elapsed * 100}%` }} />
        )}
      </span>
      {!compact && (
        <span className="text-xs text-fg-muted tabular-nums">
          {Math.round(mark.consumed * 100)}%
        </span>
      )}
    </span>
  )
}

/** One account's account-wide windows, wordless, with everything on the tooltip. */
function CompactAccount({ row }: { row: AccountRow }) {
  const windows = headlineWindows(row)
  if (windows.length === 0) return null
  return (
    <span className="inline-flex items-center gap-1 shrink-0"
          data-fleet-usage-compact={row.name}
          title={rowTitle(row)}>
      <span className="text-[10px] text-fg-ghost shrink-0"
            data-fleet-usage-compact-label={row.name}>
        {shortLabel(row.name)}
      </span>
      {windows.map((w, i) => <WindowBar key={i} mark={w} compact />)}
    </span>
  )
}

/** The expanded form: the account named, every window drawn, the figures shown. */
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

/** An icon and a count. No sentence — the sentence is the title. */
function Mark({ icon, count, tone, title, label, mark }: {
  icon: React.ReactNode; count: number; tone: string
  title: string; label: string; mark: string
}) {
  if (count === 0) return null
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs tabular-nums shrink-0 ${tone}`}
          {...{ [`data-fleet-usage-${mark}`]: String(count) }}
          title={title} aria-label={label}>
      {icon}{count}
    </span>
  )
}

export default function FleetUsageStrip() {
  const [snapshot, setSnapshot] = useState<UsageSnapshot | null>(null)
  // Compact at rest. The detail is one click away, and nothing that is WRONG
  // waits behind that click — the marks beside the bars carry it either way.
  const [open, setOpen] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  // A confirmed purge bumps this, which re-runs the read effect: the removed
  // rows leave the screen on the act, not on the next poll.
  const [purgeTick, setPurgeTick] = useState(0)
  const [purging, setPurging] = useState(false)
  const [purgeError, setPurgeError] = useState<string | null>(null)

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
  }, [purgeTick])

  const state = stripState(snapshot, now)

  // Nothing to draw yet. One muted glyph on the header's right — no sentence,
  // and no space taken from the counts that ARE measured.
  if (state.kind !== 'ready') {
    return (
      <span className="ml-auto inline-flex items-center gap-1 shrink-0"
            data-fleet-usage={state.kind} title={state.note}
            aria-label={state.note}>
        <Gauge size={13} strokeWidth={1.75} className="text-fg-ghost" aria-hidden />
        <span className="text-xs text-fg-ghost">?</span>
      </span>
    )
  }

  // The purge offer. Only the accounts the measurement could not reach are
  // named — the server re-checks that guard against ITS current snapshot, so a
  // screen that has gone stale cannot delete a healthy credential. The wording
  // says "did not answer", never "expired": unreachable is also what a network
  // failure looks like, and the confirmation is the human decision that stands
  // in for that missing knowledge.
  const silentRows = state.rows.filter(r => r.state === 'unreachable')
  const purge = () => {
    if (silentRows.length === 0 || purging) return
    const names = silentRows.map(r => r.name)
    const confirmed = window.confirm(
      `Remove ${names.length} account${names.length > 1 ? 's' : ''} that did not answer?\n\n`
      + names.join('\n')
      + '\n\nTheir stored credentials will be deleted from this machine.',
    )
    if (!confirmed) return
    setPurging(true)
    setPurgeError(null)
    fetch('/api/usage/accounts/purge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        accounts: silentRows.map(r => ({ kind: r.kind, name: r.name })),
      }),
    })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json() })
      .then(() => setPurgeTick(t => t + 1))
      .catch(() => setPurgeError('the purge did not go through — nothing was refreshed'))
      .finally(() => setPurging(false))
  }

  return (
    <span className="ml-auto inline-flex items-center gap-3 shrink-0"
          data-fleet-usage="ready"
          data-fleet-usage-rows={state.rows.length}
          data-fleet-usage-open={open ? 'open' : 'collapsed'}>
      {/* The bars themselves — the working accounts, and only those. */}
      {state.measuredRows.map(row => <CompactAccount key={`${row.kind}:${row.name}`} row={row} />)}

      {/* The three states that have no bar. Icons and counts, so compacting the
          words cannot compact away a failure with them. */}
      <span className="inline-flex items-center gap-2 shrink-0">
        <Mark mark="critical-count" count={state.criticalCount} tone="text-red-400"
              icon={<TriangleAlert size={13} strokeWidth={1.75} aria-hidden />}
              title={`${state.criticalCount} window(s) over the critical threshold`}
              label={`${state.criticalCount} critical usage window(s)`} />
        <Mark mark="unmeasured-count" count={state.unmeasuredCount} tone="text-amber-400"
              icon={<span aria-hidden>?</span>}
              title={`${state.unmeasuredCount} account(s) answered and carried no figures — not measured, which is not the same as nothing consumed`}
              label={`${state.unmeasuredCount} account(s) answered with no figures`} />
        <Mark mark="silent" count={state.silentCount} tone="text-amber-400"
              icon={<Unplug size={13} strokeWidth={1.75} aria-hidden />}
              title={`${state.silentCount} account(s) did not answer — a dead credential looks the same as a network failure from here`}
              label={`${state.silentCount} account(s) did not answer`} />
        {/* A stale screen is readable only if the reader can see how stale. */}
        {state.stale && (
          <span className="text-xs text-amber-400 tabular-nums shrink-0"
                data-fleet-usage-stale={state.measuredAt}
                title={`This is the state measured at ${new Date(state.measuredAt).toLocaleString()}, not now.`}>
            {new Date(state.measuredAt).toLocaleTimeString()}
          </span>
        )}
      </span>

      <button type="button"
              onClick={() => setOpen(!open)}
              aria-pressed={open}
              aria-label={`account usage detail ${open ? 'shown' : 'hidden'}`}
              title="Account quota — how much of each rolling window is spent. Click for the accounts by name."
              className="inline-flex items-center text-fg-muted hover:text-fg-strong shrink-0"
              data-fleet-usage-toggle={open ? 'open' : 'collapsed'}>
        {open
          ? <ChevronDown size={13} strokeWidth={1.75} aria-hidden />
          : <ChevronRight size={13} strokeWidth={1.75} aria-hidden />}
      </button>

      {/* The detail, on its own layer so it cannot push the header around. Every
          account by name, every window including the model-scoped ones, and the
          one line naming whatever could not be measured. */}
      {open && (
        <div className="absolute right-4 md:right-6 top-full mt-1 z-20 flex flex-col gap-0.5
                        rounded border border-surface-line bg-surface-raised px-3 py-2 shadow-lg"
             data-fleet-usage-detail={state.rows.length}>
          {state.rows.filter(r => r.state !== 'unreachable').map(row => (
            <Row key={`${row.kind}:${row.name}`} row={row} />
          ))}
          {state.silentCount > 0 && (
            <div className="text-xs text-amber-400"
                 data-fleet-usage-silent={state.silentCount}
                 title={silentRows.map(r => r.name).join('\n')}>
              {state.silentCount} account{state.silentCount > 1 ? 's' : ''} did not answer
              <button type="button" onClick={purge} disabled={purging}
                      className="ml-2 underline decoration-dotted text-fg-muted hover:text-fg-strong
                                 disabled:opacity-50 shrink-0"
                      data-fleet-usage-purge={purging ? 'busy' : 'ready'}
                      aria-label="remove the accounts that did not answer, and their stored credentials"
                      title="Remove these accounts from this machine. Their stored credentials will be deleted.">
                {purging ? 'purging…' : 'purge'}
              </button>
              {purgeError && (
                <span className="ml-2 text-red-400" data-fleet-usage-purge-error="yes"
                      title={purgeError}>
                  {purgeError}
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </span>
  )
}
