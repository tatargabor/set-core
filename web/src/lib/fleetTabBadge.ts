/**
 * The browser tab badge — `SET (2)` while an agent is standing in front of a
 * person.
 *
 * Asked for 2026-09-01: *"a browser tab number when an agent requires my
 * input"* — the reader works in other tabs, and the fleet screen's own header
 * cannot reach them there. The document title can.
 *
 * ## Deliberately per-viewer, and therefore localStorage
 *
 * The ask was explicitly personal: *"just for me, not sure other colleagues
 * would want it"*. A server-side setting would decide for everyone who opens
 * the dashboard; the browser's own storage decides per browser, which is the
 * granularity the request actually names. The preference travels with neither
 * the arrangement nor the account — it is a property of THIS reader's browser,
 * and it defaults ON with one click to turn it off, because the person who
 * asked for it should not have to find a setting first.
 *
 * Every storage read is guarded: a private window or a blocked-site-data
 * setting makes localStorage throw, and a badge preference must never be the
 * thing that takes the fleet screen down.
 */

import type { Tally } from './fleetAttention'

export const TAB_BADGE_KEY = 'set.fleet.tab-badge'

/**
 * How many agents need a person right now — the number the tab shows.
 *
 * `input + prompt`, and that sum is deliberate rather than missing a class:
 * `tally` counts a `background` waiter BOTH ways — in `background` as its own
 * fact and inside `input` as a waiter — so summing all three would double
 * every background agent in the tab. Parked waits are already excluded by the
 * same counters: a question nobody has come for in 45 minutes must not own
 * the tab badge forever, for the same reason it must not own the row colour.
 * `awaiting` is deliberately NOT summed in: that counts work with nobody
 * standing on it (task 7.14), a different fact, and tab real estate is the
 * scarcest attention there is.
 */
export function needsPerson(t: Tally): number {
  return t.input + t.prompt
}

/**
 * The title, with its tone — asked 2026-09-01, in the same breath as the badge:
 * a warning emoji while input is needed, a green circle when a process is
 * ready to be read.
 *
 * The warning wins over the green, and the ordering is the screen's own:
 * a person being NEEDED is more urgent than a result being AVAILABLE, and a
 * title that must be read at a glance cannot show both at once. Ready counts
 * `quiet` agents — a turn that ended with nothing outstanding — so green means
 * "something finished, come read it", and it yields the moment anybody needs
 * you again.
 */
export function tabTitle(base: string, count: number, ready = 0): string {
  if (count > 0) return `⚠️ ${base} (${count})`
  if (ready > 0) return `🟢 ${base}`
  return base
}

/** ON unless this browser said otherwise — the asker should not hunt for a setting. */
export function loadTabBadge(storage?: Storage | null): boolean {
  try {
    const s = storage ?? globalThis.localStorage
    return s?.getItem(TAB_BADGE_KEY) !== 'off'
  } catch {
    return true
  }
}

export function saveTabBadge(on: boolean, storage?: Storage | null): void {
  try {
    ;(storage ?? globalThis.localStorage)?.setItem(TAB_BADGE_KEY, on ? 'on' : 'off')
  } catch {
    /* storage unavailable — the toggle still works for this session */
  }
}
