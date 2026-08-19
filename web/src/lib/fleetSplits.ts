/**
 * Where the draggable dividers sit — read once, written on release.
 *
 * ## Why this is server state and not `localStorage`
 *
 * The same reason the arrangement is (`fleetLayout.ts`): it is a position the
 * user sets by hand and then relies on, and it should not differ between two
 * browsers on the same machine. It rides in the same document, under `splits`.
 *
 * ## Why it has its OWN write route
 *
 * `PUT /api/fleet/layout` is guarded by `base_version`, which protects a
 * hand-made arrangement from two open tabs. A divider is not part of that
 * arrangement, and routing it through the same PUT would force a choice between
 * two defects: bump the version, and the user's next group edit conflicts with
 * their own dragging; or skip the guard, and an unguarded write now lives on the
 * route that exists to guard. `PUT /api/fleet/layout/splits` writes the
 * positions alone and leaves the version where it was.
 *
 * ## An absent key is "never dragged", NOT zero
 *
 * A missing entry means the caller uses its own default width. Storing a zero
 * would render a pane as no pane at all — the false-absence class, in the
 * direction where the reader cannot even see the edge they would need to drag
 * back. So `positionOf` takes the default as an argument and returns it for
 * anything that is not a usable number.
 */

/** Divider keys. One per draggable edge; the value is that pane's size in px. */
export const SPLIT_PROJECTS = 'projects'

/**
 * What the client will accept from the store, before the viewport is consulted.
 *
 * The server clamps to what is RECOVERABLE (an edge that can be grabbed again);
 * this clamps to what is USABLE. They are deliberately different questions, and
 * neither one alone is enough: the server cannot see the window, and the client
 * cannot stop a hand-edited file from arriving.
 */
export const MIN_PANE = 180
export const MAX_PANE = 900

export type Splits = Record<string, number>

/** The stored size of one divider's pane, or `fallback` when it has none. */
export function positionOf(splits: Splits | null | undefined, key: string, fallback: number): number {
  const raw = splits?.[key]
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return fallback
  return clampPane(raw)
}

/** Keep a pane inside what the surface can actually render and grab back. */
export function clampPane(px: number, max: number = MAX_PANE): number {
  if (!Number.isFinite(px)) return MIN_PANE
  return Math.max(MIN_PANE, Math.min(max, Math.round(px)))
}

/** Read the stored positions. A failure is "no positions", never an error state:
 *  a screen that will not render because a preference could not be read is a
 *  worse outcome than one rendering at its defaults. */
export async function loadSplits(fetchImpl: typeof fetch = fetch): Promise<Splits> {
  try {
    const res = await fetchImpl('/api/fleet/layout')
    if (!res.ok) return {}
    const body = await res.json()
    const raw = body?.splits
    if (!raw || typeof raw !== 'object') return {}
    const out: Splits = {}
    for (const [k, v] of Object.entries(raw)) if (typeof v === 'number' && Number.isFinite(v)) out[k] = v
    return out
  } catch {
    return {}
  }
}

/** Write the positions. Resolves to whether the store took them, so a caller
 *  can say so; it never throws, for the same reason as above. */
export async function saveSplits(splits: Splits, fetchImpl: typeof fetch = fetch): Promise<boolean> {
  try {
    const res = await fetchImpl('/api/fleet/layout/splits', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ splits }),
    })
    return res.ok
  } catch {
    return false
  }
}
