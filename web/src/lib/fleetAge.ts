import type { FleetProject } from './fleetTypes'

/**
 * How long ago, in the shortest form that stays honest.
 *
 * Shared rather than copied. It was private to `Fleet.tsx` until the project
 * column needed the same sentence, and a second implementation of a formatter is
 * the second-copy defect this repository keeps meeting: the two drift, and the
 * screen then says `90s` in one place and `2m` in another about the same moment.
 */
export function age(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 90) return `${Math.round(seconds)}s`
  if (seconds < 5400) return `${Math.round(seconds / 60)}m`
  return `${Math.round(seconds / 3600)}h`
}

/**
 * The same instant, as a number that sorts EXACTLY the way `age` reads.
 *
 * Two rows showing `1s` and `1s` must not swap places every poll — the raw
 * seconds behind them differ in the third decimal, the fleet polls every couple
 * of seconds, and the top of the list is where the reader is about to click.
 *
 * A coarser bucket (whole minutes, say) fixes that and buys a worse problem,
 * measured on the running dashboard: with everything inside one minute, `3s`
 * rendered BELOW `32s`. The order was defensible and unreadable, which on a
 * screen is the same as wrong.
 *
 * So the key is the displayed value itself, at `age`'s own resolution: equal
 * text means an equal key — ties keep the reader's own order — and a different
 * text always sorts the way it reads. The two functions have to change
 * together, which is why they sit next to each other and share a test.
 */
export function ageKey(seconds: number): number {
  if (seconds < 90) return Math.round(seconds)
  if (seconds < 5400) return Math.round(seconds / 60) * 60
  return Math.round(seconds / 3600) * 3600
}

/**
 * The longest any agent in this project has gone without moving.
 *
 * The MAXIMUM, not the minimum or the mean: the question the fleet screen exists
 * to answer is *where has work stopped*, and one busy agent must not vouch for a
 * project whose other four have been still for an hour. A mean would do exactly
 * that, and it would look like data while doing it.
 *
 * `null` when nothing is known — no agents, or none of them reported a movement.
 * That is not the same as zero, and the caller has to be able to tell.
 */
export function stalestSeconds(project: FleetProject | undefined): number | null {
  const seen = (project?.agents ?? [])
    .map(a => a.last_movement_seconds)
    .filter((n): n is number => typeof n === 'number')
  return seen.length > 0 ? Math.max(...seen) : null
}

/**
 * The shortest time since any agent in this project moved.
 *
 * The MINIMUM, and it exists for the opposite question to `stalestSeconds`:
 * *which projects am I working in right now*. One project can be both — an
 * agent that moved seconds ago beside one still for an hour — so the two
 * numbers are kept apart rather than reconciled. Sorting on one while the row
 * displays the other is what would make the list look broken, and the reason
 * the recency order renders both when they differ.
 *
 * `null` when nothing is known, for the same reason as its counterpart: no
 * agents, or none of them reported a movement. Not zero, which would claim the
 * project moved this second.
 */
export function freshestSeconds(project: FleetProject | undefined): number | null {
  const seen = (project?.agents ?? [])
    .map(a => a.last_movement_seconds)
    .filter((n): n is number => typeof n === 'number')
  return seen.length > 0 ? Math.min(...seen) : null
}
