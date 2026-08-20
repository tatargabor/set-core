import type { ReactNode } from 'react'
import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, X } from 'lucide-react'
import FleetSplitter from './FleetSplitter'
import { type DockedBand } from '../lib/fleetDocks'
import { MIN_PANE } from '../lib/fleetSplits'
import { IconButton } from './TileControls'

/**
 * One docked view: a band along an edge, with a draggable inner edge.
 *
 * ## Why the divider is the SAME component
 *
 * `FleetSplitter`, with `grows: 'after'` on the right and bottom edges. A
 * second implementation here would be the natural thing to write — the geometry
 * is simple — and it is where the keyboard support, the pointer capture and the
 * bounds get left out. Those are the parts nobody notices missing until somebody
 * cannot use the screen at all.
 *
 * ## A collapsed band must still report a failure
 *
 * `ui-quality.md`'s rule, and this is the new hiding place it warns about:
 * *compacting must never hide a failure*. Collapsing is a layout that removes
 * things from view, so anything wrong inside has to be marked on the edge where
 * the reader is standing. Without it a collapsed band reads as calm — and a tidy
 * screen reporting calm it has not verified is worse than a cluttered one,
 * because it is more convincing.
 *
 * The distinction the marker draws is three-way, not two:
 *
 *  - `failing > 0`   — something in here is wrong. Said loudly.
 *  - `failing === 0` — checked, and nothing is wrong.
 *  - `failing == null` — the view could NOT determine what it holds. This is not
 *    the same as zero, and rendering it as zero would be the false-absence class:
 *    a claim of calm that was never measured.
 */
export interface FleetDockBandProps {
  band: DockedBand
  /** Rendered inside the band when it is not collapsed. */
  children?: ReactNode
  collapsed?: boolean
  onToggleCollapsed?: () => void
  /** Undock this view, returning its space to the grid. */
  onUndock?: () => void
  onResize: (px: number) => void
  onResizeCommit: (px: number) => void
  /** The largest this band may become, measured against the shell by the caller. */
  max: number
  /**
   * How many items inside this band are in a failed or blocked state, or `null`
   * when the view could not determine it. `null` is NOT zero.
   */
  failing?: number | null
  /** Human name of the view, for the collapsed strip and the controls. */
  title: string
  /**
   * Whether the band's own header repeats the name.
   *
   * `false` when the content already carries it — an agent card puts its own
   * label at the top, and the band header printed it again directly above,
   * which looked exactly like a defect: the same string twice, in two weights,
   * one line apart. It is the second-copy problem in its most visible form, and
   * only looking at the screen shows it.
   *
   * The name is still on the band element as a tooltip, so nothing is lost for
   * a reader who needs it.
   */
  showTitle?: boolean
}

/**
 * How thick a collapsed band is — enough for the marker, the vertical name and
 * the reopen control.
 *
 * Widened from 28 after looking at it: at 28 a collapsed side band was a bare
 * arrow at the screen edge with nothing saying what had been tidied away.
 */
export const COLLAPSED_SIZE = 34

export default function FleetDockBand({
  band, children, collapsed = false, onToggleCollapsed, onUndock,
  onResize, onResizeCommit, max, failing, title, showTitle = true,
}: FleetDockBandProps) {
  const vertical = band.edge === 'left' || band.edge === 'right'
  // The band sits BEFORE the remaining area on the left and top edges, and
  // after it on the right and bottom. The divider therefore grows the band in
  // opposite directions on opposite edges — which is exactly the `grows` prop,
  // and exactly why it exists rather than being hard-coded to one side.
  const grows = band.edge === 'left' || band.edge === 'top' ? 'before' : 'after'
  const size = collapsed ? COLLAPSED_SIZE : band.size

  const marker = (
    <span
      data-fleet-dock-marker={band.id}
      data-fleet-dock-failing={failing === null || failing === undefined ? 'unknown' : String(failing)}
      className={`text-xs tabular-nums font-semibold ${
        failing === null || failing === undefined
          ? 'text-amber-400'
          : failing > 0 ? 'text-rose-400' : 'text-fg-ghost'
      }`}
      title={
        failing === null || failing === undefined
          ? `${title}: this view could not determine the state of what it holds`
          : failing > 0
            ? `${title}: ${failing} item(s) in a failed or blocked state`
            : `${title}: nothing failing`
      }
    >
      {failing === null || failing === undefined ? '?' : failing > 0 ? `${failing} ✕` : ''}
    </span>
  )

  const Collapse = collapsed
    ? (band.edge === 'left' ? ChevronRight : band.edge === 'right' ? ChevronLeft
      : band.edge === 'top' ? ChevronDown : ChevronUp)
    : (band.edge === 'left' ? ChevronLeft : band.edge === 'right' ? ChevronRight
      : band.edge === 'top' ? ChevronUp : ChevronDown)

  const bandEl = (
    <div
      data-fleet-dock={band.id}
      data-fleet-dock-edge={band.edge}
      data-fleet-dock-collapsed={collapsed ? 'true' : undefined}
      title={title}
      className={`shrink-0 min-w-0 min-h-0 flex ${vertical ? 'flex-col' : 'flex-col'} bg-surface-panel overflow-hidden`}
      style={vertical ? { width: `${size}px` } : { height: `${size}px` }}
    >
      <div className={`shrink-0 flex gap-1.5 border-surface-line min-w-0 ${
        collapsed && vertical
          ? 'flex-col items-center py-1.5 px-0.5 flex-1 min-h-0'
          : 'items-center px-1.5 py-0.5 border-b'
      }`}>
        {/* The marker comes FIRST, before the title, and is rendered whether or
            not the band is collapsed. A marker that only appears when expanded
            would be visible exactly when it is not needed. */}
        {marker}
        {/* Collapsed, the name is the ONLY thing identifying this band, so it is
            shown whatever `showTitle` says — that flag is about not repeating a
            name the open content already prints. On a side edge there is no
            horizontal room, so it is set vertically, which is what a collapsed
            side panel does everywhere. Without this a tidied band is a bare
            arrow at the screen edge: it does not hide a FAILURE (the marker
            still renders), but it hides what is there, and a reader cannot
            choose to reopen something they cannot name. */}
        {collapsed
          ? (
            <span
              className="text-xs text-fg-strong truncate min-w-0"
              style={vertical
                ? { writingMode: 'vertical-rl', transform: 'rotate(180deg)', maxHeight: '14rem' }
                : undefined}
            >
              {title}
            </span>
          )
          : showTitle && <span className="text-xs text-fg-strong truncate min-w-0">{title}</span>}
        <span className={`flex gap-0.5 shrink-0 ${
          collapsed && vertical ? 'flex-col mt-auto' : 'ml-auto items-center'
        }`}>
          {onToggleCollapsed && (
            <IconButton
              icon={Collapse}
              label={collapsed ? `expand ${title}` : `collapse ${title}`}
              onClick={onToggleCollapsed}
            />
          )}
          {onUndock && <IconButton icon={X} label={`undock ${title}`} onClick={onUndock} />}
        </span>
      </div>
      {/* `[&>*]:flex-1` — the content FILLS the band. Without it the child sizes
          itself from its own text and the rest of the band is black space, which
          reads as a panel that failed to load rather than as a short card.
          Measured by looking at it on 2026-08-20. */}
      {!collapsed && (
        <div className="flex-1 min-h-0 min-w-0 overflow-auto flex flex-col [&>*]:flex-1 [&>*]:min-h-0">
          {children}
        </div>
      )}
    </div>
  )

  // No divider while collapsed: dragging a strip that shows nothing would set a
  // size the reader cannot see the effect of, and the size it would overwrite is
  // the one they chose before collapsing.
  const divider = collapsed ? null : (
    <FleetSplitter
      axis={vertical ? 'x' : 'y'}
      grows={grows}
      label={`${title} size`}
      size={band.size}
      min={MIN_PANE}
      max={max}
      onDrag={onResize}
      onCommit={onResizeCommit}
    />
  )

  return (
    <>
      {band.edge === 'left' || band.edge === 'top' ? bandEl : divider}
      {band.edge === 'left' || band.edge === 'top' ? divider : bandEl}
    </>
  )
}
