import { describe, expect, it } from 'vitest'

import { blockageAge, latestInput, secondsSinceInput } from '../../src/lib/fleetPm'
import type { PmItem } from '../../src/lib/fleetPm'

describe('the client-side half of the freeze', () => {
  it('never typed is not protection', () => {
    // The absence of the thing protection is measured from — not protection.
    expect(secondsSinceInput(null, 1000)).toBeNull()
  })

  it('measures from the last keystroke', () => {
    expect(secondsSinceInput(1_000_000, 1_030_000)).toBe(30)
  })

  it('never returns a negative age when the clocks disagree', () => {
    expect(secondsSinceInput(1_030_000, 1_000_000)).toBe(0)
  })

  it('counts the instruct box as typing too', () => {
    // For an agent with no framework terminal this is the ONLY answer path,
    // so a guard watching the terminal alone protects nothing on those items.
    expect(latestInput(null, 500)).toBe(500)
    expect(latestInput(500, null)).toBe(500)
    expect(latestInput(400, 900)).toBe(900)
    expect(latestInput(900, 400)).toBe(900)
    expect(latestInput(null, null)).toBeNull()
  })

  it('ages a blockage from its own start', () => {
    const item: PmItem = {
      pid: 1, project: 'p', label: null, source: 'model',
      blocked_since: 1000, blockage_point: 1000, presented_count: 0,
    }
    expect(blockageAge(item, 1_300_000)).toBe(300)
  })
})
