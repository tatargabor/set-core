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
 * How many agents are BLOCKED in front of a person — the warning's number.
 *
 * `prompt` only: an open question (AskUserQuestion / ExitPlanMode, whose
 * runtime status is `waiting`) or a permission prompt. Until 2026-10-10 this
 * was `input + prompt`, which put every merely-finished turn under the
 * warning too — and, because the green below yields to the warning, made the
 * green unreachable for exactly the agents it was meant for (B-160).
 *
 * Parked waits are excluded by the counter itself: a question nobody has come
 * for in 45 minutes must not own the tab forever. `awaiting` is deliberately
 * NOT summed in: that counts work with nobody standing on it (task 7.14).
 */
export function needsPerson(t: Tally): number {
  return t.prompt
}

/**
 * How many agents FINISHED their turn and wait to be read — the green's number.
 *
 * `input`, which already includes a finished agent that left a background
 * command running (a dev server is not the agent working), and already
 * excludes parked waits. NOT `quiet`, which is a LOG state: measured on the
 * live screen, the `quiet` agents left once the input waiters are removed are
 * the ones whose loop is still RUNNING between two log flushes, so the old
 * green announced "finished" about working agents (B-160).
 */
export function readyToRead(t: Tally): number {
  return t.input
}

/**
 * How many agents are ASKING you a question — the red question mark's number.
 *
 * `askingNow`, the same count the project row's sky `Q` marker shows: an
 * AskUserQuestion or ExitPlanMode is open, measured from the session log, and
 * a question parked for 45 minutes is left out for the same reason a parked
 * wait is. Asked 2026-10-21: a red question mark in the tab when there is a
 * question — a question is the one block whose answer is a sentence only the
 * reader can write, so it gets its own mark rather than the generic warning.
 */
export function askingYou(t: Tally): number {
  return t.askingNow
}

/**
 * The title, with its tone — asked 2026-09-01, in the same breath as the badge:
 * a warning emoji while input is needed, a green circle when a process is
 * ready to be read.
 *
 * The warning wins over the green, and the ordering is the screen's own:
 * an agent BLOCKED on you is more urgent than a result being AVAILABLE, and a
 * title that must be read at a glance cannot show both at once. The green
 * carries its count too, so "three finished" and "one finished" read apart.
 *
 * The red question mark (2026-10-21) wins over both: a question is a block
 * too — its agent is counted in `prompt` as well — so it is the more specific
 * reading of the same fact. While no live question is open, `prompt` holds
 * only the other blocks (a permission prompt, a worker request), because
 * `askingNow` and `prompt` leave out exactly the same parked agents.
 */
export function tabTitle(base: string, count: number, ready = 0, asking = 0): string {
  if (asking > 0) return `❓ ${base} (${asking})`
  if (count > 0) return `⚠️ ${base} (${count})`
  if (ready > 0) return `🟢 ${base} (${ready})`
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
