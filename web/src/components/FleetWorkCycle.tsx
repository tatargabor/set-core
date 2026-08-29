/**
 * The work-cycle panel: what the engine can drive here, and what its runs came to.
 *
 * ## Why this reads two sources and says which is which
 *
 * Recorded runs come off disk and render with nothing running. *What is runnable*
 * is asked of the engine. When the engine cannot be asked, the runs are still
 * here and the runnable column says it could not be measured — a missing
 * capability must not empty the screen, and it must not quietly become "nothing
 * to run", which is a claim about the project that nobody made.
 *
 * ## Compact, but nothing wrong is hidden
 *
 * Changes are a table because the rows are comparable. Runs sit under their
 * change, collapsed — and anything failed, waiting, stale or unreported is
 * counted ON the collapsed row, so a reader who never expands it still sees that
 * something is wrong. The count comes from `attentionMark`, which also says
 * whether it could look at all.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  attentionLabel, attentionMark, originLabel, runState, runnableLabel,
  type RunState, type WorkRun,
} from '../lib/fleetWorkCycle'

interface ChangeRow {
  change: string
  runnable: boolean | null
  selected?: string | null
  reasons?: Record<string, string>
  available?: boolean
  reason?: string
  runs: WorkRun[]
}

interface WorkCyclePayload {
  project_root: string
  adopted: boolean | null
  not_adopted_reason: string
  engine: { available: boolean; reason: string }
  changes_dir?: string | null
  changes_listed: boolean
  changes_error?: string
  changes: ChangeRow[]
  runs: WorkRun[]
}

const STATE_TONE: Record<RunState, string> = {
  waiting: 'text-amber-300',
  failed: 'text-red-400',
  stale: 'text-red-400',
  unconfirmed: 'text-amber-300',
  unreported: 'text-amber-300',
  running: 'text-fg-strong',
  done: 'text-fg-muted',
}

/** What the state MEANS, for a reader who has not read the engine's design. */
const STATE_TITLE: Record<RunState, string> = {
  waiting: 'set aside — a person must answer before this group continues',
  failed: 'the gate was red, or the unit could not proceed',
  stale: 'the record claims this run is in progress; its process is gone',
  unconfirmed: 'claims to be running, and the process holding that pid could not be '
    + 'confirmed to be the agent — a pid is reused',
  unreported: 'the run ended without ever reporting a verdict',
  running: 'running now',
  done: 'finished',
}

/**
 * This surface's own seat, for the lifetime of this browser tab.
 *
 * The engine refuses a seat that names only a PROJECT, because such a seat
 * matches every live session in it and an answer keyed to it reaches the wrong
 * one. A screen has no agent session of its own, so it identifies itself: one
 * id per tab, stable while the tab lives, stored where a reload keeps it and a
 * new tab does not inherit it.
 *
 * Truthful rather than convenient — it names THIS surface, never a project, and
 * never borrows an agent's identity to make a start look like that agent's work.
 */
export function surfaceSeat(): string {
  const KEY = 'fleet.work-cycle.seat'
  try {
    const held = sessionStorage.getItem(KEY)
    if (held) return held
    const made = `session:${crypto.randomUUID()}`
    sessionStorage.setItem(KEY, made)
    return made
  } catch {
    // Private windows and blocked site data both land here. A seat that lasts
    // one render is still a seat that identifies one act, which is what the
    // engine's rule protects; it simply will not survive a reload.
    return `session:${crypto.randomUUID()}`
  }
}

export default function FleetWorkCycle({
  root, projectName, seat, onClose, onOpenRecording,
}: {
  root: string
  projectName: string
  /**
   * The seat a start is attributed to. Session-scoped — never a project name.
   * Defaults to this surface's own; a caller passes one only when a start
   * genuinely belongs to another session.
   */
  seat?: string | null
  onClose?: () => void
  onOpenRecording?: (change: string, unitId: string) => void
}) {
  const startSeat = seat ?? surfaceSeat()
  const [data, setData] = useState<WorkCyclePayload | null>(null)
  const [error, setError] = useState<string>('')
  const [busy, setBusy] = useState<string>('')
  const [refusal, setRefusal] = useState<{ change: string; text: string } | null>(null)
  const [open, setOpen] = useState<Record<string, boolean>>({})

  const load = useCallback(() => {
    fetch(`/api/fleet/work-cycle?cwd=${encodeURIComponent(root)}`)
      .then(async res => {
        if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
        return res.json()
      })
      .then((d: WorkCyclePayload) => { setData(d); setError('') })
      .catch(e => setError(String(e?.message || e)))
  }, [root])

  useEffect(() => { load() }, [load])

  const start = useCallback(async (change: string) => {
    if (!startSeat) return
    setBusy(change)
    setRefusal(null)
    try {
      const res = await fetch('/api/fleet/units', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ change, cwd: root, seat: startSeat,
                               requested_by: startSeat }),
      })
      if (!res.ok) {
        // The refusal, in its own words, where the person acted. Never a generic
        // failure: the three sources (the engine, the location check, a command
        // that cannot be executed) each say something different and actionable.
        const body = await res.text()
        let text = body
        try {
          const parsed = JSON.parse(body)
          text = typeof parsed.detail === 'string'
            ? parsed.detail : JSON.stringify(parsed.detail ?? parsed)
        } catch { /* the body was not JSON; show it as it came */ }
        setRefusal({ change, text })
        return
      }
      load()
    } catch (e) {
      setRefusal({ change, text: String((e as Error)?.message || e) })
    } finally {
      setBusy('')
    }
  }, [root, startSeat, load])

  if (error) {
    return (
      <div className="p-3 text-xs text-red-400">
        could not read this project’s work cycle: {error}
      </div>
    )
  }
  if (!data) return <div className="p-3 text-xs text-fg-muted">reading…</div>

  const engineDown = !data.engine.available

  return (
    <div className="flex flex-col h-full min-h-0 text-xs">
      <header className="flex items-center gap-2 px-2 py-1 border-b border-border shrink-0">
        <span className="font-medium text-fg-strong truncate">work cycle · {projectName}</span>
        <button className="ml-auto text-fg-muted hover:text-fg-strong" onClick={load}
                title="re-read the engine’s records">↻</button>
        {onClose && (
          <button className="text-fg-muted hover:text-fg-strong" onClick={onClose}>✕</button>
        )}
      </header>

      {/* The engine's own state, stated before anything derived from it. A reader
          who does not know the engine is missing will read every "unknown" below
          as a property of the project. */}
      {engineDown && (
        <div className="px-2 py-1 text-amber-300 border-b border-border shrink-0">
          {data.engine.reason || 'the engine could not be asked'}
        </div>
      )}
      {data.adopted === false && (
        <div className="px-2 py-1 text-fg-muted border-b border-border shrink-0">
          not adopted — {data.not_adopted_reason || 'this project has no declaration'}
        </div>
      )}
      {data.adopted === null && !engineDown && (
        <div className="px-2 py-1 text-amber-300 border-b border-border shrink-0">
          whether this project is adopted could not be measured
        </div>
      )}
      {data.changes_listed === false && data.adopted && (
        <div className="px-2 py-1 text-amber-300 border-b border-border shrink-0">
          the changes could not be listed{data.changes_error ? ` — ${data.changes_error}` : ''}
          {' '}— this is not the same as having none
        </div>
      )}

      <div className="flex-1 min-h-0 overflow-auto">
        {data.changes.length === 0 && data.runs.length === 0 && (
          <div className="p-3 text-fg-muted">
            {data.adopted
              ? 'no changes with a task file under this project’s changes directory'
              : 'nothing to drive here yet'}
          </div>
        )}

        {/* ⚠ `table-fixed` with explicit widths, and the reason cell truncates.
            Seen on the real screen with 59 changes: the reason column grew to fit
            its longest sentence, the name column wrapped to three lines, and the
            START BUTTON was pushed off the visible area — the primary control of
            the panel, reachable only by horizontal scrolling. A control that has
            to be hunted for is the layout failure `ui-quality.md` names, and no
            structural test could see it. */}
        <table className="w-full table-fixed">
          <colgroup>
            <col className="w-[16rem]" />
            <col />
            <col className="w-[5.5rem]" />
          </colgroup>
          <tbody>
            {data.changes.map(row => {
              const label = runnableLabel(row)
              const mark = attentionMark(row.runs)
              const marker = attentionLabel(mark)
              const isOpen = open[row.change]
              return (
                <>
                  <tr key={row.change} className="border-b border-border/60 align-top">
                    <td className="px-2 py-1">
                      {/* One line per change. `break-all` wrapped long names mid-word
                          and made every row two lines tall — seen on the real screen
                          with 59 of them, where the height cost more than the name
                          did. Truncated with the full name on hover instead. */}
                      <div className="flex items-baseline gap-2 min-w-0">
                        <button className="flex items-baseline gap-1 min-w-0 text-left
                                           hover:text-fg-strong"
                                title={row.change}
                                onClick={() => setOpen(o => ({ ...o, [row.change]: !isOpen }))}>
                          <span className="text-fg-muted shrink-0">{isOpen ? '▾' : '▸'}</span>
                          <span className="text-fg-strong truncate">{row.change}</span>
                        </button>
                        {/* ⚠ ON the collapsed row, not only inside it. Anything hidden
                            that is wrong must be marked where the reader is standing —
                            so this never truncates, whatever the name does. */}
                        {marker && (
                          <span className={`shrink-0 ${
                                  mark.measured ? 'text-red-400' : 'text-amber-300'}`}
                                title="runs needing attention in this change">
                            {marker}
                          </span>
                        )}
                        {row.runs.length > 0 && (
                          <span className="shrink-0 text-fg-muted">{row.runs.length}</span>
                        )}
                      </div>
                    </td>
                    <td className={`px-2 py-1 truncate ${
                      label.tone === 'ready' ? 'text-fg-strong'
                        : label.tone === 'unknown' ? 'text-amber-300' : 'text-fg-muted'}`}
                        title={label.detail || label.text}>
                      {label.text}
                    </td>
                    <td className="px-2 py-1 text-right whitespace-nowrap">
                      <button
                        className="px-2 py-0.5 border border-border rounded hover:text-fg-strong
                                   disabled:opacity-40 disabled:cursor-not-allowed"
                        disabled={label.tone !== 'ready' || busy === row.change}
                        title={label.tone !== 'ready'
                          ? label.text
                          : `start ${row.selected ? `group ${row.selected}` : 'the next group'}`}
                        onClick={() => start(row.change)}>
                        {busy === row.change ? 'starting…' : 'start'}
                      </button>
                    </td>
                  </tr>
                  {refusal?.change === row.change && (
                    <tr key={`${row.change}-refusal`}>
                      <td colSpan={3} className="px-2 py-1 text-red-400 border-b border-border/60">
                        refused — {refusal.text}
                      </td>
                    </tr>
                  )}
                  {isOpen && row.runs.map(r => {
                    const state = runState(r)
                    return (
                      <tr key={r.unit_id} className="border-b border-border/30">
                        <td className="px-2 py-1 pl-6">
                          <span className={STATE_TONE[state]} title={STATE_TITLE[state]}>
                            {state}
                          </span>
                          <span className="ml-2 text-fg-muted">{r.group ?? '—'}</span>
                          {r.set_aside?.question && (
                            <div className="text-amber-300">
                              asks: {r.set_aside.question}
                              {r.set_aside.task ? ` (${r.set_aside.task})` : ''}
                            </div>
                          )}
                          {r.gate?.state === 'failed' && (
                            <div className="text-red-400">
                              gate: {(r.gate.failures || []).join(', ') || r.gate.detail}
                              {r.gate.attribution ? ` — ${r.gate.attribution}` : ''}
                            </div>
                          )}
                          {r.reading?.reached_nothing && (
                            <div className="text-amber-300">
                              the project’s reading declaration reached nothing
                            </div>
                          )}
                        </td>
                        <td className="px-2 py-1 text-fg-muted">
                          {originLabel(r)}
                          {r.session_id
                            ? <span className="ml-2">session {r.session_id.slice(0, 8)}</span>
                            : <span className="ml-2">session unknown</span>}
                        </td>
                        <td className="px-2 py-1 text-right whitespace-nowrap">
                          {r.commit?.committed
                            ? <span className="text-fg-muted">{r.commit.sha?.slice(0, 8)}</span>
                            : <span className="text-fg-muted">{r.commit?.reason || 'no commit'}</span>}
                          {onOpenRecording && (
                            <button className="ml-2 text-fg-muted hover:text-fg-strong"
                                    title="open what this run’s session produced — a recording, not a live terminal"
                                    onClick={() => onOpenRecording(r.change, r.unit_id)}>
                              recording
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
