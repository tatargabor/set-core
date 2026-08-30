import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

import {
  computeWireLayout, labelFor, segmentTitle,
  type ChannelsPayload, type WireLayout,
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

/** Belt re-measure interval. The poll redraws anyway; this catches layout
    shifts between polls (collapse, drag, font settle) at low cost. */
const MEASURE_BELT_MS = 2000

export default function FleetWirePanel({ payload }: { payload: ChannelsPayload | null }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [layout, setLayout] = useState<WireLayout | null>(null)

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
    setLayout(computeWireLayout({
      payload,
      rows,
      height: box.height,
      gutterWidth: WIRE_GUTTER_WIDTH,
    }))
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

  return (
    <div
      ref={containerRef}
      data-fleet-wire-gutter
      className="relative h-full shrink-0 border-l border-surface-line bg-surface-panel/30"
      style={{ width: WIRE_GUTTER_WIDTH }}
    >
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
            {layout.segments.map(seg => (
              <g key={seg.key} className="pointer-events-auto">
                {/* A fat transparent stroke under the visible one: the hover
                    target is the WIRE, not the one-pixel line a mouse must
                    find. The <title> carries identity and recency only. */}
                <path d={seg.path} stroke="transparent" strokeWidth={10} fill="none" />
                <title>{segmentTitle(seg, Date.now())}</title>
                <path
                  data-fleet-wire-segment={seg.room}
                  data-fleet-wire-flow={seg.flow}
                  data-fleet-wire-active={seg.active ? 'true' : undefined}
                  d={seg.path}
                  fill="none"
                  strokeWidth={seg.flow === 'sender' ? 2 : 1.5}
                  className={seg.active
                    ? (seg.flow === 'sender'
                      ? 'fleet-wire-seg fleet-wire-seg-active fleet-wire-seg-sender'
                      : 'fleet-wire-seg fleet-wire-seg-active')
                    : 'fleet-wire-seg fleet-wire-seg-idle'}
                />
              </g>
            ))}
            {layout.junctions.map(j => (
              <g key={j.key} className="pointer-events-auto">
                <title>{segmentTitle({
                  key: j.key, path: '', flow: 'sender', active: false, kind: 'fan',
                  room: j.room,
                  memberSeats: layout.segments
                    .filter(s => s.room === j.room).flatMap(s => s.memberSeats)
                    .filter((s, i, a) => a.indexOf(s) === i),
                  lastActivity: layout.segments.find(s => s.room === j.room)?.lastActivity ?? null,
                  label: { x: j.x, y: j.y - 10 },
                }, Date.now())}</title>
                <circle
                  data-fleet-wire-junction={j.room}
                  cx={j.x} cy={j.y} r={4}
                  className="fleet-wire-junction"
                />
              </g>
            ))}
            {/* One name per channel, at the wire's own midpoint / above the
                junction. Rendered from the segments deduped by room — a fan's
                segments all carry the same label. This is the channel's
                IDENTITY standing where the reader stands, not a hover extra:
                the user's own words after the first live view, seeing one bare
                wire and not knowing it was the wpc-board room. */}
            {[...new Map(layout.segments.map(s => [s.room, s])).values()].map(s => (
              <g key={`label-${s.room}`} className="pointer-events-auto">
                {/* The <title> lives on the wrapping <g>, NOT inside <text>:
                    inside it, the hover text joins the text node and would
                    render twice on some engines. */}
                <title>{segmentTitle(s, Date.now())}</title>
                <text
                  data-fleet-wire-label={s.room}
                  x={s.label.x}
                  y={s.label.y}
                  textAnchor="end"
                  className={s.active ? 'fleet-wire-label fleet-wire-label-active' : 'fleet-wire-label fleet-wire-label-idle'}
                >
                  {labelFor(s.room)}
                </text>
              </g>
            ))}
            {layout.terminals.map(t => (
              <circle
                key={t.pid}
                data-fleet-wire-terminal={t.pid}
                cx={4} cy={t.y} r={3.5}
                className="fleet-wire-terminal"
              >
                <title>{t.seat ?? `agent ${t.pid}`}</title>
              </circle>
            ))}
            {layout.sockets.map(s => (
              <rect
                key={s.pid}
                data-fleet-wire-socket={s.pid}
                x={1} y={s.y - 3.5} width={7} height={7}
                className="fleet-wire-socket"
              >
                <title>not enrolled on the channel bus — run `sac install` in that project to enrol it</title>
              </rect>
            ))}
          </svg>
        )
      )}
    </div>
  )
}
