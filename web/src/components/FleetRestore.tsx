/**
 * Bringing back what was here before the machine went down.
 *
 * Three placements, and only two of them are controls:
 *
 *  - **`RestoreFromEmpty`** — the panel shown when discovery answered and
 *    nothing is running. This is the PRIMARY one, and it is not the obvious
 *    choice: after a reboot no project holds an agent, so the project column
 *    offers nothing to click and a per-project control alone would be
 *    unreachable in exactly the state this feature exists for.
 *  - **`RestoreForProject`** — the per-project act, in the selected project's
 *    header, where the per-entry outcome is rendered.
 *  - the column row gets an INDICATOR only, in `FleetProjectColumn` — a count,
 *    not a button. That row already carries seven things.
 *
 * ## What the result may not do
 *
 * A restore of nine that started three is a partial result, and the single most
 * likely defect here is a green "Restored" over the six that did not come back.
 * So the outcome list is rendered where the reader is standing, every
 * non-started entry shows its reason, and the headline comes from
 * `summarise()`, which takes `complete` from the server rather than deciding it
 * a second time.
 */

import { useCallback, useEffect, useState } from 'react'
import { History, RotateCcw, TriangleAlert } from 'lucide-react'
import {
  ageLabel, canRestore, restoreOffer, summarise,
  type RestoreResult, type RestoreSummary, type RosterAnswer, type RosterProject,
} from '../lib/fleetRoster'

/**
 * A roster READ that cannot take the screen down with it.
 *
 * Found by the existing suite, 2026-08-21: 62 tests failed the moment this
 * component was mounted into the fleet screen, because their fetch mocks do not
 * know these routes and the chained `r.ok` threw. The tests were right and the
 * component was wrong — **a restore control is an addition to the screen, and an
 * addition that can break the screen is a worse defect than the absence it
 * replaces.**
 *
 * So every failure here — a rejection, a non-2xx, a body that is not JSON, a
 * mock that returns nothing at all — becomes `null`, which renders as no
 * control. That is honest: with no readable record there is nothing to offer.
 *
 * This applies to READS only. The restore ACT keeps its error visible: a 503
 * from an unreachable owner must be shown, because there the user asked for
 * something and it did not happen.
 */
async function readJson<T>(url: string): Promise<T | null> {
  try {
    const res = await fetch(url)
    if (!res || !res.ok) return null
    return (await res.json()) as T
  } catch {
    return null
  }
}

function OutcomeList({ summary }: { summary: RestoreSummary }) {
  if (!summary.unfinished.length) return null
  return (
    <ul className="mt-1.5 space-y-1" data-fleet-restore-unfinished={summary.unfinished.length}>
      {summary.unfinished.map(o => (
        <li key={o.key} className="flex items-start gap-1.5 text-xs">
          <TriangleAlert
            size={12}
            strokeWidth={1.75}
            className={`mt-0.5 shrink-0 ${o.status === 'failed' ? 'text-red-400' : 'text-amber-400'}`}
          />
          <span className="min-w-0">
            <span className="text-fg-strong">{o.label || o.key}</span>
            <span className="text-fg-ghost"> — {o.status} — </span>
            <span className="text-fg-muted">{o.reason}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

function Result({ summary }: { summary: RestoreSummary }) {
  return (
    <div
      className="mt-1.5 text-xs"
      data-fleet-restore-result={summary.complete ? 'complete' : 'partial'}
    >
      <span className={summary.complete ? 'text-emerald-400' : 'text-amber-400'}>
        {summary.headline}
      </span>
      <OutcomeList summary={summary} />
    </div>
  )
}

function useRestore(project: string | null, onDone?: () => void) {
  const [busy, setBusy] = useState(false)
  const [summary, setSummary] = useState<RestoreSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  const run = useCallback(async () => {
    if (!project) return
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`/api/fleet/roster/${encodeURIComponent(project)}/restore`,
                              { method: 'POST' })
      if (!res || !res.ok) {
        // A 503 is the owner being unreachable — nothing was attempted, and
        // saying "0 restored" would describe an attempt that never happened.
        const detail = res ? await res.json().catch(() => null) : null
        setError(detail?.detail || `restore failed (${res?.status ?? 'no answer'})`)
        return
      }
      const payload: RestoreResult = await res.json()
      setSummary(summarise(payload))
      onDone?.()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }, [project, onDone])

  return { busy, summary, error, run }
}

/**
 * The per-project control, for the selected project's header.
 */
export function RestoreForProject({ project, onRestored }: {
  project: string
  onRestored?: () => void
}) {
  const [answer, setAnswer] = useState<RosterAnswer | null>(null)
  const { busy, summary, error, run } = useRestore(project, onRestored)

  useEffect(() => {
    let live = true
    void readJson<RosterAnswer>(`/api/fleet/roster/${encodeURIComponent(project)}`)
      .then(d => { if (live) setAnswer(d) })
    return () => { live = false }
  }, [project])

  if (!canRestore(answer)) return null
  const offer = restoreOffer(answer!)

  // Everything recorded here is already up. Found by LOOKING at the running
  // screen, 2026-08-21: the control read "Restore 7 agents" for a project whose
  // seven sessions were all alive, promising an act that would have skipped
  // every one of them. The fact is still worth stating — it is why the screen
  // has nothing to restore — so it stays, as text rather than as a button that
  // would do nothing.
  if (!offer.actionable) {
    return (
      <span
        className="text-xs text-fg-ghost"
        data-fleet-restore-inert={offer.total}
        title="Recorded here and already running. A session with a live process on it is never resumed — that would fork its conversation."
      >
        {offer.label}
      </span>
    )
  }

  return (
    <span className="inline-flex flex-col" data-fleet-restore-project={project}>
      <button
        onClick={run}
        disabled={busy}
        data-fleet-restore-offer={offer.restorable}
        title="Starts an agent for each recorded session and resumes it. A session that is already running is left alone."
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-surface-line
                   text-xs text-fg-strong hover:bg-surface-raised disabled:opacity-50"
      >
        <RotateCcw size={11} strokeWidth={1.75} />
        {busy ? 'Restoring…' : offer.label}
      </button>
      {error && <span className="mt-1 text-xs text-red-400">{error}</span>}
      {summary && <Result summary={summary} />}
    </span>
  )
}

/**
 * The primary placement: the panel that shows when nothing is running anywhere.
 *
 * A list rather than a button, because there is no selected project to hang one
 * on — which is the whole reason this placement exists.
 */
export function RestoreFromEmpty() {
  const [projects, setProjects] = useState<RosterProject[] | null>(null)
  const [now] = useState(() => Date.now() / 1000)

  const load = useCallback(() => {
    void readJson<{ projects: RosterProject[] }>('/api/fleet/roster')
      .then(d => setProjects(d?.projects ?? []))
  }, [])

  useEffect(load, [load])

  if (projects === null) return null
  if (!projects.length) return null

  return (
    <div className="mt-4 rounded border border-surface-line p-3" data-fleet-restore-panel={projects.length}>
      <div className="flex items-center gap-1.5 text-sm text-fg-strong">
        <History size={13} strokeWidth={1.75} className="shrink-0" />
        Agents recorded here before
      </div>
      <p className="mt-1 text-xs text-fg-muted leading-relaxed">
        These are sessions the fleet has seen. Nothing is running now — a reboot ends every agent —
        but their conversations are on disk and can be resumed.
      </p>
      <ul className="mt-2 space-y-1.5">
        {projects.map(p => (
          <li key={p.project} className="flex items-center justify-between gap-3">
            <span className="min-w-0 text-xs">
              <span className="text-fg-strong">{p.project}</span>
              <span className="text-fg-ghost tabular-nums">
                {' '}— {p.entries} agent{p.entries === 1 ? '' : 's'}, last seen{' '}
                {ageLabel(now - p.last_seen)} ago
              </span>
            </span>
            <RestoreForProject project={p.project} onRestored={load} />
          </li>
        ))}
      </ul>
    </div>
  )
}
