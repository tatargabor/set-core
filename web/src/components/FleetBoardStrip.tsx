import { useEffect, useRef, useState } from 'react'
import { TriangleAlert } from 'lucide-react'

import { getProjectStatus, getStatusContract, type StatusCommandResult } from '../lib/api'
import { GAP_HINT } from '../lib/statusGapHints'

/**
 * The project's own board, as a strip under the active project's header row.
 *
 * The data comes from the project's `board` contract command — set-core models none
 * of it. Everything about the shape below is the producer's decision, recorded on the
 * channel (2026-08-30) and honoured here literally:
 *
 * - **`data.lanes` is rendered as a plain ordered array.** NOT `data.stageOrder`: the
 *   producer ships that field static, but it is inert on this side — no test, no
 *   consumer — and by this repo's own rule inert is not acceptance. Depending on it
 *   would be building on a field nobody here stands behind.
 * - **`unknown` is the ABSENCE of a lane, never a seventh one.** It is a scalar beside
 *   `lanes`, drawn as a hatched amber tail — this surface reserves amber for "unknown",
 *   and the hatch says "not a stage" the way a solid band would not. It is SURFACED,
 *   never folded into a band: on day one it held 149 of 180 cards, and folding that
 *   into a band would have been the calm the repo had not verified.
 * - **Honesty fields are shown, not swallowed.** `plannedNotOnBoard` and
 *   `coverage.complete: false` exist so a gap cannot look like an empty set; a strip
 *   that dropped them would undo their whole point.
 * - **A failed command renders as a gap with its reason** — never as a zero, never as
 *   silence. Same rule the Project Status page states, same reason.
 *
 * Gating: the strip mounts only for a project whose contract DECLARES `board`. A
 * project that publishes no board is not a failure and draws nothing — the same
 * suppression the agent tree applies to agent-less projects. Once the contract
 * declares it, though, every failure is on screen.
 */

/** The producer's per-lane entry. Read defensively: `data` is the project's domain. */
interface BoardLane {
  lane?: unknown
  count?: unknown
}

/** Refresh cadence. The transport layer caches answers for 30s, so asking faster
    would spawn the project's toolchain for a number it already refused to refresh. */
const POLL_MS = 30_000

function asCount(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 ? v : null
}

function asLaneList(v: unknown): BoardLane[] | null {
  if (!Array.isArray(v)) return null
  return v.filter(e => e !== null && typeof e === 'object') as BoardLane[]
}

/** One populated lane's legend entry, or null when it says nothing. */
function legendItem(l: BoardLane): { name: string; count: number } | null {
  const name = typeof l.lane === 'string' ? l.lane : null
  const count = asCount(l.count)
  return name && count !== null ? { name, count } : null
}

export default function FleetBoardStrip({ project }: { project: string }) {
  // `null` = the contract has not answered yet. `false` = it declares no board,
  // which is a decision of the project's, not a gap of anyone's.
  const [declares, setDeclares] = useState<boolean | null>(null)
  const [result, setResult] = useState<StatusCommandResult | null>(null)
  const [failed, setFailed] = useState<string | null>(null)

  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  // Does THIS project publish a board at all? One cheap manifest read decides
  // whether the strip exists here.
  useEffect(() => {
    setDeclares(null)
    setResult(null)
    setFailed(null)
    if (!project) return
    getStatusContract(project)
      .then(c => { if (alive.current) setDeclares(Boolean(c.configured && c.commands?.includes('board'))) })
      // A contract route that will not answer is the page's own breakage — the same
      // breakage the fleet payload above it is already showing. One missing strip
      // added to that would be noise, not signal.
      .catch(() => { if (alive.current) setDeclares(false) })
  }, [project])

  useEffect(() => {
    if (!declares || !project) return
    let timer: ReturnType<typeof setTimeout>

    const tick = () => {
      if (document.visibilityState !== 'visible') { timer = setTimeout(tick, POLL_MS); return }
      getProjectStatus(project, { commands: ['board'] })
        .then(res => {
          if (!alive.current) return
          setFailed(null)
          setResult(res.commands?.board ?? null)
        })
        .catch(e => { if (alive.current) setFailed(String(e?.message ?? e)) })
        .finally(() => { if (alive.current) timer = setTimeout(tick, POLL_MS) })
    }

    tick()
    return () => clearTimeout(timer)
  }, [declares, project])

  if (declares === null || declares === false) return null

  // The transport route itself is unreachable. A gap answer (below) is the project
  // saying it cannot; this is set-core saying IT cannot. Both belong on screen.
  if (failed) {
    return (
      <div data-fleet-board-strip="route-error"
           className="mt-1 rounded border border-amber-500/40 bg-amber-500/5 px-2 py-1.5 text-xs text-amber-300">
        board — could not reach the status route: {failed}
      </div>
    )
  }

  if (!result) return null

  if (!result.ok) {
    const hint = result.errorClass ? GAP_HINT[result.errorClass] : undefined
    return (
      <div data-fleet-board-strip="gap"
           className="mt-1 rounded border border-red-900/60 bg-red-950/20 px-2 py-1.5 text-xs text-red-300 space-y-0.5">
        <span className="font-medium">board</span>
        {result.errorClass && (
          <code className="ml-1.5 px-1 py-0.5 rounded bg-red-950/60 text-red-400">{result.errorClass}</code>
        )}
        {hint && <div className="text-red-200/80">{hint}</div>}
        {result.error && <div className="text-fg-muted">{result.error}</div>}
      </div>
    )
  }

  const data = (typeof result.data === 'object' && result.data !== null ? result.data : {}) as Record<string, unknown>
  const lanes = asLaneList(data.lanes)
  const unknown = asCount(data.unknown)
  const total = asCount(data.total)

  // A `lanes` that is not an array is the producer's contract having moved under us.
  // Said where the reader is standing — a strip that renders as if nothing happened
  // would be the false absence the honesty fields exist to prevent.
  if (lanes === null) {
    return (
      <div data-fleet-board-strip="shape"
           className="mt-1 rounded border border-amber-500/40 bg-amber-500/5 px-2 py-1.5 text-xs text-amber-300">
        board — the answer carries no lanes array; the project's board contract has moved
      </div>
    )
  }

  const items = lanes.map(legendItem)
  const laneSum = items.reduce((s, e) => s + (e?.count ?? 0), 0)
  const populated = items.filter((e): e is { name: string; count: number } => e !== null && e.count > 0)
  const known = laneSum + (unknown ?? 0)
  // Denominator for the band widths. The project's own `total` when it sums, its
  // own lane sum otherwise — never a constant, and never a division by zero: an
  // all-zero board draws its zero as words, not as a bar of nothing.
  const span = (total !== null && total >= known ? total : known) || 0

  const plannedOff = Array.isArray(data.plannedNotOnBoard) ? data.plannedNotOnBoard : []
  const coverage = (typeof data.coverage === 'object' && data.coverage !== null ? data.coverage : {}) as Record<string, unknown>
  const coverageIncomplete = coverage.complete === false

  const offBoardTitle = plannedOff
    .map(e => {
      const o = (e !== null && typeof e === 'object' ? e : {}) as Record<string, unknown>
      return [o.release, o.kind, o.ref].filter(Boolean).join(' ')
        + (o.reason ? ` — ${String(o.reason)}` : '')
    })
    .join('\n')

  return (
    <div data-fleet-board-strip className="mt-1 rounded border border-surface-line bg-surface-panel/40 px-2 py-1.5 space-y-1">
      <div className="flex items-center gap-2 text-xs min-w-0">
        <span
          className="text-fg-ghost shrink-0"
          title={result.generatedAt ? `as reported by the project at ${result.generatedAt}` : undefined}
        >board</span>
        {total !== null && <span className="text-fg-muted tabular-nums shrink-0">{total} cards</span>}
        <span className="ml-auto flex items-center gap-2 min-w-0">
          {plannedOff.length > 0 && (
            <span
              data-fleet-board-off-board={plannedOff.length}
              className="inline-flex items-center gap-1 text-amber-400 whitespace-nowrap"
              title={`a draft release plans this, and the board cannot see it yet:\n${offBoardTitle}`}
            >
              <TriangleAlert size={11} strokeWidth={1.75} aria-hidden />
              {plannedOff.length} planned off board
            </span>
          )}
          {coverageIncomplete && (
            <span
              data-fleet-board-coverage-incomplete
              className="inline-flex items-center gap-1 text-amber-400 whitespace-nowrap"
              title={typeof coverage.reason === 'string' ? coverage.reason : 'the project stated no reason'}
            >
              <TriangleAlert size={11} strokeWidth={1.75} aria-hidden />
              coverage incomplete
            </span>
          )}
        </span>
      </div>
      {span === 0 ? (
        <div className="text-xs text-fg-faint" data-fleet-board-empty>
          the project reports 0 cards
        </div>
      ) : (
        <>
          {/* The bands. Lane identity is carried by ORDER here and by NAME in the
              legend below — one blue holds all six, because a six-hue adjacency in a
              bar this thin is a reading test nobody should have to take, and the
              progression a ramp would encode is already told by the left-to-right
              order. The 2px gaps are load-bearing: they are what keeps neighbours
              from reading as one band. */}
          <div className="flex gap-0.5 h-2.5 min-w-0" data-fleet-board-bands>
            {items.map((e, i) => {
              const lane = lanes[i]?.lane
              const count = e?.count ?? 0
              return (
                <span
                  key={i}
                  data-fleet-board-lane={typeof lane === 'string' ? lane : undefined}
                  data-fleet-board-count={count}
                  className={`rounded-sm min-w-0 ${count > 0 ? 'bg-lane-fill' : ''}`}
                  style={count > 0 ? { flexGrow: count, flexBasis: 0 } : undefined}
                  title={typeof lane === 'string' ? `${lane}: ${count}` : undefined}
                />
              )
            })}
            {unknown !== null && unknown > 0 && (
              <span
                data-fleet-board-unknown={unknown}
                className="rounded-sm min-w-0 border border-amber-400/60"
                style={{
                  flexGrow: unknown, flexBasis: 0,
                  background: 'repeating-linear-gradient(45deg, rgba(251,191,36,0.45) 0 4px, transparent 4px 8px)',
                }}
                title={`unknown: ${unknown} — no signal matched these cards; it is the absence of a lane, not a stage`}
              />
            )}
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs min-w-0" data-fleet-board-legend>
            {populated.map(e => (
              <span key={e.name} className="text-fg-muted whitespace-nowrap">
                {e.name} <span className="tabular-nums text-fg-strong">{e.count}</span>
              </span>
            ))}
            {unknown !== null && unknown > 0 && (
              <span
                className="text-amber-400 whitespace-nowrap"
                data-fleet-board-unknown-legend={unknown}
                title="cards with no signal — the project names what was missing per card; the absence is surfaced, not folded into a lane"
              >
                unknown <span className="tabular-nums">{unknown}</span>
              </span>
            )}
          </div>
        </>
      )}
    </div>
  )
}
