import { useCallback, useEffect, useState } from 'react'

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
    <li className="flex items-baseline gap-2 flex-wrap py-0.5" data-fleet-waiter={w.pid}>
      <span className="text-xs text-fg-ghost tabular-nums shrink-0 w-16">{w.pid}</span>
      <span
        className={`text-xs shrink-0 ${STATUS_TONE[w.status] ?? 'text-fg-muted'}`}
        data-fleet-waiter-status={w.status}
        title={STATUS_NOTE[w.status] ?? 'a status this screen does not recognise'}
      >
        {w.status}
      </span>
      <span className="text-xs text-fg-muted truncate min-w-0 max-w-[22rem]" title={w.cwd ?? ''}>
        {w.cwd ?? 'no working directory'}
      </span>
      {w.rooms && w.rooms.length > 0 && (
        <span className="text-xs text-fg-ghost truncate">rooms: {w.rooms.join(', ')}</span>
      )}
      <span className="ml-auto shrink-0">
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
      {error && <span className="text-xs text-red-400 w-full">refused: {error}</span>}
    </li>
  )
}

export default function FleetWaiters({ compact }: { compact?: boolean }) {
  const [data, setData] = useState<WaitersResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)

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
      <button
        onClick={() => setOpen(v => !v)}
        className="text-xs text-fg-muted hover:text-fg-strong underline-offset-2 hover:underline"
      >
        {orphans.length > 0
          ? <span className="text-amber-400">{orphans.length} orphaned waiter(s)</span>
          : <span>{data.waiters.length} waiter(s), none orphaned</span>}
        {undeterminable.length > 0 && (
          <span className="text-amber-400"> · {undeterminable.length} undeterminable</span>
        )}
        <span className="text-fg-ghost"> {open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <ul className="mt-1 space-y-0.5 border-l border-surface-line pl-2">
          {data.waiters.length === 0 && (
            <li className="text-xs text-fg-muted">
              measured: no waiter process is running on this machine
            </li>
          )}
          {data.waiters.map(w => (
            <WaiterRow key={w.pid} w={w} onRemoved={load} />
          ))}
          {!compact && (
            <li className="text-xs text-fg-ghost pt-1">
              Only an orphan is offered, and only one at a time — there is deliberately no bulk
              removal. Removing a live waiter is invisible: its agent merely looks quiet.
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
