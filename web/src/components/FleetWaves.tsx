/**
 * Every known project's wave boards, from the fleet header.
 *
 * Asked for by the user on 2026-10-11: the projects keep wave boards (what is
 * planned, which wave is running, how fast it moves), each reachable only from
 * inside its own project. The fleet is the screen that sees every project, so it
 * carries them — one chip, one floating list, one click into the project or onto
 * the board page. "Do not overthink it" was part of the ask, so this is a list
 * of summaries, not a second board renderer.
 *
 * Two rules from the UI bar shape it:
 *
 * - **The list floats.** It is absolutely positioned under the header and moves
 *   nothing; it closes on its own control, on Escape and on a click outside.
 * - **Compacting never hides a failure.** The blocked count and the unreadable
 *   count sit on the CLOSED chip, so a stuck board is visible without opening
 *   anything.
 *
 * It fetches its own data, like the usage strip beside it: a slow board read must
 * not delay the agent list.
 */

import { useEffect, useRef, useState } from 'react'
import { ExternalLink, GitCommitHorizontal, Kanban, TriangleAlert, X } from 'lucide-react'

import { age } from '../lib/fleetAge'
import {
  barSegments, itemTotal, orderBoards, parseBoards, secondsSince, totals,
  type BarSegment, type ReadableBoard, type WaveBoard,
} from '../lib/fleetWaves'

/** Boards change on the scale of minutes; the agent poll is much faster. */
const READ_INTERVAL_MS = 60_000

const SEGMENT_TONE: Record<BarSegment['status'], string> = {
  done: 'bg-emerald-400',
  doing: 'bg-sky-400',
  blocked: 'bg-red-400',
  todo: 'bg-surface-line',
  skipped: 'bg-fg-ghost/40',
  other: 'bg-amber-400',
}

function Bar({ board }: { board: ReadableBoard }) {
  const segments = barSegments(board)
  const summary = segments.map(s => `${s.count} ${s.status}`).join(' · ')
  return (
    <span className="flex h-1.5 flex-1 min-w-[3rem] overflow-hidden rounded-sm bg-surface-line/40"
          role="img" aria-label={summary || 'no items'} title={summary || 'no items'}
          data-fleet-waves-bar={summary}>
      {segments.map(s => (
        <span key={s.status} className={SEGMENT_TONE[s.status]} style={{ width: `${s.percent}%` }} />
      ))}
    </span>
  )
}

/** The age cell's tooltip: when an item changed, and whether staleness was measured. */
function ageTitle(board: ReadableBoard): string {
  const changed = board.updated
    ? `An item last changed ${new Date(board.updated).toLocaleString()}`
    : 'No item carries a time'
  const reviewed = board.reviewed ? `; reviewed ${new Date(board.reviewed).toLocaleString()}` : ''
  const measured = board.commits_since_change === undefined || board.commits_since_change === null
    ? '; commits since: not measured'
    : `; ${board.commits_since_change} commit(s) on HEAD since`
  return changed + reviewed + measured
}

function staleTitle(board: ReadableBoard): string {
  const n = board.manual_open ?? 0
  return `${board.commits_since_change} commits on HEAD since this board last changed, `
    + `and ${n} open item${n === 1 ? '' : 's'} only an agent can move (no evidence, or blocked). `
    + 'Its statuses — blocked count included — may be out of date. The project\'s Stop hook asks its agent to review them.'
}

function BoardRow({ board, now, onProject }: {
  board: WaveBoard
  now: number
  onProject: (name: string) => void
}) {
  const project = (
    <button type="button" onClick={() => onProject(board.project)}
            className="text-left text-fg-strong hover:underline underline-offset-2 truncate"
            title={`Show ${board.project} in the fleet`}
            data-fleet-waves-project={board.project}>
      {board.project}
    </button>
  )

  if (board.unreadable) {
    return (
      <li className="grid grid-cols-1 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)] gap-x-3 py-1.5 text-xs"
          data-fleet-waves-row="unreadable">
        {project}
        <span className="text-amber-400 truncate" title={board.reason}>
          <TriangleAlert size={12} strokeWidth={1.75} className="inline mr-1 -mt-0.5" aria-hidden />
          {board.job} — {board.reason}
        </span>
      </li>
    )
  }

  const done = board.counts.done + board.counts.skipped
  const total = itemTotal(board)
  const since = secondsSince(board.updated, now)
  return (
    <li className="grid grid-cols-1 sm:grid-cols-[minmax(0,13rem)_minmax(0,1fr)] gap-x-3 gap-y-1 py-1.5 text-xs"
        data-fleet-waves-row={board.job}>
      {project}
      <span className="flex items-baseline gap-2 min-w-0">
        {board.artifact_url
          ? (
            <a href={board.artifact_url} target="_blank" rel="noopener noreferrer"
               className="text-fg-loud hover:underline underline-offset-2 truncate"
               title={`Open the board page: ${board.title}`}
               data-fleet-waves-link={board.job}>
              {board.title}
              <ExternalLink size={11} strokeWidth={1.75} className="inline ml-1 -mt-0.5 text-fg-muted" aria-hidden />
            </a>
          )
          : (
            <span className="text-fg-loud truncate" title={`${board.title} — the board page is not published yet`}
                  data-fleet-waves-unpublished={board.job}>
              {board.title} <span className="text-fg-muted">· not published</span>
            </span>
          )}
      </span>
      <span className="text-fg-muted truncate tabular-nums"
            title={board.current_wave ? `Current wave: ${board.current_wave.title || board.current_wave.id}` : 'Every wave is finished'}>
        {board.current_wave
          ? <>wave {board.current_wave.id}{board.waves ? `/${board.waves}` : ''}</>
          : 'finished'}
      </span>
      <span className="flex items-center gap-2 min-w-0">
        <Bar board={board} />
        <span className="tabular-nums text-fg-muted shrink-0" title={`${done} of ${total} items done or skipped`}>
          {done}/{total}
        </span>
        {board.counts.blocked > 0 && (
          <span className="tabular-nums text-red-400 shrink-0" title={`${board.counts.blocked} blocked`}
                data-fleet-waves-blocked={board.counts.blocked}>
            {board.counts.blocked} blocked
          </span>
        )}
        <span className="tabular-nums text-fg-muted shrink-0 w-8 text-right"
              title={ageTitle(board)}>
          {age(since)}
        </span>
        {board.stale === true && (
          <span className="inline-flex items-center gap-0.5 tabular-nums text-amber-400 shrink-0"
                title={staleTitle(board)}
                data-fleet-waves-stale={board.commits_since_change ?? ''}>
            <GitCommitHorizontal size={12} strokeWidth={1.75} aria-hidden />
            {board.commits_since_change} since
          </span>
        )}
      </span>
    </li>
  )
}

export default function FleetWaves({ selected, onSelectProject }: {
  selected: string | null
  onSelectProject: (name: string) => void
}) {
  const [boards, setBoards] = useState<WaveBoard[] | null>(null)
  const [open, setOpen] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const rootRef = useRef<HTMLSpanElement>(null)

  useEffect(() => {
    let cancelled = false
    const read = () => {
      fetch('/api/fleet/waveboards')
        .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
        .then(d => { if (!cancelled) { setBoards(parseBoards(d)); setNow(Date.now()) } })
        // A failed read keeps the last list; the ages on it keep growing, which
        // is the honest picture of a list that stopped refreshing.
        .catch(() => { if (!cancelled) setNow(Date.now()) })
    }
    read()
    const t = setInterval(read, READ_INTERVAL_MS)
    return () => { cancelled = true; clearInterval(t) }
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    const onDown = (e: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('pointerdown', onDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('pointerdown', onDown)
    }
  }, [open])

  if (!boards || boards.length === 0) return null
  const t = totals(boards)
  const ordered = orderBoards(boards, selected)
  const label = `${t.boards} wave board${t.boards === 1 ? '' : 's'}`
    + (t.blocked ? `, ${t.blocked} item${t.blocked === 1 ? '' : 's'} blocked` : '')
    + (t.unreadable ? `, ${t.unreadable} unreadable` : '')
    + (t.stale ? `, ${t.stale} stale` : '')

  return (
    <span ref={rootRef} className="inline-flex items-center shrink-0" data-fleet-waves={t.boards}>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
              aria-label={label} title={`${label}. Click for every project's boards.`}
              className={`inline-flex items-center gap-1 text-xs tabular-nums rounded px-1 border ${
                open ? 'border-sky-400/60 bg-sky-400/10 text-sky-300' : 'border-transparent text-fg-muted hover:text-fg-strong'}`}
              data-fleet-waves-toggle={open ? 'open' : 'closed'}>
        <Kanban size={13} strokeWidth={1.75} aria-hidden />
        {t.boards}
        {t.blocked > 0 && (
          <span className="text-red-400" data-fleet-waves-blocked-total={t.blocked}>· {t.blocked}</span>
        )}
        {t.stale > 0 && (
          <span className="text-amber-400 inline-flex items-center gap-0.5" data-fleet-waves-stale-total={t.stale}
                title={`${t.stale} board${t.stale === 1 ? '' : 's'} the repository has moved past`}>
            · <GitCommitHorizontal size={12} strokeWidth={1.75} aria-hidden />{t.stale}
          </span>
        )}
        {t.unreadable > 0 && (
          <span className="text-amber-400 inline-flex items-center gap-0.5" data-fleet-waves-unreadable={t.unreadable}>
            · <TriangleAlert size={12} strokeWidth={1.75} aria-hidden />{t.unreadable}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute left-2 md:left-6 top-full mt-1 z-30 w-[min(48rem,calc(100vw-1rem))]
                        max-h-[70vh] overflow-y-auto rounded border border-surface-line bg-surface-raised
                        px-3 py-2 shadow-lg"
             role="dialog" aria-label="Wave boards" data-fleet-waves-list={ordered.length}>
          <div className="flex items-center gap-2 pb-1 border-b border-surface-line">
            <span className="text-xs font-semibold text-fg-loud">Wave boards</span>
            <span className="hidden sm:inline text-xs text-fg-muted">— every project, from its tracked job file</span>
            <button type="button" onClick={() => setOpen(false)} aria-label="Close the wave boards"
                    className="ml-auto text-fg-muted hover:text-fg-strong" data-fleet-waves-close>
              <X size={14} strokeWidth={1.75} aria-hidden />
            </button>
          </div>
          <ul className="divide-y divide-surface-line/60">
            {ordered.map(b => (
              <BoardRow key={`${b.project}/${b.job}`} board={b} now={now}
                        onProject={name => { onSelectProject(name); setOpen(false) }} />
            ))}
          </ul>
        </div>
      )}
    </span>
  )
}
