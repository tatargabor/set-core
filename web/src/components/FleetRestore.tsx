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
import { ChevronDown, ChevronRight, History, RotateCcw, TriangleAlert } from 'lucide-react'
import {
  ageLabel, canRestore, composition, offerFor, restoreOffer, summarise,
  type RestoreOffer, type RestoreResult, type RestoreSummary,
  type RosterAnswer, type RosterEntry, type RosterProject,
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

/**
 * The agents that came back under a name nobody chose.
 *
 * Not an alarm — they are running, which is what was asked for. But the name is
 * the handle a person navigates by, and a name the framework invented looks
 * exactly like one they chose. So it is said plainly, next to the agent it is
 * about, with what was wanted where there was something to want.
 */
function NameList({ summary }: { summary: RestoreSummary }) {
  if (!summary.unnamed.length) return null
  return (
    <ul className="mt-1.5 space-y-1" data-fleet-restore-unnamed={summary.unnamed.length}>
      {summary.unnamed.map(o => (
        <li key={o.key} className="text-xs text-fg-muted">
          <span className="text-fg-strong">{o.label_used}</span>
          {o.name_source === 'renamed'
            ? <> — came back as this because <span className="text-fg-strong">{o.wanted_label}</span> was taken</>
            : <> — the framework named this one; no name was recorded for it</>}
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
      <NameList summary={summary} />
    </div>
  )
}

function useRestore(project: string | null, onDone?: () => void) {
  const [busy, setBusy] = useState(false)
  const [summary, setSummary] = useState<RestoreSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  /**
   * `keys === null` posts no body, which is the route's "the whole recorded
   * list" — the request this control has always made. A list posts exactly
   * those entries.
   *
   * An empty list is never posted: the caller disables the act instead. That is
   * not the same as trusting the server to be kind about it — the server treats
   * an empty selection as "attempt nothing", which is correct — it is that a
   * button offering to restore zero agents is a control that does nothing, and
   * this screen already refuses to draw one of those.
   */
  const run = useCallback(async (keys: string[] | null) => {
    if (!project) return
    if (keys !== null && keys.length === 0) return
    setBusy(true)
    setError(null)
    try {
      const res = await fetch(`/api/fleet/roster/${encodeURIComponent(project)}/restore`,
                              keys === null
                                ? { method: 'POST' }
                                : { method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ keys }) })
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
 * One armed act: state the blast radius, wait, then run.
 *
 * Shared by both offers rather than written twice. The arming is not a nicety —
 * reported by the user 2026-08-23 with a screenshot: this control sits inches
 * from `+ start an agent` in the same header row, and one mis-aimed click
 * started **21 agents** on a project they were not working on, with no way to
 * undo it except stopping each one. An act whose blast radius is a number
 * printed on the button itself must state that number and wait.
 *
 * A smaller default set is a reason to keep this guard proportionate, never a
 * reason to drop it.
 */
function ArmedRestore({ project, offer, keys, busy, onRun, label, title, mark }: {
  project: string
  offer: RestoreOffer
  /** `null` — the whole recorded list, posted with no body. */
  keys: string[] | null
  busy: boolean
  onRun: (keys: string[] | null) => void
  label: string
  title: string
  mark: Record<string, string | number>
}) {
  const [armed, setArmed] = useState(false)
  const n = offer.restorable

  if (armed) {
    return (
      <span className="inline-flex items-baseline gap-2" data-fleet-restore-confirm={n}>
        <span className="text-xs text-amber-300">
          Start {n} agent{n === 1 ? '' : 's'} in {project}?
        </span>
        <button
          onClick={() => { setArmed(false); onRun(keys) }}
          disabled={busy}
          data-fleet-restore-go={n}
          className="px-1.5 py-0.5 rounded border border-amber-500/60 text-xs text-amber-200
                     hover:bg-amber-500/10 disabled:opacity-50"
        >
          {busy ? 'Restoring…' : `yes, restore ${n}`}
        </button>
        <button onClick={() => setArmed(false)} className="text-xs text-fg-muted hover:text-fg-strong">
          cancel
        </button>
      </span>
    )
  }

  return (
    <button
      onClick={() => setArmed(true)}
      disabled={busy}
      data-fleet-restore-offer={n}
      title={title}
      {...mark}
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border border-surface-line
                 text-xs text-fg-strong hover:bg-surface-raised disabled:opacity-50"
    >
      <RotateCcw size={11} strokeWidth={1.75} />
      {busy ? 'Restoring…' : label}
    </button>
  )
}

/**
 * Everything recorded that was NOT open — reachable, and never offered by
 * accident.
 *
 * It is on the screen because the record holding more than the composition is
 * information: a project with 3 open and 21 remembered tells the reader
 * something a list of 3 does not. It is behind a disclosure and individually
 * checked because those 21 are old conversations of the same agents, and
 * starting them was the defect this whole change exists to remove.
 */
function TheRest({ project, entries, busy, onRun }: {
  project: string
  entries: RosterEntry[]
  busy: boolean
  onRun: (keys: string[] | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [picked, setPicked] = useState<Record<string, boolean>>({})
  if (!entries.length) return null

  const chosen = entries.filter(e => picked[e.key])
  const offer = offerFor(chosen)
  const now = Date.now() / 1000

  return (
    <span className="mt-1 flex flex-col" data-fleet-restore-rest={entries.length}>
      <button
        onClick={() => setOpen(v => !v)}
        className="inline-flex items-center gap-1 text-xs text-fg-muted hover:text-fg-strong"
        data-fleet-restore-rest-toggle={open ? 'open' : 'closed'}
      >
        {open ? <ChevronDown size={11} strokeWidth={1.75} /> : <ChevronRight size={11} strokeWidth={1.75} />}
        {entries.length} more recorded here, not open
      </button>
      {open && (
        <>
          {/* Capped and scrolled, because LOOKING at it on 2026-08-26 showed a
              47-entry record push the entire agent grid off the screen: the
              disclosure is in a header row, so its height is the page's. A list
              that hides the work to show the history is the compacting rule
              failing in the other direction. */}
          <ul className="mt-1 space-y-0.5 max-h-64 overflow-y-auto pr-1">
            {entries.map(e => {
              // Why an entry cannot be picked is said next to it. A checkbox
              // that is simply dead teaches the reader the screen is broken.
              const blocked = e.running === true
                ? 'running now — a resume would fork its conversation'
                : !e.resumable ? (e.not_resumable_reason || 'not resumable') : null
              return (
                <li key={e.key} className="flex items-start gap-1.5 text-xs">
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    checked={!!picked[e.key]}
                    disabled={!!blocked}
                    aria-label={e.label || e.key}
                    onChange={ev => setPicked(p => ({ ...p, [e.key]: ev.target.checked }))}
                  />
                  <span className="min-w-0">
                    <span className={blocked ? 'text-fg-ghost' : 'text-fg-strong'}>{e.label || e.key}</span>
                    <span className="text-fg-ghost tabular-nums"> · last seen {ageLabel(now - e.last_seen)} ago</span>
                    {blocked && <span className="text-fg-ghost"> — {blocked}</span>}
                  </span>
                </li>
              )
            })}
          </ul>
          <span className="mt-1" data-fleet-restore-selected={offer.restorable}>
            {offer.actionable ? (
              <ArmedRestore
                project={project}
                offer={offer}
                keys={offer.keys}
                busy={busy}
                onRun={onRun}
                label={`Restore ${offer.restorable} selected`}
                title="Resumes only the conversations you ticked."
                mark={{ 'data-fleet-restore-selection': offer.restorable }}
              />
            ) : (
              <span className="text-xs text-fg-ghost">Tick the ones to bring back.</span>
            )}
          </span>
        </>
      )}
    </span>
  )
}

/**
 * The per-project control, for the selected project's header.
 *
 * **Two offers, one act.** The primary one is the last observed composition —
 * what was open when the fleet was last seen — and the rest of the record sits
 * behind a disclosure. Both post to the same route and render through the same
 * `summarise()`, so the partial-result rendering cannot drift into two versions.
 *
 * Why the composition rather than the record: measured 2026-08-26 on one
 * machine, the record held 233 entries against 13 that were open, because an
 * entry is keyed on the session id and a resume mints a new one. The control's
 * count was honest about what the code would do, and what the code would do was
 * start nine sessions nobody left open.
 */
export function RestoreForProject({ project, onRestored }: {
  project: string
  onRestored?: () => void
}) {
  const [answer, setAnswer] = useState<RosterAnswer | null>(null)
  const [now] = useState(() => Date.now() / 1000)
  const { busy, summary, error, run } = useRestore(project, onRestored)

  useEffect(() => {
    let live = true
    void readJson<RosterAnswer>(`/api/fleet/roster/${encodeURIComponent(project)}`)
      .then(d => { if (live) setAnswer(d) })
    return () => { live = false }
  }, [project])

  if (!canRestore(answer)) return null
  const comp = composition(answer)
  // Known: offer the composition. Unknown: the whole list, WITH the reason —
  // a whole-list offer wearing a composition's label is the same false value by
  // a quieter route.
  const offer = comp.known ? offerFor(comp.entries) : restoreOffer(answer!)
  const observed = comp.observedAt === null ? null : ageLabel(now - comp.observedAt)

  const result = (
    <>
      {error && <span className="mt-1 text-xs text-red-400">{error}</span>}
      {summary && <Result summary={summary} />}
    </>
  )

  return (
    <span className="inline-flex flex-col ml-4 pl-4 border-l border-surface-line"
          data-fleet-restore-project={project}>
      {comp.known && comp.entries.length === 0 ? (
        // The fleet WAS observed and nothing was open here. Said in words, and
        // no earlier round is offered in its place — presenting agents the user
        // had already closed as "what was open" is a false value in the acting
        // direction, and it is the one this whole change removes.
        <span className="text-xs text-fg-ghost" data-fleet-restore-composition-empty={comp.rest.length}>
          Nothing was open here when the fleet was last seen
          {observed ? ` (${observed} ago)` : ''}
        </span>
      ) : offer.actionable ? (
        <ArmedRestore
          project={project}
          offer={offer}
          keys={comp.known ? offer.keys : null}
          busy={busy}
          onRun={run}
          label={comp.known
            ? `${offer.label}${observed ? ` — open ${observed} ago` : ''}`
            : offer.label}
          title={comp.known
            ? 'Asks first. Brings back the agents that were open when the fleet was last seen, resuming each conversation.'
            : 'Asks first. Then starts an agent for each recorded session and resumes it — a session that is already running is left alone.'}
          mark={comp.known
            ? { 'data-fleet-restore-composition': offer.total }
            : { 'data-fleet-restore-whole-list': offer.total }}
        />
      ) : (
        // Everything in this offer is already up. Found by LOOKING at the
        // running screen, 2026-08-21: the control read "Restore 7 agents" for a
        // project whose seven sessions were all alive, promising an act that
        // would have skipped every one of them. The fact is still worth stating
        // — it is why the screen has nothing to restore — so it stays, as text
        // rather than as a button that would do nothing.
        <span
          className="text-xs text-fg-ghost"
          data-fleet-restore-inert={offer.total}
          title="Recorded here and already running. A session with a live process on it is never resumed — that would fork its conversation."
        >
          {offer.label}
        </span>
      )}
      {!comp.known && (
        <span className="mt-0.5 text-xs text-fg-ghost" data-fleet-restore-unknown-composition={offer.total}>
          {comp.reason}
        </span>
      )}
      {comp.known && <TheRest project={project} entries={comp.rest} busy={busy} onRun={run} />}
      {result}
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
