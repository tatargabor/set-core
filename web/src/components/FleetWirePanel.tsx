import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import {
  computeRoomMatrix, cellTitle, directGroupTitle, ageBucket, ageLine,
  HEADER_Y,
  type ChannelsPayload, type RoomMatrix,
} from '../lib/fleetWireLayout'

/**
 * The wire gutter — live agents on the left, the channels between them in
 * the strip this component occupies.
 *
 * ## What anchors where
 *
 * Terminals are measured, not laid out: every `[data-fleet-agent-row]` in the
 * document is a live agent row, and its rectangle relative to THIS container
 * decides where its terminal sits. Measurement re-runs on poll answers, on
 * scroll (capture — the column scrolls inside itself), on resize, and on a
 * slow belt interval, because a row can move for a reason none of those fire
 * (a group collapsed elsewhere, a font settled). A stale rectangle draws a
 * wire to nowhere, which is the one failure this screen must not have
 * silently — so re-measuring is cheap and frequent rather than clever.
 *
 * ## What the gutter shows when it cannot see the source
 *
 * `sourceAvailable: false` renders one sentence and no sockets — never an
 * all-unenrolled board, which would report "nobody is enrolled" about a bus
 * nobody could ask. The distinction is the screen's own rule: not-enrolled is
 * a measurement, source-down is an absence of one.
 */

/** The gutter's width in px. Wide enough for three lanes; the main pane's
    splitter still owns the rest, so this is a claim on 140px, not on the edge. */
export const WIRE_GUTTER_WIDTH = 140
/** Wider gutter for many columns — sixteen rooms in 140px is 8px per column,
    which no name fits. Computed rooms choose the width; the layout is then
    computed FOR the chosen width (pure function, run twice). */
export const WIRE_GUTTER_MAX = 220

/** Belt re-measure interval. The poll redraws anyway; this catches layout
    shifts between polls (collapse, drag, font settle) at low cost. */
const MEASURE_BELT_MS = 2000

/** One line of the legend: a swatch drawn with the drawing's OWN classes,
    then the sentence. `children` carry the swatch's SVG shape. */
function LegendRow({ swatch, children }: {
  swatch: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <div className="flex items-start gap-1.5">
      <svg width="10" height="10" viewBox="0 0 10 10" className="mt-0.5 shrink-0" aria-hidden>
        {swatch}
      </svg>
      <span>{children}</span>
    </div>
  )
}

export default function FleetWirePanel({ payload }: { payload: ChannelsPayload | null }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [layout, setLayout] = useState<RoomMatrix | null>(null)
  /** Pair rooms fold into one `+N direct` column until expanded. Local on
      purpose: the fold is a reading aid for THIS visit, not an arrangement —
      the server-side layout document holds positions, not view toggles. */
  const [directOpen, setDirectOpen] = useState(false)
  /** Hover focus. A row hover (agent anywhere on the board) or a column hover
      (room in this gutter) dims every cell that does not match — the answer
      to "which of these dots are mine / whose is this column". */
  const [hoverPid, setHoverPid] = useState<number | null>(null)
  const [hoverRoom, setHoverRoom] = useState<string | null>(null)

  const measure = useCallback(() => {
    const container = containerRef.current
    if (!container) return
    const box = container.getBoundingClientRect()
    const rows: { pid: number; top: number; bottom: number }[] = []
    for (const el of document.querySelectorAll('[data-fleet-agent-row]')) {
      const pid = Number((el as HTMLElement).dataset.fleetAgentRow)
      if (!Number.isFinite(pid)) continue
      const rect = (el as HTMLElement).getBoundingClientRect()
      if (rect.height === 0) continue
      rows.push({ pid, top: rect.top - box.top, bottom: rect.bottom - box.top })
    }
    // Two passes: the first counts columns, the second lays them out in the
    // width their count chose. Pure function, so the double run is free.
    const probe = computeRoomMatrix({ payload, rows, height: box.height, gutterWidth: WIRE_GUTTER_MAX, collapseDirect: !directOpen })
    const width = probe.columns.length > 8 ? WIRE_GUTTER_MAX : WIRE_GUTTER_WIDTH
    setLayout({ ...probe, width })
  }, [payload, directOpen])

  useLayoutEffect(measure, [measure])

  useEffect(() => {
    // Rows live in the SIBLING column, so their hover never reaches this
    // component's own tree — the listener rides the document instead. A row
    // hovered anywhere on the board focuses this agent's cells.
    const onOver = (event: MouseEvent) => {
      const row = (event.target as HTMLElement | null)?.closest?.('[data-fleet-agent-row]')
      const pid = row ? Number((row as HTMLElement).dataset.fleetAgentRow) : NaN
      setHoverPid(Number.isFinite(pid) ? pid : null)
    }
    document.addEventListener('mouseover', onOver)
    return () => document.removeEventListener('mouseover', onOver)
  }, [])

  useEffect(() => {
    // Capture catches the column's INTERNAL scrolls, which do not bubble.
    window.addEventListener('scroll', measure, true)
    window.addEventListener('resize', measure)
    const belt = setInterval(measure, MEASURE_BELT_MS)
    return () => {
      window.removeEventListener('scroll', measure, true)
      window.removeEventListener('resize', measure)
      clearInterval(belt)
    }
  }, [measure])

  const sourceDown = payload?.sourceAvailable === false
  const [legendOpen, setLegendOpen] = useState(false)
  /** The room card: one room's members and write age, opened by clicking its
      column. Seat names and ages ONLY — the payload carries no message bodies,
      and the card must not become a reason to change that. */
  const [cardRoom, setCardRoom] = useState<string | null>(null)

  // Escape closes whatever overlay holds the focus — the card first.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setCardRoom(null)
        setLegendOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div
      ref={containerRef}
      data-fleet-wire-gutter
      className="relative h-full shrink-0 border-l border-surface-line bg-surface-panel/30"
      style={{ width: layout?.width ?? WIRE_GUTTER_WIDTH }}
    >
      {/* The legend, toggled by its icon. The swatches render with the SAME
          classes the drawing uses, so the two cannot drift apart: restyle the
          wires and the legend restyles with them. Bottom-right, because the
          room labels own the top band. */}
      <button
        type="button"
        data-fleet-wire-legend-toggle
        aria-expanded={legendOpen}
        title="what the wires mean"
        onClick={() => setLegendOpen(o => !o)}
        className={`absolute bottom-1 right-1 z-10 h-5 w-5 rounded border text-[10px] leading-none ${
          legendOpen
            ? 'border-fg-strong bg-fg-strong text-surface-panel'
            : 'border-surface-line text-fg-muted hover:text-fg-strong'
        }`}
      >
        ?
      </button>
      {legendOpen && (
        <div
          data-fleet-wire-legend
          className="absolute bottom-7 left-1 right-1 z-10 space-y-1 rounded border border-surface-line bg-surface-panel p-1.5 text-[10px] leading-tight text-fg-muted shadow-lg"
        >
          <LegendRow swatch={<circle cx="5" cy="5" r="4" className="fleet-wire-cell-sender fleet-wire-cell-live" />}>
            pulsing — wrote LAST here, under 2 min ago
          </LegendRow>
          <LegendRow swatch={<circle cx="5" cy="5" r="4" className="fleet-wire-cell-sender" />}>
            filled — wrote LAST here, 2–30 min back
          </LegendRow>
          <LegendRow swatch={<circle cx="5" cy="5" r="3.5" className="fleet-wire-cell-member-active" />}>
            thick ring — in the room, written to &lt;30 min ago
          </LegendRow>
          <LegendRow swatch={<circle cx="5" cy="5" r="3.5" className="fleet-wire-cell-member-idle" />}>
            thin dim ring — in the room, idle
          </LegendRow>
          <LegendRow swatch={<span className="inline-block h-2 w-2" />}>
            blank — not a member of that room
          </LegendRow>
          <LegendRow swatch={<rect x="1" y="1" width="2" height="8" className="fleet-wire-terminal" />}>
            tick — enrolled agent
          </LegendRow>
          <LegendRow swatch={<rect x="1" y="1" width="6" height="7" rx="1" className="fleet-wire-socket fleet-wire-socket-drift" />}>
            amber socket — session drift, re-enrol
          </LegendRow>
          <LegendRow swatch={<rect x="1" y="1" width="6" height="7" rx="1" className="fleet-wire-socket" />}>
            hollow socket — not enrolled
          </LegendRow>
          <div className="border-t border-surface-line pt-1">
            columns lead with the most recently written room; hover any dot for the room, its members and the write age
          </div>
        </div>
      )}
      {sourceDown ? (
        <div data-fleet-wire-source-down
             className="px-2 py-2 text-xs text-amber-300">
          the channel source is unreachable — wires are paused, not empty
        </div>
      ) : (
        layout && (
          <svg
            data-fleet-wire-svg
            width="100%"
            height="100%"
            className="pointer-events-none select-none"
          >
            {/* Column guide lines and their VERTICAL names, pinned to the top
                band. The guide runs full height — it is the column's track —
                and its tone is the room's THREE-STEP age: fresh (under 2 min,
                being written to right now), warm (inside the 30-min window),
                idle. Click opens the room card; the folded pair-group expands. */}
            {layout.columns.map(col => {
              const age = ageBucket(col.lastActivity, Date.now(), payload?.activityWindowSeconds)
              const colCls = age === 'fresh' ? 'fleet-wire-col fleet-wire-col-fresh'
                : age === 'warm' ? 'fleet-wire-col fleet-wire-col-warm'
                : 'fleet-wire-col fleet-wire-col-idle'
              const labelCls = age === 'fresh' ? 'fleet-wire-label fleet-wire-label-fresh'
                : age === 'warm' ? 'fleet-wire-label fleet-wire-label-warm'
                : 'fleet-wire-label fleet-wire-label-idle'
              return (
              <g key={`col-${col.room}`}
                 className="pointer-events-auto fleet-wire-col-hit"
                 onPointerEnter={() => setHoverRoom(col.room)}
                 onPointerLeave={() => setHoverRoom(r => (r === col.room ? null : r))}
                 onClick={() => {
                   // The fold expands on click; every real room opens its card.
                   if (col.isDirectGroup) setDirectOpen(true)
                   else setCardRoom(col.room)
                 }}
              >
                <title>{col.directCount != null
                  ? directGroupTitle(col.directCount, col.lastActivity, Date.now())
                  : cellTitle(col.room, col.memberSeats, col.lastActivity, Date.now())}</title>
                <line
                  data-fleet-wire-column={col.room}
                  data-fleet-wire-col-age={age}
                  x1={col.x} y1={34} x2={col.x} y2="100%"
                  className={colCls}
                />
                <text
                  data-fleet-wire-label={col.room}
                  data-fleet-wire-direct-group={col.isDirectGroup ? 'true' : undefined}
                  x={col.x + 3}
                  y={HEADER_Y}
                  transform={`rotate(90 ${col.x + 3} ${HEADER_Y})`}
                  className={labelCls}
                >
                  {col.label ?? (col.room.length > 14 ? `${col.room.slice(0, 13)}…` : col.room)}
                </text>
              </g>
              )
            })}
            {/* Membership cells. The room's SENDER renders filled (animated
                while fresh) — in a grid, who-sent is WHICH CELL IS FILLED.
                A row or column hover dims every cell that does not match. */}
            {layout.cells.map(cell => {
              const focusActive = hoverPid != null || hoverRoom != null
              const focused = (hoverPid == null || cell.pid === hoverPid)
                && (hoverRoom == null || cell.room === hoverRoom)
              const dim = focusActive && !focused
              const roomCol = layout.columns.find(c => c.room === cell.room)
              // The pulse means "being written to RIGHT NOW" (<2 min); a room
              // merely inside the 30-min window holds a still-filled sender.
              const bucket = ageBucket(roomCol?.lastActivity ?? null, Date.now(), payload?.activityWindowSeconds)
              const base = cell.role === 'sender'
                ? (bucket === 'fresh'
                    ? 'fleet-wire-cell fleet-wire-cell-sender fleet-wire-cell-live'
                    : 'fleet-wire-cell fleet-wire-cell-sender')
                : (cell.active
                    ? 'fleet-wire-cell fleet-wire-cell-member-active'
                    : 'fleet-wire-cell fleet-wire-cell-member-idle')
              return (
                <g key={cell.key} className="pointer-events-auto">
                  <title>{roomCol?.directCount != null
                    ? directGroupTitle(roomCol.directCount, roomCol.lastActivity, Date.now())
                    : cellTitle(cell.room, roomCol?.memberSeats ?? [], roomCol?.lastActivity ?? null, Date.now())}</title>
                  {cell.role === 'sender' ? (
                    <circle
                      data-fleet-wire-cell={cell.room}
                      data-fleet-wire-role="sender"
                      data-fleet-wire-active={cell.active ? 'true' : undefined}
                      data-fleet-wire-dim={dim ? 'true' : undefined}
                      cx={cell.x} cy={cell.y} r={4}
                      className={dim ? `${base} fleet-wire-cell-dim` : base}
                    />
                  ) : (
                    <circle
                      data-fleet-wire-cell={cell.room}
                      data-fleet-wire-role="member"
                      data-fleet-wire-active={cell.active ? 'true' : undefined}
                      data-fleet-wire-dim={dim ? 'true' : undefined}
                      cx={cell.x} cy={cell.y} r={3.5}
                      className={dim ? `${base} fleet-wire-cell-dim` : base}
                    />
                  )}
                </g>
              )
            })}
            {layout.terminals.map(t => (
              <rect
                key={t.pid}
                data-fleet-wire-terminal={t.pid}
                x={0} y={t.y - 4} width={2.5} height={8}
                className="fleet-wire-terminal"
              >
                <title>{t.seat ?? `agent ${t.pid}`}</title>
              </rect>
            ))}
            {layout.sockets.map(s => (
              <rect
                key={s.pid}
                data-fleet-wire-socket={s.pid}
                data-fleet-wire-socket-state={s.projectSeatCount ? 'drift' : 'unenrolled'}
                x={0} y={s.y - 3.5} width={6} height={7}
                className={s.projectSeatCount
                  ? 'fleet-wire-socket fleet-wire-socket-drift'
                  : 'fleet-wire-socket'}
              >
                <title>{s.projectSeatCount
                  ? 'seats exist for this project, but none carries THIS session (session drift) — re-enrol: sac install'
                  : 'not enrolled on the channel bus — run `sac install` in that project to enrol it'}</title>
              </rect>
            ))}
          </svg>
        )
      )}
      {/* The room card. Seat names and ages only, never message content —
          the payload's structural line stops exactly short of bodies, and
          this card is why that line must hold. */}
      {!sourceDown && cardRoom && layout && (() => {
        const col = layout.columns.find(c => c.room === cardRoom)
        if (col == null) return null
        const senderSeats = new Set(
          layout.cells
            .filter(c => c.room === col.room && c.role === 'sender')
            .map(c => payload?.nodes?.find(n => n.pid === c.pid)?.seat)
            .filter((s): s is string => typeof s === 'string'),
        )
        return (
          <div
            data-fleet-wire-card={col.room}
            className="absolute left-1 right-1 top-8 z-20 space-y-1 rounded border border-surface-line bg-surface-panel p-2 text-[10px] leading-tight text-fg-muted shadow-lg"
          >
            <div className="flex items-center justify-between gap-1">
              <span data-fleet-wire-card-title className="text-xs text-fg-strong truncate">
                {col.label ?? col.room}
              </span>
              <button
                type="button"
                data-fleet-wire-card-close
                aria-label="close room card"
                onClick={() => setCardRoom(null)}
                className="shrink-0 h-4 w-4 rounded border border-surface-line text-[10px] leading-none text-fg-muted hover:text-fg-strong"
              >
                ×
              </button>
            </div>
            <div data-fleet-wire-card-age>
              newest write {ageLine(col.lastActivity, Date.now() / 1000)}
              {col.directCount != null ? ` across ${col.directCount} direct rooms` : ''}
            </div>
            <ul className="space-y-0.5">
              {col.memberSeats.map(seat => (
                <li key={seat} data-fleet-wire-card-seat={seat}>
                  {seat}
                  {senderSeats.has(seat) ? ' — wrote last' : ''}
                </li>
              ))}
            </ul>
            <div className="flex items-center gap-2 border-t border-surface-line pt-1">
              {col.isDirectGroup && (
                <button
                  type="button"
                  data-fleet-wire-card-expand
                  onClick={() => { setDirectOpen(true); setCardRoom(null) }}
                  className="rounded border border-surface-line px-1 text-fg-strong"
                >
                  expand
                </button>
              )}
              {!col.isDirectGroup && col.room.startsWith('dm-') && (
                <button
                  type="button"
                  data-fleet-wire-card-fold
                  onClick={() => { setDirectOpen(false); setCardRoom(null) }}
                  className="rounded border border-surface-line px-1 text-fg-strong"
                >
                  fold direct rooms
                </button>
              )}
              <span className="ml-auto truncate">leave: sac part {col.room}</span>
            </div>
          </div>
        )
      })()}
    </div>
  )
}
