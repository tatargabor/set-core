/**
 * One duration formatter, because there were four and they disagreed about where to stop.
 *
 * Found by looking at the orchestration screen: a change had been running long enough that its
 * cell read `72104m57s`. Nothing was broken — the formatter simply had no unit above the minute,
 * so it kept counting. Two of the other three copies stopped at the hour and would have rendered
 * the same value as `1201h44m`, which is no easier to read and disagrees with the first.
 *
 * This is the second-place defect in its plainest form: one fact, four renderings, drifting
 * independently. The unit ladder is not a matter of taste and does not deserve four opinions —
 * `formatTokens`, ten lines below one of those copies, already rolled over at every 1000×.
 *
 * The rule it follows: show two units at most, and never a number whose magnitude the reader has
 * to divide in their head. A duration a person cannot read at a glance reports the same thing as
 * no duration at all, only more convincingly.
 */

/**
 * Seconds as a human duration: `45s`, `12m30s`, `3h07m`, `50d 01h`.
 *
 * Returns the caller's own placeholder for a missing value rather than inventing one. `0` is a
 * real duration and formats as `0s`; `undefined` is an absence and must not become one — the
 * distinction this surface keeps everywhere else applies to time as much as to counts.
 */
export function formatDuration(secs?: number, absent = '—'): string {
  if (secs === undefined || secs === null || Number.isNaN(secs)) return absent
  if (secs < 0) return absent

  const s = Math.floor(secs)
  if (s < 60) return `${s}s`

  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m${String(s % 60).padStart(2, '0')}s`

  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h${String(m % 60).padStart(2, '0')}m`

  const d = Math.floor(h / 24)
  return `${d}d ${String(h % 24).padStart(2, '0')}h`
}

/**
 * Milliseconds, for call-level timings where sub-second precision is the point.
 *
 * Delegates above a minute rather than carrying its own ladder, so a long call and a long change
 * are described the same way. The sub-second range stays here because it exists nowhere else.
 */
export function formatDurationMs(ms: number, absent = '-'): string {
  if (!Number.isFinite(ms) || ms <= 0) return absent
  if (ms < 1000) return `${Math.round(ms)}ms`
  const s = ms / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  return formatDuration(s, absent)
}
