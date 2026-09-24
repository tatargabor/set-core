import { useCallback, useEffect, useState } from 'react'
import { Hourglass } from 'lucide-react'
import { Chip } from './Chip'
import { Panel, PanelRow, PanelTable } from './Panel'
import type { PanelColumn } from './Panel'
import { useDisclosure } from '../lib/useDisclosure'


import type { Waiter, WaitersResponse } from '../lib/fleetTypes'

/**
 * Waiter processes, and which of them have no session left — task 7.13.
 *
 * Placed where the missing-waiter remedy is offered, because that is exactly
 * the moment somebody is about to add to the pile: an instruction that reported
 * `waiters_here: 0` invites installing one, and the debris from the last dozen
 * belongs in the same view rather than a page away.
 *
 * ## Three statuses, and the third is why this is not a boolean
 *
 *  - `orphaned` — its session is gone. This may be removed.
 *  - `live` — its session is running. This must NOT be.
 *  - `undeterminable` — the session could not be read. Listed, treated as live,
 *    never offered. Collapsing it into either neighbour is the only way to get
 *    this wrong, and one direction of that mistake kills a live waiter — after
 *    which the agent it belonged to merely looks quiet, and the next
 *    instruction sent to it sits unread.
 *
 * ## One at a time, and it says what it does
 *
 * There is no bulk endpoint and this component builds no bulk affordance: no
 * "remove all", no select-many, not even a loop behind one button. A cleanup
 * that takes a list is one mistaken list away from killing live waiters. Each
 * removal is confirmed in place and states plainly that it **stops a process**.
 *
 * ## `measured: false` is not an empty list
 *
 * "No orphans" invites installing another waiter; "we could not look" does not.
 * The two render differently and the second never shows a clean list.
 */

/**
 * The columns, declared once.
 *
 * The list used to read `105989 live /a/project/checkout not
 * offered` — four fields run together in one wrapping row, so nothing could be
 * compared down a column and the eye had no edge to follow.
 */
const WAITER_COLUMNS: PanelColumn[] = [
  { key: 'pid', label: 'PID', width: '5rem' },
  { key: 'status', label: 'Status', width: '8rem' },
  { key: 'cwd', label: 'Working directory', width: 'minmax(0,1fr)' },
  { key: 'action', label: 'Action', width: '14rem', align: 'end' },
]

const STATUS_TONE: Record<string, string> = {
  orphaned: 'text-amber-400',
  live: 'text-emerald-400',
  undeterminable: 'text-amber-400',
}

const STATUS_NOTE: Record<string, string> = {
  orphaned: 'its session is gone — this waiter listens for nobody',
  live: 'its session is running — removing it would silence a working agent',
  undeterminable: 'its session could not be read, so it is treated as live and not offered',
}

function WaiterRow({ w, onRemoved }: { w: Waiter; onRemoved: () => void }) {
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const remove = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`/api/fleet/waiters/${w.pid}/remove`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => null)
        // Every refusal carries its reason — "its session is alive" is
        // information for the reader, not an error to swallow.
        setError(String(body?.detail?.reason ?? body?.detail?.error ?? `HTTP ${res.status}`))
        return
      }
      onRemoved()
    } catch (e) {
      setError(String((e as Error)?.message ?? e))
    } finally {
      setBusy(false)
      setConfirming(false)
    }
  }, [w.pid, onRemoved])

  return (
    <>
    <PanelRow data={{ 'data-fleet-waiter': String(w.pid) }}>
      <span className="text-xs text-fg-ghost tabular-nums">{w.pid}</span>
      <span
        className={`text-xs ${STATUS_TONE[w.status] ?? 'text-fg-muted'}`}
        data-fleet-waiter-status={w.status}
        title={STATUS_NOTE[w.status] ?? 'a status this screen does not recognise'}
      >
        {w.status}
      </span>
      {/* The directory and the rooms share one cell: an extra top-level child
          would become an extra COLUMN, and the row would stop lining up with
          its own heading. */}
      <span className="min-w-0 truncate text-xs text-fg-muted" title={w.cwd ?? ''}>
        {w.cwd ?? 'no working directory'}
        {w.rooms && w.rooms.length > 0 && (
          <span className="text-fg-ghost"> · rooms: {w.rooms.join(', ')}</span>
        )}
      </span>
      <span className="text-right">
        {w.removable ? (
          confirming ? (
            <button
              onClick={() => void remove()}
              disabled={busy}
              data-fleet-waiter-confirm={w.pid}
              className="text-xs text-red-400 hover:text-red-300 disabled:opacity-50"
              title="This stops the process. It cannot be undone from here."
            >
              {busy ? 'stopping…' : `sure? this stops process ${w.pid}`}
            </button>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              data-fleet-waiter-remove={w.pid}
              className="text-xs text-fg-muted hover:text-red-400"
              title="Removal stops the process — it is not a tidy-up of a record."
            >
              remove (stops the process)
            </button>
          )
        ) : (
          <span className="text-xs text-fg-ghost" data-fleet-waiter-kept={w.pid}>
            not offered
          </span>
        )}
      </span>
    </PanelRow>
    {/* Full width, outside the grid: a refusal is a sentence, and a sentence
        squeezed into the action column is a sentence nobody reads. */}
    {error && <div className="px-1 pb-1 text-xs text-red-400">refused: {error}</div>}
    </>
  )
}

export default function FleetWaiters({ compact }: { compact?: boolean }) {
  const [data, setData] = useState<WaitersResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Shared with every other header opener, so this trigger finally has a stable
  // open-state marker: its test used to find it as "the only button" in an
  // isolated render, which is not a selector so much as an accident.
  const { open, toggle, close, triggerData } = useDisclosure('waiters')

  const load = useCallback(() => {
    fetch('/api/fleet/waiters')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d: WaitersResponse) => { setData(d); setError(null) })
      .catch(e => setError(String(e.message ?? e)))
  }, [])

  useEffect(() => { load() }, [load])

  if (error) {
    return <div className="text-xs text-red-400" data-fleet-waiters="error">waiters could not be read: {error}</div>
  }
  if (!data) {
    return <div className="text-xs text-fg-muted" data-fleet-waiters="loading">reading the waiters…</div>
  }

  // We could not look. Never a clean list, and never a zero.
  if (!data.measured) {
    return (
      <div className="text-xs text-amber-400" data-fleet-waiters="unmeasured">
        ⚠ the waiters could not be measured{data.reason ? ` — ${data.reason}` : ''}. This is not
        “there are none”: nothing is known about what is listening.
      </div>
    )
  }

  const orphans = data.waiters.filter(w => w.status === 'orphaned')
  const undeterminable = data.waiters.filter(w => w.status === 'undeterminable')

  return (
    <div data-fleet-waiters="measured" data-fleet-waiters-orphaned={orphans.length}>
      {/* Mark and number — see `Chip`. The ORPHAN count is what the chip shows
          when there is one: an orphan is the only waiter anybody acts on, and a
          strip that shows the harmless total beside it would spend its one
          number on the calmer fact. The colour carries which one it is. */}
      <Chip
        jump="waiters"
        onClick={toggle}
        data={triggerData}
        tone={orphans.length > 0 || undeterminable.length > 0 ? 'text-amber-400' : 'text-fg-muted'}
        mark={<Hourglass size={13} strokeWidth={1.75} aria-hidden />}
        count={orphans.length > 0 ? orphans.length : data.waiters.length}
        // No caret: a caret promises the row is about to grow, and nothing
        // grows any more — the list opens as a panel over the page.
        trailing={undeterminable.length > 0
          ? <span className="text-amber-400">+{undeterminable.length}?</span>
          : undefined}
        title={[
          orphans.length > 0
            ? `${orphans.length} orphaned waiter(s) of ${data.waiters.length}`
            : `${data.waiters.length} waiter(s), none orphaned`,
          undeterminable.length > 0 ? `${undeterminable.length} undeterminable` : null,
        ].filter(Boolean).join(' · ')}
        label={[
          orphans.length > 0
            ? `${orphans.length} orphaned waiters`
            : `${data.waiters.length} waiters, none orphaned`,
          undeterminable.length > 0 ? `${undeterminable.length} undeterminable` : null,
        ].filter(Boolean).join(', ')}
      />

      {open && (
        <Panel
          icon={<Hourglass size={13} strokeWidth={1.75} className="shrink-0 text-fg-muted" aria-hidden />}
          title="Waiters"
          counts={`${data.waiters.length} measured`}
          headerExtra={orphans.length > 0 ? (
            <span className="text-xs text-amber-300" data-fleet-waiters-orphaned-mark={orphans.length}>
              {orphans.length} orphaned
            </span>
          ) : undefined}
          onClose={close}
          data={{ 'data-fleet-waiters-panel': String(data.waiters.length) }}
          /*
            NO footer. Every action here belongs to one row — an orphan, one at
            a time — and a footer is exactly where a bulk act would arrive by
            accident. A structural test already asserts the absence of one
            (`fleetInstructSurface.test.tsx:355`).
          */
        >
          {data.waiters.length === 0 ? (
            <div className="text-xs text-fg-muted">
              measured: no waiter process is running on this machine
            </div>
          ) : (
            <PanelTable columns={WAITER_COLUMNS}>
              {data.waiters.map(w => (
                <WaiterRow key={w.pid} w={w} onRemoved={load} />
              ))}
            </PanelTable>
          )}
          {!compact && (
            <div className="pt-2 text-xs text-fg-ghost">
              Only an orphan is offered, and only one at a time — there is deliberately no bulk
              removal. Removing a live waiter is invisible: its agent merely looks quiet.
            </div>
          )}
        </Panel>
      )}
    </div>
  )
}
