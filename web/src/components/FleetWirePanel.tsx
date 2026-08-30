import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import {
  computeRoomMatrix, cellTitle, HEADER_Y,
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
    const probe = computeRoomMatrix({ payload, rows, height: box.height, gutterWidth: WIRE_GUTTER_MAX })
    const width = probe.columns.length > 8 ? WIRE_GUTTER_MAX : WIRE_GUTTER_WIDTH
    setLayout({ ...probe, width })
  }, [payload])

  useLayoutEffect(measure, [measure])

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
          <LegendRow swatch={<circle cx="5" cy="5" r="4" className="fleet-wire-cell-sender" />}>
            filled — wrote LAST in this room
          </LegendRow>
          <LegendRow swatch={<circle cx="5" cy="5" r="4" className="fleet-wire-cell-sender fleet-wire-cell-live" />}>
            pulsing — that write is &lt;30 min old
          </LegendRow>
          <LegendRow swatch={<circle cx="5" cy="5" r="3.5" className="fleet-wire-cell-member-active" />}>
            thick ring — in the room, room is fresh
          </LegendRow>
          <LegendRow swatch={<circle cx="5" cy="5" r="3.5" className="fleet-wire-cell-member-idle" />}>
            thin dim ring — in the room, idle
          </LegendRow>
          <LegendRow swatch={<span className="inline-block h-2 w-2" />}>
            blank — not a member of that room
          </LegendRow>
          <LegendRow swatch={<rect x="1" y="1" width="2" height="8" className="fleet-wire-terminal" />}>
            tick — enrolled agent · socket — not enrolled
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
                and brightens when the room's newest write is fresh. */}
            {layout.columns.map(col => (
              <g key={`col-${col.room}`} className="pointer-events-auto">
                <title>{cellTitle(col.room, col.memberSeats, col.lastActivity, Date.now())}</title>
                <line
                  data-fleet-wire-column={col.room}
                  x1={col.x} y1={34} x2={col.x} y2="100%"
                  className={col.recent ? 'fleet-wire-col fleet-wire-col-active' : 'fleet-wire-col fleet-wire-col-idle'}
                />
                <text
                  data-fleet-wire-label={col.room}
                  x={col.x + 3}
                  y={HEADER_Y}
                  transform={`rotate(90 ${col.x + 3} ${HEADER_Y})`}
                  className={col.recent ? 'fleet-wire-label fleet-wire-label-active' : 'fleet-wire-label fleet-wire-label-idle'}
                >
                  {col.room.length > 14 ? `${col.room.slice(0, 13)}…` : col.room}
                </text>
              </g>
            ))}
            {/* Membership cells. The room's SENDER renders filled (animated
                while fresh) — in a grid, who-sent is WHICH CELL IS FILLED. */}
            {layout.cells.map(cell => (
              <g key={cell.key} className="pointer-events-auto">
                <title>{cellTitle(cell.room, layout.columns.find(c => c.room === cell.room)?.memberSeats ?? [], layout.columns.find(c => c.room === cell.room)?.lastActivity ?? null, Date.now())}</title>
                {cell.role === 'sender' ? (
                  <circle
                    data-fleet-wire-cell={cell.room}
                    data-fleet-wire-role="sender"
                    data-fleet-wire-active={cell.active ? 'true' : undefined}
                    cx={cell.x} cy={cell.y} r={4}
                    className={cell.active
                      ? 'fleet-wire-cell fleet-wire-cell-sender fleet-wire-cell-live'
                      : 'fleet-wire-cell fleet-wire-cell-sender'}
                  />
                ) : (
                  <circle
                    data-fleet-wire-cell={cell.room}
                    data-fleet-wire-role="member"
                    data-fleet-wire-active={cell.active ? 'true' : undefined}
                    cx={cell.x} cy={cell.y} r={3.5}
                    className={cell.active
                      ? 'fleet-wire-cell fleet-wire-cell-member-active'
                      : 'fleet-wire-cell fleet-wire-cell-member-idle'}
                  />
                )}
              </g>
            ))}
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
                x={0} y={s.y - 3.5} width={6} height={7}
                className="fleet-wire-socket"
              >
                <title>{s.projectSeatCount
                  ? 'seats exist for this project, but none carries THIS session (session drift) — re-enrol: sac install'
                  : 'not enrolled on the channel bus — run `sac install` in that project to enrol it'}</title>
              </rect>
            ))}
          </svg>
        )
      )}
    </div>
  )
}
