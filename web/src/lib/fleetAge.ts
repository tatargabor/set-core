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
