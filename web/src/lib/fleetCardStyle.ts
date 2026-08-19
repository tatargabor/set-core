/**
 * What an agent tile looks like, and why — the decision kept out of the JSX so
 * it can be asserted rather than eyeballed.
 *
 * Three requests from 2026-08-19 land on the same element, and they have to be
 * resolved together or they fight each other:
 *
 *  1. *"nagyon összefolynak az agent kockák"* — the tiles have no visible edge.
 *     Measured cause, and it is the SECOND time this exact defect appears:
 *     `--color-surface-line` and `--color-surface-raised` are both
 *     `neutral-800`, so a border painted with `surface-line` cannot be seen
 *     against a raised surface and is barely visible against the page. Task
 *     7.17 fixed it for the project column with `surface-edge` (neutral-700);
 *     the agent tiles were never given the same treatment.
 *  2. *"nem saját agenteket jelölni kell vizuálisan más színnel … nem tudjuk
 *     utasítani set-ből, keretből"* — ownership is the most consequential
 *     thing about a tile and it was carried by one dim line of text.
 *  3. *"az aktuális csempe, amin gépelek, lehetne aktívan jelezve"*.
 *
 * ## The rule that decides the palette
 *
 * `ui-quality.md`: **one visual weight per meaning.** This screen already
 * spends red on *broken*, amber on *undetermined* and sky on *waiting for a
 * person*. Ownership may not take any of those, or a foreign agent would read
 * as a problem — it is not one, it is the ordinary case.
 *
 * So ownership is carried by the EDGE's shape, not by a new colour:
 *
 *  - **ours** — solid edge, slightly raised fill. The framework holds it, so a
 *    terminal can be attached and it can be told what to do.
 *  - **foreign** — dashed edge, no fill. Nothing here holds it; the dashes say
 *    "not attached" without claiming anything is wrong.
 *  - **unknown** — dashed edge in amber, which is this screen's existing colour
 *    for *we could not find out*. It is NOT a shade of foreign: while the owner
 *    service is restarting every agent arrives unknown, and rendering that as
 *    foreign states "the framework does not hold it" about agents it does.
 *
 * Typing is the one thing that gets a colour, because it answers *where am I* —
 * a sky ring, matching the focus meaning it already carries, and it is measured
 * from real DOM focus rather than from which pane was opened last.
 */

import { terminalOffer } from './fleetTerminal'
import type { FleetAgent } from './fleetTypes'

/**
 * Who holds this agent. Read from the producer's `population`, never guessed.
 *
 * `orphaned` is a fourth value rather than a shade of the others (task 5.5):
 * the framework STARTED it and no longer holds its terminal. Calling it foreign
 * would deny that we started it; calling it unknown would deny that we measured
 * it. The scope it still runs in is what a recovery would stop.
 */
export type Ownership = 'ours' | 'orphaned' | 'foreign' | 'unknown'

/**
 * Ownership from the same source the terminal offer uses.
 *
 * Deliberately delegating rather than re-reading `population`: two functions
 * deciding the same thing from the same field is the second-place defect, and
 * the copy that drifts is always the one nobody is looking at. If a terminal
 * can be attached, the framework holds it — that IS the ownership question.
 */
export function ownershipOf(agent: Partial<FleetAgent>, ownerReachable?: boolean): Ownership {
  const kind = terminalOffer(agent, ownerReachable).kind
  if (kind === 'available') return 'ours'
  if (kind === 'orphaned') return 'orphaned'
  if (kind === 'foreign') return 'foreign'
  return 'unknown'
}

export interface CardState {
  /** The tile is the enlarged one (task 7.4) — width, not meaning. */
  enlarged?: boolean
  /** The tile is alone on the panel (full screen). */
  focused?: boolean
  /** The reader's keyboard is in THIS tile's terminal, measured from DOM focus. */
  typing?: boolean
}

/** One short label for the ownership, for a title attribute or a marker. */
export const OWNERSHIP_NOTE: Record<Ownership, string> = {
  ours: 'the framework started this agent and holds it — it has a terminal and can be told what to do',
  orphaned: 'the framework started this agent and lost its terminal — the scope survived, the pty did not',
  foreign: 'started outside the framework — nothing here holds it, so it cannot be driven from set',
  unknown: 'the owner service could not be asked — we do not know who holds this one',
}

/**
 * The tile's classes.
 *
 * Every tile gets the SAME padding and the same edge width, so the grid reads
 * as one set of things; what varies is the edge's style and the fill. The
 * request also named the sizes — *"az sem segít hogy különböző méretűek"* — and
 * that is settled at the grid rather than here, because a tile cannot know how
 * tall its neighbour is: `Fleet.tsx` gives the rows
 * `auto-rows-[minmax(11rem,1fr)]`, so every tile has the same height and a floor.
 *
 * ⚠ This paragraph used to say the grid did it with "`items-start` plus a
 * minimum height". `items-start` was real; **the minimum height did not exist**
 * — zero hits for `min-h` outside `min-h-0`. A comment claiming a guard the code
 * does not have is worse than no comment: the next reader stops looking. Both
 * halves are true as of 2026-08-19, and the grep that checks them is
 * `grep -n 'auto-rows' src/pages/Fleet.tsx`.
 */
export function cardClasses(ownership: Ownership, state: CardState = {}): string {
  const edge =
    ownership === 'ours' ? 'border-surface-edge'
      // Ours, damaged. A solid edge because we started it and it is still
      // running; amber because something about it needs attention — which is
      // the same meaning amber carries everywhere else on this screen.
      : ownership === 'orphaned' ? 'border-amber-400/50'
        : ownership === 'unknown' ? 'border-amber-400/40 border-dashed'
          : 'border-surface-edge-soft/40 border-dashed'
  const fill = ownership === 'ours' || ownership === 'orphaned' ? 'bg-surface-raised/40' : 'bg-transparent'
  const ring = state.typing ? 'ring-2 ring-sky-400/70' : ''
  const size = state.focused ? 'p-4' : 'px-3 py-2'
  return ['border rounded', edge, fill, ring, size].filter(Boolean).join(' ')
}
