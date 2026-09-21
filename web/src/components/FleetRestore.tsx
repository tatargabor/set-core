/**
 * Bringing back what was here before the machine went down.
 *
 * Four placements, and three of them are controls:
 *
 *  - **`RestoreFromEmpty`** — the panel shown when discovery answered and
 *    nothing is running. This is the PRIMARY one, and it is not the obvious
 *    choice: after a reboot no project holds an agent, so the project column
 *    offers nothing to click and a per-project control alone would be
 *    unreachable in exactly the state this feature exists for.
 *  - **`RestoreForProject`** — the per-project act, in the selected project's
 *    header, where the per-entry outcome is rendered.
 *  - **`RestoreAcrossProjects`** — the fleet-wide act, at the end of the project
 *    column's attention row: one dialog over every project's record, so a person
 *    can bring back sessions of several projects without selecting each one.
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
import { ChevronDown, ChevronRight, CircleDashed, History, RotateCcw, TriangleAlert } from 'lucide-react'
import { Chip } from './Chip'
import {
  ageLabel, allBlocked, canRestore, composition, groupByLabel, offerAcross, offerFor,
  restoreOffer, summarise, summariseAcross, turnSummary,
  type AcrossPart,
  type Peek, type RestoreResult, type RestoreSummary,
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

/**
 * One entry that did not start, as ONE truncated item in the result row.
 *
 * Compacted 2026-09-07 on the user's report with the strip on screen: the list
 * used to be a block of one row per entry, and a server reason carries a full
 * session id plus a sentence — the header grew a wrapped paragraph for a
 * single skip. The full text moves into the tooltip; `truncate` keeps it in the
 * DOM, so nothing that reads the fact loses it, and amber stays where the
 * reader is standing (compacting must never hide a failure — it hides the
 * *length*, not the fact).
 */
function OutcomeItem({ o }: { o: RestoreSummary['unfinished'][number] }) {
  const whole = `${o.label || o.key} — ${o.status}${o.reason ? ` — ${o.reason}` : ''}`
  return (
    <li key={o.key} className="flex min-w-0 items-center gap-1 text-xs" title={whole}>
      <TriangleAlert
        size={12}
        strokeWidth={1.75}
        className={`shrink-0 ${o.status === 'failed' ? 'text-red-400' : 'text-amber-400'}`}
      />
      <span className="truncate">
        <span className="text-fg-strong">{o.label || o.key}</span>
        <span className="text-fg-ghost"> — {o.status}{o.reason ? ' — ' : ''}</span>
        <span className="text-fg-muted">{o.reason}</span>
      </span>
    </li>
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
    <ul className="contents" data-fleet-restore-unnamed={summary.unnamed.length}>
      {summary.unnamed.map(o => {
        const whole = o.name_source === 'renamed'
          ? `${o.label_used} — came back as this because ${o.wanted_label} was taken`
          : `${o.label_used} — the framework named this one; no name was recorded for it`
        return (
          <li key={o.key} className="min-w-0 text-xs text-fg-muted" title={whole}>
            <span className="truncate">
              <span className="text-fg-strong">{o.label_used}</span>
              {o.name_source === 'renamed'
                ? <> — came back as this because <span className="text-fg-strong">{o.wanted_label}</span> was taken</>
                : <> — the framework named this one; no name was recorded for it</>}
            </span>
          </li>
        )
      })}
    </ul>
  )
}

/**
 * The restore outcome, as ONE compact row in the project strip.
 *
 * Compacted 2026-09-07 on the user's report: *"nem elég compact a felső menu,
 * sok a szöveg"*. The headline, every non-started entry and every renamed one
 * sit in a single wrapping line — each item truncated to the strip's width,
 * full text on hover — instead of a stacked block that wrapped a session id
 * and a sentence across the header. The colour still splits complete from
 * partial, and the `data-fleet-restore-*` count markers are unchanged, so the
 * DOM still states the shape a reader (or a test) can assert on.
 */
function Result({ summary }: { summary: RestoreSummary }) {
  return (
    <div
      className="mt-1 flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs"
      data-fleet-restore-result={summary.complete ? 'complete' : 'partial'}
    >
      <span
        className={summary.complete ? 'text-emerald-400' : 'text-amber-400'}
        title={summary.headline}
      >
        {summary.headline}
      </span>
      {/* `contents` lifts the list items into the row above rather than letting
          the ul draw a block of its own — the lists remain in the DOM with
          their count markers, and the strip stays one visual line. */}
      {summary.unfinished.length > 0 && (
        <ul className="contents" data-fleet-restore-unfinished={summary.unfinished.length}>
          {summary.unfinished.map(o => <OutcomeItem key={o.key} o={o} />)}
        </ul>
      )}
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
function ArmedRestore({ where, count, busy, onRun, label, title, mark }: {
  /** Where the agents would start — a project name, or "3 projects". */
  where: string
  /** The blast radius: how many agents the act would start. */
  count: number
  busy: boolean
  onRun: () => void
  label: string
  title: string
  mark: Record<string, string | number>
}) {
  const [armed, setArmed] = useState(false)
  const n = count

  if (armed) {
    return (
      <span className="inline-flex items-baseline gap-2" data-fleet-restore-confirm={n}>
        <span className="text-xs text-amber-300">
          Start {n} agent{n === 1 ? '' : 's'} in {where}?
        </span>
        <button
          onClick={() => { setArmed(false); onRun() }}
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
/**
 * The last turns of ONE recorded conversation, read on request.
 *
 * The question this answers is the one a person has in front of six rows
 * carrying the same name: *which conversation was this*. The answer is in the
 * transcript the entry would be resumed from, and reading its end costs a tail
 * read — no agent started, no session resumed, no context loaded.
 *
 * **Read on every open, held nowhere.** Not `localStorage`, not a module store,
 * not a memo that survives the panel closing. The framework may display a
 * project's data at runtime and must persist none of it, and a convenience
 * cache is exactly how that boundary gets crossed without anyone deciding to.
 */
function Peeked({ project, entry, onClose }: {
  project: string
  entry: RosterEntry
  onClose: () => void
}) {
  const [peek, setPeek] = useState<Peek | null>(null)
  const [busy, setBusy] = useState(true)

  useEffect(() => {
    let live = true
    setBusy(true)
    void readJson<Peek>(
      `/api/fleet/roster/${encodeURIComponent(project)}/${encodeURIComponent(entry.key)}/peek?limit=6`,
    ).then(d => {
      if (!live) return
      // `null` is the READ failing — a transport error, a 404, a body that is
      // not JSON. It must not render as a conversation with nothing in it.
      setPeek(d ?? { turns: [], problem: 'the last turns of this session could not be read' })
      setBusy(false)
    })
    return () => { live = false }
  }, [project, entry.key])

  return (
    <div className="mt-1 ml-5 rounded border border-surface-line bg-surface-raised/40 p-1.5"
         data-fleet-peek={entry.key}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-fg-muted">
          {busy ? 'reading the transcript…'
            : peek?.problem ? 'nothing to read'
            : `the last ${peek?.turns.length ?? 0} turn${(peek?.turns.length ?? 0) === 1 ? '' : 's'}`}
          {/* Stated with the turns, always: a six-turn answer to a
              two-hundred-turn conversation must not read as the whole of it. */}
          {peek?.truncated && peek.total_read
            ? <span className="text-fg-ghost"> of {peek.total_read} — earlier ones are still in the transcript</span>
            : null}
        </span>
        <button onClick={onClose} className="text-xs text-fg-muted hover:text-fg-strong">close</button>
      </div>
      {peek?.problem ? (
        <p className="mt-1 text-xs text-amber-400" data-fleet-peek-problem>{peek.problem}</p>
      ) : (
        <ul className="mt-1 space-y-1 max-h-48 overflow-y-auto pr-1">
          {(peek?.turns ?? []).map((t, i) => (
            <li key={i} className="text-xs">
              <span className={t.role === 'user' ? 'text-sky-300' : 'text-fg-muted'}>{t.role}</span>
              <span className="text-fg-ghost"> · </span>
              <span className="text-fg-strong whitespace-pre-wrap break-words">
                {turnSummary(t).slice(0, 400)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/**
 * One recorded entry: pick it, or look at what it was.
 *
 * The two are deliberately separate controls. Peeking is a READ and must not be
 * able to arm, select or start anything — the whole point of it is to decide
 * before acting.
 */
function RecordedEntry({ project, entry, picked, onPick, now }: {
  project: string
  entry: RosterEntry
  picked: boolean
  onPick: (key: string, on: boolean) => void
  now: number
}) {
  const [peeking, setPeeking] = useState(false)
  // Why an entry cannot be picked is said next to it. A checkbox that is simply
  // dead teaches the reader the screen is broken.
  const blocked = entry.running === true
    ? 'running now — a resume would fork its conversation'
    : !entry.resumable ? (entry.not_resumable_reason || 'not resumable') : null

  return (
    <li className="text-xs" data-fleet-recorded-entry={entry.key}>
      <span className="flex items-start gap-1.5">
        <input
          type="checkbox"
          className="mt-0.5"
          checked={picked}
          disabled={!!blocked}
          aria-label={entry.label || entry.key}
          onChange={ev => onPick(entry.key, ev.target.checked)}
        />
        <span className="min-w-0">
          <span className={blocked ? 'text-fg-ghost' : 'text-fg-strong'}>{entry.label || entry.key}</span>
          <span className="text-fg-ghost tabular-nums"> · last seen {ageLabel(now - entry.last_seen)} ago</span>
          {blocked && <span className="text-fg-ghost"> — {blocked}</span>}
          {' '}
          <button
            onClick={() => setPeeking(v => !v)}
            className="text-fg-muted hover:text-fg-strong underline decoration-dotted"
            data-fleet-peek-toggle={entry.key}
            title="Reads the last few turns of this conversation. Nothing is started and nothing is resumed."
          >
            {peeking ? 'hide' : 'what was this?'}
          </button>
        </span>
      </span>
      {peeking && <Peeked project={project} entry={entry} onClose={() => setPeeking(false)} />}
    </li>
  )
}

/**
 * The recorded entries of ONE project, as lineages with per-entry picks.
 *
 * Shared by the per-project dialog and the fleet-wide one, so the grouping,
 * the blocked-entry reasons and the peek cannot drift into two versions. The
 * selection lives with the caller: this only shows rows and reports ticks.
 */
function RecordedList({ project, entries, picked, onPick, now }: {
  project: string
  entries: RosterEntry[]
  picked: Record<string, boolean>
  onPick: (key: string, on: boolean) => void
  now: number
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const lineages = groupByLabel(entries)
  const pick = onPick
  return (
    <ul className="space-y-0.5" data-fleet-restore-lineages={lineages.length}>
      {lineages.map(line => {
        // One entry under a name is that entry. Wrapping it in a group
        // would make the reader open something to find one row.
        if (line.entries.length === 1) {
          return (
            <RecordedEntry key={line.key} project={project} entry={line.entries[0]}
                           picked={!!picked[line.entries[0].key]} onPick={pick} now={now} />
          )
        }
        const shown = !!expanded[line.key]
        const dead = allBlocked(line.entries)
        return (
          <li key={line.key} data-fleet-lineage={line.label}>
            <button
              onClick={() => setExpanded(p => ({ ...p, [line.key]: !shown }))}
              className="flex items-center gap-1 text-xs text-left"
              data-fleet-lineage-toggle={shown ? 'open' : 'closed'}
            >
              {shown ? <ChevronDown size={11} strokeWidth={1.75} className="shrink-0" />
                     : <ChevronRight size={11} strokeWidth={1.75} className="shrink-0" />}
              <span className={dead ? 'text-fg-ghost' : 'text-fg-strong'}>{line.label}</span>
              <span className="text-fg-ghost tabular-nums">
                · {line.entries.length} conversations · newest {ageLabel(now - line.entries[0].last_seen)} ago
              </span>
              {/* A compacted row must not be able to hide that nothing
                  inside it can come back. */}
              {dead && <span className="text-fg-ghost">· none can be resumed</span>}
            </button>
            {shown && (
              <ul className="ml-4 mt-0.5 space-y-0.5 border-l border-surface-line pl-2">
                {line.entries.map(e => (
                  <RecordedEntry key={e.key} project={project} entry={e}
                                 picked={!!picked[e.key]} onPick={pick} now={now} />
                ))}
              </ul>
            )}
          </li>
        )
      })}
    </ul>
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
 *
 * **Entries sharing a label render as one lineage** (B-80): six rows of one
 * name differing only by an age is the state in which a person picks the wrong
 * conversation. The lineage is a way of SHOWING rows — the selection stays per
 * entry, and there is no act that restores a lineage as a unit.
 */
function TheRest({ project, entries, busy, onRun }: {
  project: string
  entries: RosterEntry[]
  busy: boolean
  onRun: (keys: string[] | null) => void
}) {
  const [open, setOpen] = useState(false)
  const [picked, setPicked] = useState<Record<string, boolean>>({})

  // Escape closes it, because a layer that covers the page and can only be
  // dismissed with the mouse is a trap for anyone reading with the keyboard.
  // The same rule the follow panel already states, for the same reason.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  if (!entries.length) return null

  const chosen = entries.filter(e => picked[e.key])
  const offer = offerFor(chosen)
  const now = Date.now() / 1000
  const lineages = groupByLabel(entries)
  const pick = (key: string, on: boolean) => setPicked(p => ({ ...p, [key]: on }))

  return (
    /* Not a column and not indented: the dialog it opens is `fixed`, so this
       wrapper only ever holds the chip. */
    <span className="inline-flex" data-fleet-restore-rest={entries.length}>
      <Chip
        jump="restore-rest"
        onClick={() => setOpen(true)}
        data={{ 'data-fleet-restore-rest-toggle': open ? 'open' : 'closed' }}
        mark={<History size={13} strokeWidth={1.75} aria-hidden />}
        count={entries.length}
        title={`${entries.length} session(s) recorded in this project that are not open — click to look at them`}
        label={`${entries.length} more recorded here, not open`}
      />

      {/*
        A DIALOG, not a drop-down — asked for by the user 2026-08-26, with the
        screen in front of them: *"funkcióban jó de szerintem ez egy popup screen
        kellene legyen nagyban és nincs close most pl hogy bezárjam"*.

        Both halves of that are the same defect. The list opened inside a header
        row, so it was as wide as a header row and as tall as whatever was left
        — a 47-entry record with a transcript excerpt inside it does not fit in
        that, and the peek was reading a paragraph through a letterbox. And the
        only way to close it was the line that opened it, which is a toggle
        wearing the clothes of a heading: nothing about it says *press me again
        and this goes away*. A surface that can be opened and not obviously
        closed is a trap, and it was reported as one within minutes.

        So: the house dialog (the follow panel's), which already carries the
        three ways out a covering layer owes the reader — the ×, Escape, and a
        click on the backdrop.
      */}
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-surface-page/60"
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
          data-fleet-restore-dialog={entries.length}
        >
          <div
            className="w-[70vw] max-w-4xl h-[76vh] flex flex-col rounded border border-surface-line
                       bg-surface-page shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-line shrink-0">
              <History size={13} strokeWidth={1.75} className="shrink-0 text-fg-muted" />
              <span className="text-sm text-fg-strong">Recorded in {project}, not open</span>
              <span className="text-xs text-fg-ghost">
                {entries.length} conversation{entries.length === 1 ? '' : 's'} · {lineages.length} agent
                {lineages.length === 1 ? '' : 's'}
              </span>
              <button
                onClick={() => setOpen(false)}
                className="ml-auto text-fg-muted hover:text-fg-strong px-1 text-base leading-none"
                aria-label="close"
                data-fleet-restore-dialog-close
              >×</button>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto px-3 py-2">
              <RecordedList project={project} entries={entries} picked={picked} onPick={pick} now={now} />
            </div>

            <div className="flex items-center gap-3 px-3 py-2 border-t border-surface-line shrink-0"
                 data-fleet-restore-selected={offer.restorable}>
              {offer.actionable ? (
                <ArmedRestore
                  where={project}
                  count={offer.restorable}
                  busy={busy}
                  onRun={() => onRun(offer.keys)}
                  label={`Restore ${offer.restorable} selected`}
                  title="Resumes only the conversations you ticked."
                  mark={{ 'data-fleet-restore-selection': offer.restorable }}
                />
              ) : (
                <span className="text-xs text-fg-ghost">Tick the ones to bring back.</span>
              )}
              <button
                onClick={() => setOpen(false)}
                className="ml-auto text-xs text-fg-muted hover:text-fg-strong"
              >close</button>
            </div>
          </div>
        </div>
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
    /* A ROW of chips, with the result — a multi-line report — underneath it.
       It used to be a plain column, which put `55 more recorded here` on a
       second line of the project header and made the whole strip two rows tall
       for two numbers. */
    <span className="inline-flex flex-col ml-4 pl-4 border-l border-surface-line"
          data-fleet-restore-project={project}>
      <span className="inline-flex items-center gap-2">
      {comp.known && comp.entries.length === 0 ? (
        // The fleet WAS observed and nothing was open here — a MEASURED zero, so
        // it is drawn as one rather than left out: no earlier round is offered
        // in its place either, because presenting agents the user had already
        // closed as "what was open" is a false value in the acting direction,
        // and it is the one this whole change removes.
        <Chip
          jump="restore-empty"
          data={{ 'data-fleet-restore-composition-empty': String(comp.rest.length) }}
          tone="text-fg-ghost"
          mark={<RotateCcw size={13} strokeWidth={1.75} aria-hidden />}
          count={0}
          title={`Nothing was open here when the fleet was last seen${observed ? ` (${observed} ago)` : ''} — so there is nothing to bring back. The count beside this is what is recorded but was not open.`}
          label={`Nothing was open here when the fleet was last seen${observed ? ` (${observed} ago)` : ''}`}
        />
      ) : offer.actionable ? (
        <ArmedRestore
          where={project}
          count={offer.restorable}
          busy={busy}
          onRun={() => run(comp.known ? offer.keys : null)}
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
        <Chip
          jump="restore-inert"
          data={{ 'data-fleet-restore-inert': String(offer.total) }}
          tone="text-fg-ghost"
          mark={<RotateCcw size={13} strokeWidth={1.75} aria-hidden />}
          count={offer.total}
          title={`${offer.label}. Recorded here and already running — a session with a live process on it is never resumed, that would fork its conversation.`}
          label={offer.label}
        />
      )}
      {/* Why the offer is the whole list rather than a composition. A `?` in
          the same place the counts are, because that is what it is — the record
          could not say — and the sentence is one hover away. */}
      {!comp.known && (
        <Chip
          jump="restore-unknown-composition"
          data={{ 'data-fleet-restore-unknown-composition': String(offer.total) }}
          tone="text-fg-ghost"
          mark={<CircleDashed size={13} strokeWidth={1.75} aria-hidden />}
          count="?"
          title={comp.reason ?? ''}
          label={comp.reason ?? 'the composition is not known'}
        />
      )}
      {comp.known && <TheRest project={project} entries={comp.rest} busy={busy} onRun={run} />}
      </span>
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

/**
 * One project inside the fleet-wide dialog: a row that opens to its record.
 *
 * The record is read on the FIRST open and not before — at 34 projects, reading
 * every one when the dialog opens would be 34 liveness-asking reads to draw a
 * list of names the listing already gave. Held only while the dialog is open;
 * nothing here persists a project's data (the same rule `Peeked` states).
 */
function AcrossProjectRow({ item, now, picked, onPick }: {
  item: RosterProject
  now: number
  picked: Record<string, boolean>
  onPick: (project: string, entry: RosterEntry, on: boolean) => void
}) {
  const [open, setOpen] = useState(false)
  const [answer, setAnswer] = useState<RosterAnswer | null | 'failed'>(null)
  // The ages inside are measured against the moment THIS record was read. The
  // dialog's own clock is taken when it opens, and an entry seen after that —
  // a running one, say — would be "last seen in the future", which `ageLabel`
  // prints as `unknown`. Found by looking at the live screen, 2026-09-21.
  const [readAt, setReadAt] = useState(now)

  useEffect(() => {
    if (!open || answer !== null) return
    let live = true
    void readJson<RosterAnswer>(`/api/fleet/roster/${encodeURIComponent(item.project)}`)
      .then(d => {
        if (!live) return
        setReadAt(Date.now() / 1000)
        setAnswer(d && Array.isArray(d.entries) ? d : 'failed')
      })
    return () => { live = false }
  }, [open, answer, item.project])

  const entries = answer && answer !== 'failed' ? answer.entries : []
  const ticked = Object.values(picked).filter(Boolean).length
  const byKey = new Map(entries.map(e => [e.key, e]))

  return (
    <li data-fleet-across-project={item.project}>
      <button
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-1.5 text-xs text-left py-0.5"
        data-fleet-across-toggle={open ? 'open' : 'closed'}
      >
        {open ? <ChevronDown size={11} strokeWidth={1.75} className="shrink-0" />
              : <ChevronRight size={11} strokeWidth={1.75} className="shrink-0" />}
        <span className="text-fg-strong">{item.project}</span>
        <span className="text-fg-ghost tabular-nums">
          · {item.entries} recorded
          {typeof item.running === 'number' && item.running > 0 ? ` · ${item.running} running` : ''}
          {' '}· newest {ageLabel(now - item.last_seen)} ago
        </span>
        {ticked > 0 && <span className="text-amber-300 tabular-nums">· {ticked} ticked</span>}
      </button>
      {open && (
        <div className="ml-4 mt-0.5 mb-1 border-l border-surface-line pl-2">
          {answer === null ? (
            <span className="text-xs text-fg-muted">reading the record…</span>
          ) : answer === 'failed' ? (
            // A read that failed is not an empty record — say which it is.
            <span className="text-xs text-amber-400" data-fleet-across-unreadable>
              this project's record could not be read
            </span>
          ) : entries.length === 0 ? (
            <span className="text-xs text-fg-ghost">nothing recorded here</span>
          ) : (
            <RecordedList
              project={item.project}
              entries={entries}
              picked={picked}
              onPick={(key, on) => { const e = byKey.get(key); if (e) onPick(item.project, e, on) }}
              now={readAt}
            />
          )}
        </div>
      )}
    </li>
  )
}

/**
 * The fleet-wide reopen: every project's record, in ONE dialog.
 *
 * Asked for by the user 2026-09-21 (dictated): reopen past sessions of
 * different projects *in one window, without doing it one by one from the
 * project folder*, from an icon right after the status marks at the top of the
 * project column. The per-project dialog needs a selected project, and
 * `RestoreFromEmpty` only shows when nothing runs anywhere — so with any agent
 * alive there was no route to a second project's history but walking to it.
 *
 * **Nothing is ticked on open, and there is no "all" act.** The blast radius
 * here spans projects, which makes the 21-agent mis-click behind `ArmedRestore`
 * larger, not smaller. The confirmation names both numbers.
 *
 * The act posts each project's keys to that project's own restore route, one
 * after another, so the server stays the only judge of each project's outcome
 * and `summariseAcross()` only adds them up.
 */
export function RestoreAcrossProjects({ onRestored }: { onRestored?: () => void }) {
  const [projects, setProjects] = useState<RosterProject[] | null>(null)
  const [open, setOpen] = useState(false)
  const [now, setNow] = useState(() => Date.now() / 1000)
  const [picked, setPicked] = useState<Record<string, Record<string, RosterEntry>>>({})
  const [busy, setBusy] = useState(false)
  const [parts, setParts] = useState<AcrossPart[] | null>(null)

  const load = useCallback(() => {
    void readJson<{ projects: RosterProject[] }>('/api/fleet/roster')
      .then(d => setProjects(d && Array.isArray(d.projects) ? d.projects : []))
  }, [])
  useEffect(load, [load])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const onPick = useCallback((project: string, entry: RosterEntry, on: boolean) => {
    setPicked(p => {
      const mine = { ...(p[project] ?? {}) }
      if (on) mine[entry.key] = entry
      else delete mine[entry.key]
      return { ...p, [project]: mine }
    })
  }, [])

  const run = useCallback(async (plan: { project: string; keys: string[] }[]) => {
    setBusy(true)
    const out: AcrossPart[] = []
    // Sequential on purpose: each post starts agents through the owner service,
    // and N projects at once is a load the per-project path never produces.
    for (const { project, keys } of plan) {
      try {
        const res = await fetch(`/api/fleet/roster/${encodeURIComponent(project)}/restore`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ keys }),
        })
        if (!res || !res.ok) {
          const detail = res ? await res.json().catch(() => null) : null
          out.push({ project, error: detail?.detail || `restore failed (${res?.status ?? 'no answer'})` })
          continue
        }
        out.push({ project, summary: summarise(await res.json() as RestoreResult) })
      } catch (e) {
        out.push({ project, error: String(e) })
      }
    }
    setParts(out)
    setPicked({})
    setBusy(false)
    load()
    onRestored?.()
  }, [load, onRestored])

  if (!projects || !projects.length) return null

  const total = projects.reduce((n, p) => n + p.entries, 0)
  const running = projects.reduce((n, p) => n + (typeof p.running === 'number' ? p.running : 0), 0)
  const selection = Object.fromEntries(
    Object.entries(picked).map(([proj, m]) => [proj, Object.values(m)]))
  const offer = offerAcross(selection)
  const across = parts ? summariseAcross(parts) : null

  return (
    <span className="inline-flex" data-fleet-across={projects.length}>
      <Chip
        jump="restore-across"
        onClick={() => { setNow(Date.now() / 1000); setOpen(true) }}
        data={{ 'data-fleet-across-open': open ? 'open' : 'closed' }}
        mark={<History size={13} strokeWidth={1.75} aria-hidden />}
        count={total - running}
        title={`Reopen earlier sessions — ${total} recorded across ${projects.length} project(s)${running ? `, ${running} running now` : ''}. Opens one window over every project; nothing starts until you tick and confirm.`}
        label={`reopen recorded sessions across ${projects.length} projects`}
      />
      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-surface-page/60"
          onClick={() => setOpen(false)}
          role="dialog"
          aria-modal="true"
          data-fleet-across-dialog={projects.length}
        >
          <div
            className="w-[70vw] max-w-4xl h-[76vh] flex flex-col rounded border border-surface-line
                       bg-surface-page shadow-2xl"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 px-3 py-2 border-b border-surface-line shrink-0">
              <History size={13} strokeWidth={1.75} className="shrink-0 text-fg-muted" />
              <span className="text-sm text-fg-strong">Reopen recorded sessions</span>
              <span className="text-xs text-fg-ghost tabular-nums">
                {total} recorded · {projects.length} project{projects.length === 1 ? '' : 's'}
              </span>
              <button
                onClick={() => setOpen(false)}
                className="ml-auto text-fg-muted hover:text-fg-strong px-1 text-base leading-none"
                aria-label="close"
                data-fleet-across-close
              >×</button>
            </div>

            <ul className="flex-1 min-h-0 overflow-y-auto px-3 py-2 space-y-0.5">
              {projects.map(p => (
                <AcrossProjectRow
                  key={p.project}
                  item={p}
                  now={now}
                  picked={Object.fromEntries(Object.keys(picked[p.project] ?? {}).map(k => [k, true]))}
                  onPick={onPick}
                />
              ))}
            </ul>

            {across && parts && (
              <div
                className="px-3 py-1.5 border-t border-surface-line shrink-0 space-y-0.5 max-h-40 overflow-y-auto"
                data-fleet-across-result={across.complete ? 'complete' : 'partial'}
              >
                <div className={`text-xs ${across.complete ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {across.headline}
                </div>
                <ul className="space-y-0.5">
                  {parts.map(part => (
                    <li key={part.project} className="text-xs min-w-0" data-fleet-across-part={part.project}>
                      <span className="text-fg-strong">{part.project}</span>
                      {part.error !== undefined ? (
                        <span className="text-red-400" data-fleet-across-part-error> — {part.error}</span>
                      ) : (
                        <Result summary={part.summary} />
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex items-center gap-3 px-3 py-2 border-t border-surface-line shrink-0"
                 data-fleet-across-selected={offer.restorable}>
              {offer.actionable ? (
                <ArmedRestore
                  where={`${offer.projects} project${offer.projects === 1 ? '' : 's'}`}
                  count={offer.restorable}
                  busy={busy}
                  onRun={() => void run(offer.parts)}
                  label={`Restore ${offer.restorable} selected in ${offer.projects} project${offer.projects === 1 ? '' : 's'}`}
                  title="Resumes only the conversations you ticked, each in its own project."
                  mark={{ 'data-fleet-across-selection': offer.restorable }}
                />
              ) : (
                <span className="text-xs text-fg-ghost">Open a project and tick the sessions to bring back.</span>
              )}
              <button
                onClick={() => setOpen(false)}
                className="ml-auto text-xs text-fg-muted hover:text-fg-strong"
              >close</button>
            </div>
          </div>
        </div>
      )}
    </span>
  )
}
