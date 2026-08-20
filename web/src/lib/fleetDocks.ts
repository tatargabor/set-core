/**
 * Which view instances are docked to which edge, and how the remaining area is
 * computed from that.
 *
 * ## The geometry is here, not in the components
 *
 * A docked band and the area left over are the same subtraction seen from two
 * sides. Computing each where it is rendered means two expressions of one fact,
 * and they drift in the direction nobody notices: the band and the gap disagree
 * by a few pixels, or by a scrollbar, and the result still looks like a layout.
 *
 * ## The grid is told nothing
 *
 * `remainingArea` hands back a box. The agent grid lays out inside it and never
 * learns what took the rest, which is what keeps the column count meaning what
 * the user chose — three columns stays three columns in a narrower box. If the
 * grid knew about docking it would need a rule per edge, and every new view kind
 * would have to be taught to it.
 *
 * ## Size is a divider position, deliberately not stored here
 *
 * A docked view's size lives in `splits` under a key derived from its identity,
 * because a docked view's inner edge IS a divider. Two stores for one edge is
 * how a screen ends up rendering a width nobody set.
 */
import { SPLIT_PROJECTS, positionOf, type Splits } from './fleetSplits'

export const DOCK_EDGES = ['left', 'right', 'top', 'bottom'] as const
export type DockEdge = (typeof DOCK_EDGES)[number]

export interface DockedView {
  kind: string
  id: string
  edge: DockEdge
}

/** Whether a stored entry is usable. An unknown edge is not a smaller mistake. */
export function isDockedView(value: unknown): value is DockedView {
  if (!value || typeof value !== 'object') return false
  const v = value as Partial<DockedView>
  return typeof v.kind === 'string' && v.kind.length > 0
    && typeof v.id === 'string' && v.id.length > 0
    && typeof v.edge === 'string' && (DOCK_EDGES as readonly string[]).includes(v.edge)
}

/**
 * The divider key for one docked view.
 *
 * Derived from its identity rather than from its edge: a view dragged from the
 * right edge to the bottom keeps the size the user gave it, instead of picking
 * up whatever the last view on that edge happened to be. Keyed by edge, moving
 * a view would silently resize it — which reads as the screen deciding.
 */
export function dockSplitKey(view: Pick<DockedView, 'kind' | 'id'>): string {
  return `dock:${view.kind}:${view.id}`
}

/**
 * The default size of a docked band before anybody drags it — per AXIS, because
 * width and height are not the same question.
 *
 * Measured against a real screen on 2026-08-20: one number (320) gave a
 * left-docked agent panel a terminal squeezed to a horizontal scrollbar. A
 * terminal is a fixed-grid device that assumes 80 columns, which is roughly
 * 560px at this font — so 320 was not a smaller terminal, it was a broken one.
 *
 * The fix is NOT to make the terminal narrower. This is the nesting case the
 * evidence rules already record: a sentence at top level gets the page's width,
 * the same sentence inside a band gets whatever the band left. The width is
 * decided here, so here is where it is fixed.
 *
 * A 560px-tall bottom band, on the other hand, would be absurd — it would take
 * most of the screen's height for a strip. Hence two numbers.
 */
export const DEFAULT_DOCK_WIDTH = 560
export const DEFAULT_DOCK_HEIGHT = 280

/** The default for one edge. */
export function defaultDockSize(edge: DockEdge): number {
  return edge === 'left' || edge === 'right' ? DEFAULT_DOCK_WIDTH : DEFAULT_DOCK_HEIGHT
}

/** A box in CSS pixels. Only the two dimensions the layout actually divides. */
export interface Area {
  width: number
  height: number
}

export interface DockedBand extends DockedView {
  /** Size along the axis the band divides: width for left/right, height otherwise. */
  size: number
}

/** Bands in render order, each carrying the size the store holds for it. */
export function dockedBands(
  docks: readonly unknown[] | null | undefined,
  splits: Splits | null | undefined,
): DockedBand[] {
  const out: DockedBand[] = []
  for (const entry of docks ?? []) {
    if (!isDockedView(entry)) continue
    out.push({ ...entry, size: positionOf(splits, dockSplitKey(entry), defaultDockSize(entry.edge)) })
  }
  return out
}

/**
 * What is left for the agent grid after the project list and every docked band.
 *
 * **Never returns a negative or zero box.** A box of zero is not a smaller box —
 * it is a grid that renders nothing, and a reader looking at an empty panel has
 * no way to tell it from "no agents". So the remainder is floored, and the
 * overflow is reported so a caller can say the screen is too full rather than
 * pretending it is not.
 */
export function remainingArea(
  shell: Area,
  bands: readonly DockedBand[],
  splits: Splits | null | undefined,
  opts: { projectColumn?: boolean; minWidth?: number; minHeight?: number } = {},
): Area & { overflowed: boolean } {
  const minWidth = opts.minWidth ?? 360
  const minHeight = opts.minHeight ?? 200
  let width = shell.width
  let height = shell.height
  if (opts.projectColumn !== false) width -= positionOf(splits, SPLIT_PROJECTS, 288)
  for (const band of bands) {
    if (band.edge === 'left' || band.edge === 'right') width -= band.size
    else height -= band.size
  }
  const overflowed = width < minWidth || height < minHeight
  return { width: Math.max(minWidth, width), height: Math.max(minHeight, height), overflowed }
}

/** The bands on one edge, in stored order. */
export function bandsOn(bands: readonly DockedBand[], edge: DockEdge): DockedBand[] {
  return bands.filter(b => b.edge === edge)
}

/**
 * Dock a view to an edge, or undock it when `edge` is null.
 *
 * Returns a new list; the caller persists it. Moving an already-docked view
 * keeps its position in the list rather than sending it to the end — a view
 * jumping to the bottom of its edge because it was moved to that edge would be
 * the screen rearranging something the user did not.
 */
export function withDock(
  docks: readonly DockedView[],
  view: Pick<DockedView, 'kind' | 'id'>,
  edge: DockEdge | null,
): DockedView[] {
  const at = docks.findIndex(d => d.kind === view.kind && d.id === view.id)
  if (edge === null) return docks.filter((_, i) => i !== at)
  if (at === -1) return [...docks, { kind: view.kind, id: view.id, edge }]
  return docks.map((d, i) => (i === at ? { ...d, edge } : d))
}

/**
 * Read the stored docking. A failure is "nothing docked", never an error state —
 * the same rule as the divider positions: a screen that will not render because
 * a preference could not be read is a worse outcome than one at its defaults.
 */
export async function loadDocks(fetchImpl: typeof fetch = fetch): Promise<DockedView[]> {
  try {
    const res = await fetchImpl('/api/fleet/layout')
    if (!res.ok) return []
    const body = await res.json()
    const raw = body?.docks
    return Array.isArray(raw) ? raw.filter(isDockedView) : []
  } catch {
    return []
  }
}

/** Write the docking. Says whether it landed; never throws at the caller. */
export async function saveDocks(
  docks: readonly DockedView[], fetchImpl: typeof fetch = fetch,
): Promise<boolean> {
  try {
    const res = await fetchImpl('/api/fleet/layout/docks', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ docks }),
    })
    return res.ok
  } catch {
    return false
  }
}
