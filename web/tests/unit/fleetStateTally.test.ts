import { describe, expect, it } from 'vitest'

import { ASKING, EMPTY_TALLY, QUIET, UNKNOWN, WAITING, WORKING, tally } from '../../src/lib/fleetAttention'
import type { AttentionProject } from '../../src/lib/fleetAttention'

/**
 * The header's arithmetic must close — every state lands in exactly one bucket.
 *
 * Written after the defect it guards, found by review rather than by a test.
 * `tally()` was an `if / else if` chain over three states with no final branch,
 * so a fourth state was counted nowhere while `agents` still included it. The
 * numbers beside the agent simply stopped adding up, and in the expensive
 * direction: the agent that most needs a person vanishes from the header while
 * the screen looks calm.
 *
 * So the claim under test is not "asking is counted" — it is that the buckets
 * sum to the population, which is a claim about the next state too.
 */

const project = (...states: string[]): AttentionProject => ({
  name: 'p',
  agents: states.map((state, i) => ({ pid: i, state })),
})

describe('the tally closes over every state', () => {
  it('sums to the population', () => {
    const t = tally([project(WORKING, UNKNOWN, WAITING, ASKING, QUIET)])
    expect(t.working + t.unknown + t.waiting + t.asking + t.quiet + t.unbucketed).toBe(t.agents)
    expect(t.agents).toBe(5)
    expect(t.unbucketed).toBe(0)
  })

  it('reports a state no bucket counts instead of swallowing it', () => {
    const t = tally([project(WORKING, 'a-state-invented-later')])
    expect(t.unbucketed).toBe(1)
    expect(t.working + t.unknown + t.waiting + t.asking + t.quiet + t.unbucketed).toBe(t.agents)
  })

  it('keeps asking and waiting apart', () => {
    // A measurement and a declaration. Summing them makes the distinction
    // unrecoverable exactly when a reader wants it — deciding whether to
    // trust the number.
    const t = tally([project(ASKING, WAITING)])
    expect(t.asking).toBe(1)
    expect(t.waiting).toBe(1)
  })

  it('starts empty with every bucket present', () => {
    // A missing key would read as zero at every call site, which is the same
    // false-absence the unbucketed counter exists to prevent.
    for (const k of ['agents', 'working', 'unknown', 'waiting', 'asking', 'quiet', 'unbucketed'] as const) {
      expect(EMPTY_TALLY[k]).toBe(0)
    }
  })

  it('counts nothing twice across projects', () => {
    const t = tally([project(ASKING), project(ASKING, QUIET)])
    expect(t.agents).toBe(3)
    expect(t.asking).toBe(2)
    expect(t.quiet).toBe(1)
  })
})
