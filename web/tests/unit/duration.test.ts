/**
 * The unit ladder, asserted at every rung — including the one whose absence was visible on screen.
 *
 * `72104m57s` is what the orchestration table rendered for a change that had been running fifty
 * days: not a bug, just a formatter with no unit above the minute. Two of the other three copies
 * stopped at the hour and would have said `1201h44m` for the same value. All four are now one
 * function, and these tests are what stops the ladder being shortened again.
 */
import { describe, expect, it } from 'vitest'
import { formatDuration, formatDurationMs } from '../../src/lib/duration'

describe('formatDuration', () => {
  it('reads at a glance at every magnitude', () => {
    expect(formatDuration(45)).toBe('45s')
    expect(formatDuration(750)).toBe('12m30s')
    expect(formatDuration(11_100)).toBe('3h05m')
    expect(formatDuration(4_326_297)).toBe('50d 01h')
  })

  it('never emits a magnitude the reader has to divide in their head', () => {
    // The shape that was on screen. Held as an assertion rather than a comment so a later
    // "simplify the ladder" fails here instead of shipping `72104m57s` a second time.
    const fiftyDays = 72104 * 60 + 57
    expect(formatDuration(fiftyDays)).not.toMatch(/^\d{4,}m/)
    expect(formatDuration(fiftyDays)).not.toMatch(/^\d{3,}h/)
  })

  it('keeps zero and absent apart, because they mean different things', () => {
    // A duration of nothing is a measurement; a missing duration is not. Collapsing them is the
    // same false-absence this surface refuses for counts.
    expect(formatDuration(0)).toBe('0s')
    expect(formatDuration(undefined)).toBe('—')
    expect(formatDuration(undefined, '')).toBe('')
  })

  it('pads the minor unit so a column of durations stays comparable', () => {
    // `3h5m` under `3h05m` misaligns and reads as a different magnitude for a moment.
    expect(formatDuration(3 * 3600 + 5 * 60)).toBe('3h05m')
    expect(formatDuration(3 * 3600 + 45 * 60)).toBe('3h45m')
  })
})

describe('formatDurationMs', () => {
  it('keeps sub-second precision where that is the point', () => {
    expect(formatDurationMs(420)).toBe('420ms')
    expect(formatDurationMs(4200)).toBe('4.2s')
  })

  it('hands anything longer to the shared ladder rather than carrying its own', () => {
    // A long call and a long change must be described the same way; two ladders would drift.
    expect(formatDurationMs(11_100_000)).toBe(formatDuration(11_100))
  })
})
