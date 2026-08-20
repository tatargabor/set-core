/**
 * PM mode's client-side types and the two facts the browser owns.
 *
 * Everything else is decided by the server — what is queued, in what order,
 * whether a switch may be offered. The client contributes exactly one thing the
 * server cannot see: when the reader last typed into the presented terminal.
 */

export interface PmItem {
  pid: number
  project: string
  label: string | null
  /** `structural` (measured) or `model` (an opinion). Rendered differently. */
  source: string
  blocked_since: number
  blockage_point: number | null
  presented_count: number
}

export interface PmCounts {
  queued: number
  idle: number
  dismissed: number
  not_covered: number
  unclassified: number
  /**
   * ⚠ Never conflate with `queued === 0`. "Nothing needs you" and "we could not
   * look" lead to opposite actions, and the first is the one a reader acts on
   * by walking away.
   */
  judgment_measured: boolean
  judgment_reason: string | null
}

export interface PmSnapshot {
  enabled: boolean
  presented: PmItem | null
  queued: PmItem[]
  counts: PmCounts
  can_go_back: boolean
  can_go_forward: boolean
  /** What WOULD take the screen. Null while the typing window holds. */
  pending_switch: PmItem | null
  last_cycle: number | null
  last_error: string | null
  advanced?: boolean
}

/** How long the announced switch runs before it happens. Mirrors the server. */
export const COUNTDOWN_MS = 5000

/**
 * Seconds since the reader last put something into the presented session.
 *
 * `null` means they never have — which is the ABSENCE of the thing protection
 * is measured from, not protection itself. An agent nobody has typed into is
 * preemptible immediately, and that is right: nothing is being interrupted.
 */
export function secondsSinceInput(lastInputAt: number | null, now: number): number | null {
  if (lastInputAt === null) return null
  return Math.max(0, (now - lastInputAt) / 1000)
}

/**
 * Both input paths count as typing.
 *
 * The terminal is the obvious one. The instruct box is the one that gets
 * forgotten, and forgetting it is worse than it looks: for an agent the
 * framework holds no terminal for — 2 of 18 measured on this machine — the
 * instruct box is the ONLY way to answer, so a guard that watches only the
 * terminal protects nothing at all on exactly those items.
 */
export function latestInput(terminalAt: number | null, instructAt: number | null): number | null {
  if (terminalAt === null) return instructAt
  if (instructAt === null) return terminalAt
  return Math.max(terminalAt, instructAt)
}

/** A blockage's age in seconds, for the frame's ordering hint. */
export function blockageAge(item: PmItem, now: number): number {
  return Math.max(0, now / 1000 - item.blocked_since)
}
