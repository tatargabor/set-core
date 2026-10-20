/**
 * Latest mode — which agents the fleet shows, and where each one sits.
 *
 * Asked for 2026-10-19 (dictated): *"ne kelljen a projektenken kattintgatnom,
 * hogy az adott agentet megtaláljam"* — the agents a person most recently wrote
 * into, across every project, on one screen.
 *
 * Pure functions over the agent list and the count, so the two rules that make
 * the mode usable can be tested without a screen (design D3 of
 * `fleet-latest-mode`):
 *
 *  - **the selection** is by `last_human_input_seconds`, smallest first, and an
 *    agent with no measured value comes after every measured one — absent means
 *    *no message from you found*, never *a long time ago*;
 *  - **the placement is stable**: sorting happens when the mode is turned on and
 *    when the reader asks for it, never because a poll arrived. Typing into
 *    tile 3 makes it the most recent agent, and a grid that re-sorted on that
 *    would move the tile under the reader's hand — the reflow `ui-quality.md`
 *    forbids.
 */

import type { FleetAgent, FleetProject } from './fleetTypes'

/**
 * The view-memory key the mode's own layout is stored under.
 *
 * It contains a `/`, which no directory name can, and project names come from
 * directory names — so no project can ever read or overwrite this memory. The
 * design sketch said `__latest__`; that IS a legal directory name, so it was
 * not used.
 */
export const LATEST_VIEW_KEY = 'latest/'

export const DEFAULT_LATEST_COUNT = 10
export const MIN_LATEST_COUNT = 1
export const MAX_LATEST_COUNT = 50

/** The browser-local memory of the mode: whether it is on, and its count. */
const STORE_KEY = 'set-fleet-latest'

export interface LatestPrefs {
  on: boolean
  count: number
}

/** A count as typed, clamped to what the control offers; garbage is the default. */
export function clampCount(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return DEFAULT_LATEST_COUNT
  return Math.min(MAX_LATEST_COUNT, Math.max(MIN_LATEST_COUNT, Math.round(n)))
}

export function readLatestPrefs(): LatestPrefs {
  try {
    const raw = localStorage.getItem(STORE_KEY)
    if (!raw) return { on: false, count: DEFAULT_LATEST_COUNT }
    const parsed = JSON.parse(raw) as Partial<LatestPrefs> | null
    return {
      on: parsed?.on === true,
      count: parsed?.count === undefined ? DEFAULT_LATEST_COUNT : clampCount(parsed.count),
    }
  } catch {
    // Unavailable or corrupt storage: nothing is remembered, the mode starts off.
    return { on: false, count: DEFAULT_LATEST_COUNT }
  }
}

export function writeLatestPrefs(prefs: LatestPrefs): void {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(prefs))
  } catch {
    /* nothing remembered; the mode still works for this visit */
  }
}

/** Seconds since a person last wrote here, or null when none was found. */
export function recencyOf(agent: Pick<FleetAgent, 'last_human_input_seconds'>): number | null {
  const v = agent.last_human_input_seconds
  return typeof v === 'number' && Number.isFinite(v) ? v : null
}

/**
 * Most recent first; unmeasured after every measured agent. Ties fall back to
 * the pid so the order is deterministic — two polls that measure the same
 * thing must not produce two different screens.
 */
export function byRecency(a: FleetAgent, b: FleetAgent): number {
  const ra = recencyOf(a)
  const rb = recencyOf(b)
  if (ra === null && rb !== null) return 1
  if (rb === null && ra !== null) return -1
  if (ra !== null && rb !== null && ra !== rb) return ra - rb
  return a.pid - b.pid
}

/** Every agent of every project, once each. */
export function allAgents(projects: readonly FleetProject[]): FleetAgent[] {
  const seen = new Set<number>()
  const out: FleetAgent[] = []
  for (const p of projects) {
    for (const a of p.agents) {
      if (seen.has(a.pid)) continue
      seen.add(a.pid)
      out.push(a)
    }
  }
  return out
}

/** The slots when the mode is turned on: the `n` most recent, in order. */
export function initial(agents: readonly FleetAgent[], n: number): number[] {
  return [...agents].sort(byRecency).slice(0, Math.max(0, n)).map(a => a.pid)
}

/** Re-sort on request — the same answer as turning the mode on now. */
export function resort(agents: readonly FleetAgent[], n: number): number[] {
  return initial(agents, n)
}

/**
 * The slots after a new answer, moving as little as possible.
 *
 * - an agent that left the fleet frees its slot;
 * - an agent that is now within the most recent `n` but not shown takes a free
 *   slot, or else the slot of the shown agent with the OLDEST recency — and
 *   only that one tile changes;
 * - a smaller `n` drops the oldest shown agents, a larger one lets the next
 *   most recent in;
 * - a slot nobody can fill is removed rather than drawn empty.
 *
 * Returns the SAME array when nothing changed, so a caller holding it in state
 * does not re-render on every poll.
 */
export function update(slots: readonly number[], agents: readonly FleetAgent[], n: number): number[] {
  const want = Math.max(0, n)
  const byPid = new Map(agents.map(a => [a.pid, a]))
  const ranked = [...agents].sort(byRecency)
  const rankOf = new Map(ranked.map((a, i) => [a.pid, i]))

  let next: (number | null)[] = slots.map(pid => (byPid.has(pid) ? pid : null))

  // A smaller count: drop the oldest shown agents, keeping everyone else put.
  const shown = () => next.filter((p): p is number => p !== null)
  while (shown().length > want) {
    const oldest = shown().reduce((x, y) => ((rankOf.get(x) ?? 0) > (rankOf.get(y) ?? 0) ? x : y))
    next = next.map(p => (p === oldest ? null : p))
  }

  const top = ranked.slice(0, want).map(a => a.pid)
  const topSet = new Set(top)
  for (const pid of top) {
    if (next.includes(pid)) continue
    const free = next.indexOf(null)
    if (free >= 0) {
      next[free] = pid
      continue
    }
    if (next.length < want) {
      next.push(pid)
      continue
    }
    // Full: the newcomer takes the slot of the oldest shown agent that is no
    // longer among the most recent `n`. One always exists — the newcomer is in
    // the top `n` and the slots hold `n` agents, so one of them is not.
    let victim = -1
    for (let i = 0; i < next.length; i++) {
      const p = next[i]
      if (p === null || topSet.has(p)) continue
      if (victim < 0 || (rankOf.get(p) ?? 0) > (rankOf.get(next[victim] as number) ?? 0)) victim = i
    }
    if (victim >= 0) next[victim] = pid
  }

  const result = next.filter((p): p is number => p !== null)
  const same = result.length === slots.length && result.every((p, i) => p === slots[i])
  return same ? (slots as number[]) : result
}

/** The agents in slot order, for the grid. */
export function agentsInSlots(slots: readonly number[], agents: readonly FleetAgent[]): FleetAgent[] {
  const byPid = new Map(agents.map(a => [a.pid, a]))
  return slots.map(pid => byPid.get(pid)).filter((a): a is FleetAgent => a !== undefined)
}

/**
 * The synthetic project the mode shows — design D1.
 *
 * Everything downstream of the selected project (grid, enlarged view, tab
 * strip, columns) runs unchanged on it. Its `root` is EMPTY on purpose
 * (design D2): every tile must take its root from its own agent, and anything
 * still reading the selected project's root finds nothing rather than a wrong
 * tree — the project's files and board panels, which the mode does not offer,
 * hide themselves on exactly that.
 */
export function latestProject(agents: FleetAgent[]): FleetProject {
  return {
    name: LATEST_VIEW_KEY,
    root: '',
    sources: [],
    archived: false,
    agents,
    checkouts: [],
  }
}

/**
 * The root a tile in the mode acts on: its agent's own project root, then the
 * root its project is listed under. Null when neither is known — a link is then
 * not offered, rather than resolved against some other tree.
 */
export function rootOfAgent(agent: FleetAgent, projects: readonly FleetProject[]): string | null {
  if (agent.project_root) return agent.project_root
  const listed = projects.find(p => p.agents.some(a => a.pid === agent.pid))
    ?? projects.find(p => p.name === agent.project)
  return listed?.root || null
}

/**
 * Ctrl+←/→ switches the strip's tab in latest mode — asked for 2026-10-20:
 * *"pressing ctrl-left and ctrl-right combinations switch the panel tab on
 * latest mode layout to the next or prev tab"*.
 *
 * The user chose for it to work EVERYWHERE, inside a terminal included, which
 * costs the terminal its Ctrl+←/→ word-jump while latest mode is on (Alt+B /
 * Alt+F still jump words in shells and in Claude Code). One predicate, read by
 * both the terminal (to give the key up) and the page (to act on it), so the
 * two cannot disagree about which keystroke is the switch.
 *
 * Returns -1, +1, or 0 for any other key. Plain Ctrl only: Ctrl+Shift+← is
 * select-by-word in an input, and Alt/Meta combinations belong to the browser.
 */
export function tabSwitchDirection(e: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'altKey' | 'shiftKey' | 'metaKey'>): -1 | 0 | 1 {
  if (!e.ctrlKey || e.altKey || e.shiftKey || e.metaKey) return 0
  if (e.key === 'ArrowLeft') return -1
  if (e.key === 'ArrowRight') return 1
  return 0
}

/**
 * The index of the tab to switch to, wrapping at both ends; null when there is
 * nothing to switch to. With no tab active, → takes the first and ← the last.
 */
export function stepTab(entries: readonly { active: boolean }[], dir: -1 | 1): number | null {
  const n = entries.length
  if (n === 0) return null
  const at = entries.findIndex(t => t.active)
  if (at < 0) return dir === 1 ? 0 : n - 1
  if (n === 1) return null
  return (at + dir + n) % n
}
