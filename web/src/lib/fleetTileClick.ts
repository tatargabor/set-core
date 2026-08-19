/**
 * Clicking the tile itself opens the agent — asked for 2026-08-19:
 * *"ha kattintok egy területen ami az adott agenthez tartozik de nem gomb,
 * akkor az agentre kellene fokuszálnia és kinyílnia az ablaknak"*.
 *
 * The tile is a window, so its body is a way in and not only a display. What
 * makes this worth a file rather than an inline `onClick` is that **a
 * click-anywhere handler swallows acts the reader meant differently**, and each
 * one fails silently:
 *
 *  - **a control already means something.** A click on the log button bubbles to
 *    the tile, so the tile would re-layout underneath the act the reader asked
 *    for. The handler must stop at the first element that already has a meaning;
 *  - **a surface inside the tile is not the tile.** The log, the terminal and the
 *    instruction box are their own things — clicking into a terminal is how you
 *    put the keyboard in it, and re-laying out the screen at that moment moves
 *    the box out from under the hands that are already typing;
 *  - **selecting text ends in a click.** Dragging across an excerpt to copy it
 *    fires `click` on mouseup like any other. Enlarging there destroys the
 *    selection that was the whole point, and it does so *only* for readers who
 *    reached for the text — which is why nobody hits it while testing.
 *
 * The direction chosen for all three is the same: **when in doubt, do nothing.**
 * A click that fails to open costs one more click on a control that is visible
 * two centimetres away; a click that opens when it should not takes the reader's
 * layout, their selection, or their keystroke, and gives no way to tell why.
 */

/**
 * Elements whose own click already means something.
 *
 * `label` is in the list because clicking one moves focus into its control —
 * the click belongs to the control even though it landed on text.
 */
const INTERACTIVE =
  'a,button,input,textarea,select,label,summary,[role="button"],[role="link"],[role="tab"],[contenteditable="true"]'

/**
 * A surface that lives inside the tile but is not part of it.
 *
 * Marked at the surface rather than listed here, so a new panel inside a tile
 * declares itself instead of being remembered about in a second place.
 */
const OWN_SURFACE = '[data-fleet-own-surface]'

export interface TileClick {
  /** Where the click landed. */
  target: Element | null
  /** The tile, which bounds the search — an ancestor outside it is not ours. */
  card: Element
  /** What is selected right now, if anything. */
  selection?: string | null
}

/**
 * Whether this click is a request to open the agent.
 *
 * Returns false for everything that already has a meaning, and for a click that
 * ends a text selection.
 */
export function tileClickOpens({ target, card, selection }: TileClick): boolean {
  if (!target || !card.contains(target)) return false
  // A drag that ends inside the tile arrives as a click. Trimmed, because a
  // double-click leaves a single space selected in some browsers and that is
  // not a selection anybody made on purpose.
  if (selection && selection.trim().length > 0) return false
  // `closest` walks past the tile as well, so both hits are checked for being
  // INSIDE it — a tile nested in some future clickable container must not read
  // that container's meaning as its own.
  const interactive = target.closest(INTERACTIVE)
  if (interactive && card.contains(interactive)) return false
  const surface = target.closest(OWN_SURFACE)
  if (surface && card.contains(surface)) return false
  return true
}

/**
 * What the browser has selected, as a string.
 *
 * Split out so the decision above stays pure and testable: jsdom's selection
 * support is thin, and a test that had to fake a Selection object would be
 * measuring the fake.
 */
export function currentSelection(): string {
  if (typeof window === 'undefined' || !window.getSelection) return ''
  return window.getSelection()?.toString() ?? ''
}
