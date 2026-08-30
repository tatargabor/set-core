import { useEffect, useRef, useState } from 'react'
import { Expand, Maximize2, Minimize2, RotateCw, Shrink, TriangleAlert, X } from 'lucide-react'

import { getProjectStatus, getStatusContract, type StatusCommandResult } from '../lib/api'
import { GAP_HINT } from '../lib/statusGapHints'
import { DOCK_CONTROLS, IconButton } from './TileControls'
import type { DockEdge } from '../lib/fleetDocks'

/**
 * The project's own board, under the active project's header row: the summary
 * strip, and beneath it the card columns.
 *
 * The data comes from the project's `board` contract command — set-core models none
 * of it. Everything about the shape below is the producer's decision, recorded on the
 * channel (2026-08-30) and honoured here literally:
 *
 * - **`data.lanes` is rendered as a plain ordered array.** NOT `data.stageOrder`: the
 *   producer ships that field static, but it is inert on this side — no test, no
 *   consumer — and by this repo's own rule inert is not acceptance. Depending on it
 *   would be building on a field nobody here stands behind.
 * - **Cards are placed by their OWN `lane` value; nothing is derived.** Column order
 *   and header counts come from the `lanes` array alone. If the producer's counts and
 *   its cards disagree, both render as given — the surface never reconciles, per the
 *   agent-api-parity precedent (recomputed values ran 412 % against 164 % actual).
 * - **The card face is set-core's own vocabulary** (`id`, `title`, `kind`, `blocked`,
 *   `tasksDone`, `tasksTotal`, `plannedRelease`, `note`, `openTarget`) — a project
 *   maps its field names onto it; none of theirs may appear in this code.
 * - **`unknown` is the ABSENCE of a lane, never a seventh one.** It is a scalar beside
 *   `lanes`, drawn hatched — this surface reserves amber for "unknown", and the hatch
 *   says "not a stage" the way a solid band would not. Cards with no usable lane join
 *   the hatched tray; the tray's header count is the scalar, not a count of tray cards.
 * - **Honesty fields are shown, not swallowed.** `plannedNotOnBoard` and
 *   `coverage.complete: false` exist so a gap cannot look like an empty set; a board
 *   that dropped them would undo their whole point.
 * - **A failed command renders as a gap with its reason** — never as zero columns,
 *   never as silence.
 *
 * Gating: the board mounts only for a project whose contract DECLARES `board`. A
 * project that publishes no board is not a failure and draws nothing — the same
 * suppression the agent tree applies to agent-less projects. Once the contract
 * declares it, though, every failure is on screen.
 */

/** The producer's per-lane entry. Read defensively: `data` is the project's domain. */
interface BoardLane {
  lane?: unknown
  count?: unknown
}

/**
 * The generic card face. `id` and `title` are the producer's values verbatim; the
 * rest is optional and renders only when present. No field here carries a meaning
 * set-core interprets — `blocked` is drawn as a mark, `note` as text, nothing more.
 */
interface BoardCard {
  id?: unknown
  title?: unknown
  lane?: unknown
  kind?: unknown
  blocked?: unknown
  tasksDone?: unknown
  tasksTotal?: unknown
  plannedRelease?: unknown
  note?: unknown
  /** The artefact the card IS, as a project-root-relative path — a file (the
      ticket's own document) or a directory (the change's folder). Declared BY
      THE PRODUCER, never derived here: set-core's own `path`-style fields on
      the producer's cards carried source documents, not the artefact (measured
      on the channel, 2026-08-30), so a click that guesses would look like it
      worked and open the wrong file. */
  openTarget?: unknown
}

/** The open target as a usable path, or null. A non-empty string only — anything
    else is as if absent, and the card stays a non-clicking face. */
function cardOpenTarget(c: BoardCard): string | null {
  return typeof c.openTarget === 'string' && c.openTarget ? c.openTarget : null
}

/** One card face. A DIV, not a button: the board is read-only, and a control that
    looks clickable but writes nothing is a promise the surface should not make.
    The ONE exception is a card whose producer declared `openTarget` — following it
    is a reading act (opening the artefact, through the page's `onOpenTarget`), it
    writes nothing, and the card stays a plain div whenever the field is absent or
    the page offers no way to open anything. */
function BoardCardFace({ c, onOpenTarget }: { c: BoardCard; onOpenTarget?: (path: string) => void }) {
  const id = cardId(c)
  const title = cardTitle(c)
  const blocked = blockedDetail(c)
  const progress = cardProgress(c)
  const openTarget = cardOpenTarget(c)
  const clickable = Boolean(openTarget && onOpenTarget)
  const face = (
    <>
      <div className="flex items-center gap-1.5 text-xs min-w-0">
        {id && <span className="text-fg-ghost tabular-nums shrink-0">{id}</span>}
        {typeof c.kind === 'string' && c.kind
          && <span className="text-fg-faint truncate">{c.kind}</span>}
        {blocked && (
          <span className="text-amber-400 shrink-0" title={blocked}>
            <TriangleAlert size={11} strokeWidth={1.75} aria-hidden />
          </span>
        )}
        {typeof c.plannedRelease === 'string' && c.plannedRelease && (
          <span className="ml-auto text-fg-ghost shrink-0">{c.plannedRelease}</span>
        )}
      </div>
      {title && (
        <div className="text-xs text-fg-normal leading-4 line-clamp-2" title={title}>{title}</div>
      )}
      {(progress || (typeof c.note === 'string' && c.note)) && (
        <div className="flex items-center gap-1.5 text-xs min-w-0">
          {progress && (
            <span className="text-fg-muted tabular-nums shrink-0"
                  title="tasks done / tasks total, as the project reports them">{progress}</span>
          )}
          {typeof c.note === 'string' && c.note && (
            <span className="text-fg-ghost truncate" title={c.note}>{c.note}</span>
          )}
        </div>
      )}
    </>
  )
  const shell = 'rounded border border-surface-line bg-surface-raised/40 px-1.5 py-1 space-y-0.5 min-w-0'
  if (clickable) {
    return (
      <button
        type="button"
        data-fleet-board-card={id ?? undefined}
        data-fleet-board-card-open={openTarget!}
        className={`${shell} w-full text-left cursor-pointer hover:border-fg-ghost/60`}
        title={`open ${openTarget}`}
        onClick={() => onOpenTarget!(openTarget!)}
      >{face}</button>
    )
  }
  return (
    <div data-fleet-board-card={id ?? undefined} className={shell}>{face}</div>
  )
}

/**
 * The last answer and the contract decision, per project, IN MEMORY ONLY.
 *
 * The board unmounts on every project and view switch, and state that lives in
 * the component dies with it — measured as the board re-asking the project and
 * showing a loading gap every time the reader came back, while the terminals
 * around it appeared to remember. They remembered because their data is held
 * above the switch; the board now does the same. Render the cached answer
 * INSTANTLY, revalidate in the background. Dies with the page, never written
 * anywhere — the same confidentiality line the transport layer holds.
 */
const declaresCache = new Map<string, boolean>()
const answerCache = new Map<string, { result: StatusCommandResult; at: number }>()

/** TESTS ONLY: the caches are per-process by design; a suite that mounts the
    board for many fake projects must start each test from the same ground. */
export function _resetBoardCachesForTests() {
  declaresCache.clear()
  answerCache.clear()
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

/** The cards as the generic face, or null when the field is present but unreadable.
    `undefined` when the producer publishes no cards at all — a strip-only board. */
function asCardList(v: unknown): BoardCard[] | null | undefined {
  if (v === undefined) return undefined
  if (!Array.isArray(v)) return null
  return v.filter(e => e !== null && typeof e === 'object') as BoardCard[]
}

function cardId(c: BoardCard): string | null {
  if (typeof c.id === 'string') return c.id
  if (typeof c.id === 'number' && Number.isFinite(c.id)) return String(c.id)
  return null
}

function cardTitle(c: BoardCard): string | null {
  return typeof c.title === 'string' && c.title ? c.title : null
}

/** Blocked is drawn as a mark with whatever the producer said about it — never
    interpreted. A `true` with no detail is a mark with a generic title. */
function blockedDetail(c: BoardCard): string | null {
  if (!c.blocked) return null
  if (typeof c.blocked === 'object' && c.blocked !== null
      && typeof (c.blocked as Record<string, unknown>).detail === 'string') {
    return (c.blocked as Record<string, unknown>).detail as string
  }
  return 'the project marks this blocked'
}

function cardProgress(c: BoardCard): string | null {
  const done = asCount(c.tasksDone)
  const totalCount = asCount(c.tasksTotal)
  return done !== null && totalCount !== null ? `${done}/${totalCount}` : null
}

/** An empty column says so, in faint text — one that says nothing reads as
    "not drawn yet" (asked for 2026-08-30). The two empty shapes get DIFFERENT
    words, because a gap is not a zero: `0 cards` is the project's OWN zero,
    straight from its count; a positive count with no cards placed is the
    counts-vs-cards disagreement, which this surface renders unreconciled —
    worded so it cannot read as a zero. */
function ColumnEmpty({ count, placed }: { count: number; placed: number }) {
  if (placed > 0) return null
  if (count === 0) {
    return <div className="text-xs text-fg-faint px-1 py-0.5" data-fleet-board-col-empty="zero">0 cards</div>
  }
  return (
    <div className="text-xs text-fg-faint px-1 py-0.5" data-fleet-board-col-empty="mismatch"
         data-fleet-board-col-mismatch={count}
         title={`the project counts ${count} here, but no card carries this lane`}>
      no cards placed
    </div>
  )
}

export default function FleetBoard({
  project, projectName, showBoard = true, onClose, onDock, dockedEdge, maximised, onMaximise,
  fullscreen, onFullscreen, onOpenTarget,
}: {
  project: string
  /** Set by a PANEL context: names the title bar and turns on the window chrome.
      The inline summary under the project header passes nothing — a strip has
      no window to control. */
  projectName?: string
  /** Whether the card columns render. The panel owns them when it is open;
      the inline copy then stays the summary line only, so one board is never
      drawn twice on one screen. */
  showBoard?: boolean
  onClose?: () => void
  onDock?: (edge: DockEdge | null) => void
  dockedEdge?: DockEdge | null
  maximised?: boolean
  onMaximise?: () => void
  /** Full screen — the whole layout, not just the tile's grid cell. */
  fullscreen?: boolean
  onFullscreen?: () => void
  /** Opens a card's declared artefact — the page's file view. Reading only: the
      board itself still has no write path. Absent = every card stays a plain
      div, even one that declares an open target. */
  onOpenTarget?: (path: string) => void
}) {
  // Seeded from the per-process cache: a board the reader has already seen this
  // session renders its last answer INSTANTLY on remount, then revalidates.
  // `null` = the contract has not answered yet. `false` = it declares no board,
  // which is a decision of the project's, not a gap of anyone's.
  const [declares, setDeclares] = useState<boolean | null>(() => declaresCache.get(project) ?? null)
  const [result, setResult] = useState<StatusCommandResult | null>(() => answerCache.get(project)?.result ?? null)
  const [answeredAt, setAnsweredAt] = useState<number | null>(() => answerCache.get(project)?.at ?? null)
  const [failed, setFailed] = useState<string | null>(null)

  const alive = useRef(true)
  useEffect(() => {
    alive.current = true
    return () => { alive.current = false }
  }, [])

  // Does THIS project publish a board at all? One cheap manifest read decides
  // whether the strip exists here.
  useEffect(() => {
    setDeclares(declaresCache.get(project) ?? null)
    setResult(answerCache.get(project)?.result ?? null)
    setAnsweredAt(answerCache.get(project)?.at ?? null)
    setFailed(null)
    if (!project) return
    getStatusContract(project)
      .then(c => {
        const ok = Boolean(c.configured && c.commands?.includes('board'))
        declaresCache.set(project, ok)
        if (alive.current) setDeclares(ok)
      })
      // A contract route that will not answer is the page's own breakage — the same
      // breakage the fleet payload above it is already showing. One missing strip
      // added to that would be noise, not signal.
      .catch(() => { if (alive.current) setDeclares(false) })
  }, [project])

  const fetchRef = useRef<((force: boolean) => void) | null>(null)

  useEffect(() => {
    if (!declares || !project) return
    let timer: ReturnType<typeof setTimeout>
    let inFlight = false

    const tick = (force: boolean) => {
      // A poll that is still running is not raced by the next one: the board is
      // read-only, so there is nothing to lose by letting the slow answer land.
      if (inFlight) return
      inFlight = true
      if (document.visibilityState !== 'visible' && !force) {
        inFlight = false
        timer = setTimeout(() => tick(false), POLL_MS)
        return
      }
      getProjectStatus(project, { commands: ['board'], refresh: force })
        .then(res => {
          if (!alive.current) return
          setFailed(null)
          const board = res.commands?.board ?? null
          if (board) {
            const at = Date.now()
            answerCache.set(project, { result: board, at })
            setResult(board)
            setAnsweredAt(at)
          }
        })
        .catch(e => { if (alive.current) setFailed(String(e?.message ?? e)) })
        .finally(() => {
          inFlight = false
          if (alive.current) timer = setTimeout(() => tick(false), POLL_MS)
        })
    }

    fetchRef.current = (force: boolean) => tick(force)
    tick(false)
    return () => { clearTimeout(timer); fetchRef.current = null }
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

  // The card columns. Placement is by each card's OWN lane value; the headers are
  // the producer's counts. A present-but-unreadable `cards` field is the contract
  // having moved — said, not swallowed; an absent one is a strip-only board.
  const cards = asCardList(data.cards)
  const bandNames = items.filter((e): e is { name: string; count: number } => e !== null)
    .map(e => e.name)
  const inBand = (lane: unknown): lane is string =>
    typeof lane === 'string' && bandNames.includes(lane)
  const trayCards = cards === null ? [] : (cards ?? []).filter(c => !inBand(c.lane))
  const cardsByLane = new Map<string, BoardCard[]>()
  if (cards !== null && cards !== undefined) {
    for (const c of cards) {
      if (!inBand(c.lane)) continue
      const list = cardsByLane.get(c.lane as string) ?? []
      list.push(c)
      cardsByLane.set(c.lane as string, list)
    }
  }
  const countByLane = new Map(items
    .filter((e): e is { name: string; count: number } => e !== null)
    .map(e => [e.name, e.count]))

  // Windowed (panel/fullscreen) contexts FILL their window; the inline strip
  // under the project header stays bounded. See the note on the panel body.
  const fill = Boolean(projectName)

  const body = (
    <>
      <div className="flex items-center gap-2 text-xs min-w-0">
        <span
          className="text-fg-ghost shrink-0"
          title={result.generatedAt ? `as reported by the project at ${result.generatedAt}` : undefined}
        >board</span>
        {total !== null && <span className="text-fg-muted tabular-nums shrink-0">{total} cards</span>}
        {/* WHEN this answer was taken, where the reader is standing — a strip
            that refreshes silently is a strip whose freshness has to be guessed
            (asked 2026-08-30). The clock time of the answer, not an age: an age
            would need a per-second re-render of every card to stay true. */}
        {answeredAt !== null && (
          <span className="text-fg-ghost tabular-nums shrink-0"
                title="when this answer was taken; it re-asks on its own about every 30s while the page is visible">
            · {new Date(answeredAt).toLocaleTimeString()}
          </span>
        )}
        <IconButton
          icon={RotateCw}
          testId="board-refresh"
          tone="ghost"
          label="ask the project again now — this also skips the few seconds of answer cache on set-core's side"
          onClick={() => fetchRef.current?.(true)}
        />
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
          {/* The card columns. Header counts are the producer's; the cards are
              placed by their own lane value and never re-sorted into agreement
              with the counts. Scroll lives in each column — the board is bounded
              so 180 cards cannot take the screen. */}
          {showBoard && cards !== null && (
            <div className={`flex gap-1.5 min-w-0 overflow-x-auto ${fill ? 'flex-1 min-h-0' : ''}`} data-fleet-board-columns>
              {bandNames.map(name => (
                <div key={name} data-fleet-board-col={name}
                     className={`flex-1 min-w-28 space-y-1 ${fill ? 'flex flex-col min-h-0' : ''}`}>
                  <div className="flex items-baseline gap-1.5 text-xs border-b border-surface-edge/70 pb-0.5">
                    <span className="text-fg-muted truncate">{name}</span>
                    <span className="text-fg-ghost tabular-nums shrink-0"
                          title="as the project counts it">{countByLane.get(name)}</span>
                  </div>
                  <div className={`space-y-1 overflow-y-auto ${fill ? 'flex-1 min-h-0' : 'max-h-72'}`}>
                    {(cardsByLane.get(name) ?? []).map((c, i) => (
                      <BoardCardFace key={cardId(c) ?? i} c={c} onOpenTarget={onOpenTarget} />
                    ))}
                    <ColumnEmpty count={countByLane.get(name) ?? 0}
                                 placed={(cardsByLane.get(name) ?? []).length} />
                  </div>
                </div>
              ))}
              {(unknown !== null || trayCards.length > 0) && (
                <div data-fleet-board-tray
                     className={`flex-1 min-w-28 space-y-1 ${fill ? 'flex flex-col min-h-0' : ''}`}>
                  <div
                    className="flex items-baseline gap-1.5 text-xs pb-0.5 text-amber-400"
                    style={{ background:
                      'repeating-linear-gradient(45deg, rgba(251,191,36,0.12) 0 4px, transparent 4px 8px)' }}
                    title="cards with no lane — the absence of a band, not a seventh band"
                  >
                    <span className="shrink-0">unknown</span>
                    <span className="tabular-nums shrink-0"
                          title="the project's own unknown figure">{unknown ?? trayCards.length}</span>
                  </div>
                  <div className={`space-y-1 overflow-y-auto ${fill ? 'flex-1 min-h-0' : 'max-h-72'}`}>
                    {trayCards.map((c, i) => (
                      <BoardCardFace key={cardId(c) ?? i} c={c} onOpenTarget={onOpenTarget} />
                    ))}
                    <ColumnEmpty count={unknown ?? trayCards.length} placed={trayCards.length} />
                  </div>
                </div>
              )}
            </div>
          )}
          {showBoard && cards === null && (
            <div className="text-xs text-amber-300" data-fleet-board-cards-shape>
              board — the answer carries a cards field this build cannot read
            </div>
          )}
        </>
      )}
    </>
  )

  // PANEL context: a title bar with the same window chrome every other project
  // panel carries — four dock edges, maximise, close (asked for 2026-08-30:
  // the board must not read as a second-class panel next to the agent ones).
  if (projectName) {
    return (
      <div className="flex flex-col h-full min-h-0" data-fleet-board-panel={projectName}>
        <div className="flex items-center gap-1.5 px-2 py-1 border-b border-surface-line shrink-0">
          <span className="text-xs text-fg-strong shrink-0">board</span>
          <span className="text-xs text-fg-ghost truncate">{projectName}</span>
          <span className="ml-auto flex items-center gap-0.5 shrink-0">
            {onDock && (
              <span className="flex items-center" data-fleet-board-dock={dockedEdge ?? 'grid'}>
                {DOCK_CONTROLS.map(({ edge, icon, where }) => (
                  <IconButton
                    key={edge}
                    icon={icon}
                    testId={`board-dock-${edge}`}
                    active={dockedEdge === edge}
                    label={dockedEdge === edge
                      ? `bring the board back into the grid from the ${where}`
                      : `put the board ${where} — the panel takes its space out of the grid`}
                    onClick={() => onDock(dockedEdge === edge ? null : edge)}
                  />
                ))}
              </span>
            )}
            {onMaximise && (
              <IconButton
                icon={maximised ? Minimize2 : Maximize2}
                testId="board-max"
                active={maximised}
                mark={{ 'data-fleet-board-maximised': maximised ? 'on' : 'off' }}
                label={maximised
                  ? 'back to the size it had — the agents get their room back'
                  : 'as large as this placement allows — in the grid the agents move to the strip above; on an edge the band takes the room the layout can spare'}
                onClick={onMaximise}
              />
            )}
            {onFullscreen && (
              <IconButton
                icon={fullscreen ? Shrink : Expand}
                testId="board-fullscreen"
                active={fullscreen}
                mark={{ 'data-fleet-board-fullscreen': fullscreen ? 'on' : 'off' }}
                label={fullscreen
                  ? 'back out of full screen — the column, the docks and the sidebar come back'
                  : 'full screen — the board takes the whole layout, not just its grid cell'}
                onClick={onFullscreen}
              />
            )}
            {onClose && (
              <IconButton icon={X} testId="board-close" label="close the board" onClick={onClose} />
            )}
          </span>
        </div>
        {/* A windowed board FILLS its window: the body is a flex column and the
            card columns take the room below the strip, each scrolling its own
            cards — a max-height cap here is what left two thirds of the full
            screen dark (seen on screen, 2026-08-30). The inline strip under the
            project header keeps the cap; it shares its page with real content. */}
        <div className={`flex-1 min-h-0 overflow-y-auto px-2 py-1.5 ${fill ? 'flex flex-col' : ''}`}>
          <div data-fleet-board-strip className={`space-y-1 ${fill ? 'flex flex-1 min-h-0 flex-col' : ''}`}>{body}</div>
        </div>
      </div>
    )
  }

  // INLINE context: the summary card under the project header, as shipped.
  return (
    <div data-fleet-board-strip className="mt-1 rounded border border-surface-line bg-surface-panel/40 px-2 py-1.5 space-y-1">
      {body}
    </div>
  )
}
