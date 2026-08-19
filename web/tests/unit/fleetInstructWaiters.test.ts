/**
 * The decisions behind the instruction input and the waiter list — tasks 7.7,
 * 7.13, 4.4, 3.4/3.5 and 3.9, asserted as pure functions.
 *
 * Every case here is a direction the surface may not fail in, and each has a
 * cheap wrong implementation that looks identical from far away:
 *
 *  - `outcome` read off the status code → `sits-unread` renders as a delivery;
 *  - `held` treated as finished → the tile shows "held" for a dead message;
 *  - `unknown` upgraded to a delivery → a silence becomes a yes;
 *  - a missing `waiters_here` read as zero → a remedy offered for a problem
 *    nobody measured;
 *  - `declared.blocked` folded into `state` → the pair that disagrees becomes
 *    unsayable, and that pair exists on this machine right now;
 *  - `progress.measured: false` drawn as `0/0` → a bar for a change nobody
 *    counted, identical to one nobody started.
 */
import { describe, expect, it } from 'vitest'

import {
  holdNote,
  isSettled,
  meaningOf,
  offerWaiterRemedy,
} from '../../src/lib/fleetInstructOutcome'
import {
  blockUnexpectedFrom,
  declarationAge,
  declaredStanding,
  declaresBlocked,
  instructability,
  phaseRepeatsBlock,
  purposeStanding,
} from '../../src/lib/fleetDeclared'

describe('an outcome is not a status code', () => {
  it('separates the deliveries from the sends that reached nobody', () => {
    expect(meaningOf('arrives-now').tone).toBe('delivered')
    expect(meaningOf('at-turn-end').tone).toBe('delivered')
    expect(meaningOf('sits-unread').tone).toBe('undelivered')
    expect(meaningOf('wakes-nobody').tone).toBe('undelivered')
  })

  /**
   * The counter-intuitive one, and getting it backwards is a real risk: the
   * name sounds like a deferral, but the agent's stop-hook will not let the
   * turn close over unread addressed mail, so the agent DOES get it.
   */
  it('counts `at-turn-end` as a delivery, because the producer measured it as one', () => {
    expect(meaningOf('at-turn-end').tone).toBe('delivered')
  })

  it('never renders an unrecognised outcome as a success', () => {
    const m = meaningOf('something-new-from-the-channel')
    expect(m.tone).toBe('unknown')
    expect(m.label).toBe('something-new-from-the-channel')
  })

  it('says the channel gave no usable answer rather than treating it as a quiet yes', () => {
    expect(meaningOf('unknown').tone).toBe('unknown')
    expect(meaningOf('unknown').tone).not.toBe('delivered')
  })
})

describe('`held` is not a resting state', () => {
  it('is the one outcome that is not settled', () => {
    expect(isSettled({ outcome: 'held', settled: false })).toBe(false)
    for (const o of ['arrives-now', 'at-turn-end', 'sits-unread', 'wakes-nobody', 'expired', 'refused', 'not-instructable']) {
      expect(isSettled({ outcome: o, settled: true })).toBe(true)
    }
  })

  /**
   * The fallback matters: an older producer sends no `settled`, and resolving
   * that to "done" would freeze a hold into a permanent claim — which is the
   * exact defect the non-terminal outcome exists to prevent.
   */
  it('still knows a hold is open when the producer sends no `settled`', () => {
    expect(isSettled({ outcome: 'held' } as { outcome: string; settled: boolean })).toBe(false)
    expect(isSettled({ outcome: 'arrives-now' } as { outcome: string; settled: boolean })).toBe(true)
  })

  /**
   * There is no endpoint that re-asks what became of a hold. So the honest
   * sentence is not "held" — a claim about now that nobody verified — but "held
   * as of N ago, not re-checked since", which is a claim about a moment and
   * stays true.
   */
  it('states a hold as a moment with an age, never as a present fact', () => {
    expect(holdNote(12)).toMatch(/12s ago/)
    expect(holdNote(600)).toMatch(/10m ago/)
    expect(holdNote(5)).toMatch(/re-checked/)
  })
})

describe('the missing-waiter remedy is offered where the count is zero', () => {
  it('offers it on a measured zero', () => {
    expect(offerWaiterRemedy({ waiters_here: 0 })).toBe(true)
    expect(offerWaiterRemedy({ waiters: 0 })).toBe(true)
  })

  it('does not offer it when waiters were found', () => {
    expect(offerWaiterRemedy({ waiters_here: 2 })).toBe(false)
  })

  /** An absent count is not a zero — the false-absence direction. */
  it('offers nothing when no count was reported at all', () => {
    expect(offerWaiterRemedy({})).toBe(false)
  })

  /**
   * ⚠ THE REPORTED ONE, 2026-08-19, with a screenshot.
   *
   * A send the channel refused — the seat was in a room the sender had not
   * joined — rendered this remedy under the refusal, saying *"every instruction
   * sent here sits unread"*. Nothing had been sent. The waiter count was a true
   * measurement of a condition the send never reached, and the sentence built
   * on it was a present-tense claim about messages that do not exist.
   *
   * It cost more than a wrong sentence: the remedy is AMBER, which means *needs
   * attention* everywhere on this screen, while the remedy that would have
   * worked — the channel's own *join the room first* — was the faintest line on
   * the card. The wrong instruction had the alarm and the right one had the
   * whisper.
   */
  it('offers nothing when the send never happened', () => {
    expect(offerWaiterRemedy({ waiters_here: 0, accepted: false })).toBe(false)
    expect(offerWaiterRemedy({ waiters: 0, accepted: false })).toBe(false)
  })

  /**
   * And an ABSENT `accepted` is not a refusal. Suppressing on a missing field
   * would hide a real remedy on an older server — the same false-absence
   * direction as the test above, mirrored.
   */
  it('still offers it when the send was made, or when nothing said whether it was', () => {
    expect(offerWaiterRemedy({ waiters_here: 0, accepted: true })).toBe(true)
    expect(offerWaiterRemedy({ waiters_here: 0 })).toBe(true)
  })
})

describe('where the input cannot be, the reason stands in its place', () => {
  it('gives the seat when the agent can be addressed', () => {
    expect(instructability({ instructable: true, seat: 'set-core#abc' })).toEqual({ kind: 'yes', seat: 'set-core#abc' })
  })

  it('carries the producer’s own sentence when it cannot', () => {
    expect(instructability({ instructable: false, reason: 'this session has no seat on the messaging bus' }))
      .toEqual({ kind: 'no', reason: 'this session has no seat on the messaging bus' })
  })

  it('says something rather than nothing when the producer refused without a reason', () => {
    const r = instructability({ instructable: false, reason: null })
    expect(r.kind).toBe('no')
    expect(r.kind === 'no' && r.reason.length).toBeGreaterThan(0)
  })

  /**
   * An older server sends neither field. Reading that as a refusal would remove
   * the input from every agent on a server that merely predates the feature —
   * an absent key is not a `false`.
   */
  it('treats a server that says nothing as unknown, not as a refusal', () => {
    expect(instructability({}).kind).toBe('unknown')
  })
})

describe('what the agent SAYS, beside what was measured', () => {
  it('tells apart “could not ask” from “says nothing”', () => {
    expect(declaredStanding({ declared: { known: false } }).kind).toBe('unasked')
    expect(declaredStanding({ declared: { known: true, focus: null, phase: null, blocked: false, files: [] } }).kind).toBe('silent')
    expect(declaredStanding({ declared: null }).kind).toBe('unasked')
  })

  /**
   * The live case this exists for, measured on this machine 2026-08-19:
   * pid 1433849 was `state: quiet` with `declared.blocked: true`. The tile drew
   * it as calm.
   */
  it('marks a declared block that the measurement does not lead you to expect', () => {
    const standing = declaredStanding({ declared: { known: true, blocked: true, phase: 'blocked' } })
    expect(declaresBlocked(standing)).toBe(true)
    expect(blockUnexpectedFrom('quiet', standing)).toBe(true)
    expect(blockUnexpectedFrom('working', standing)).toBe(true)
  })

  it('does not shout about a block beside `waiting`, where it is the reason rather than a surprise', () => {
    const standing = declaredStanding({ declared: { known: true, blocked: true } })
    expect(blockUnexpectedFrom('waiting', standing)).toBe(false)
  })

  /**
   * Found by looking at the live screen, not by a test: one tile carried
   * `⚠ says it is blocked` in its header and `says: blocked` a line below —
   * one claim, twice, in two weights. The two come from different fields and
   * coincide when an agent names its phase after the flag.
   */
  it('drops a phase that only repeats the marker already shown', () => {
    expect(phaseRepeatsBlock('blocked', true)).toBe(true)
    expect(phaseRepeatsBlock('  Blocked ', true)).toBe(true)
  })

  /**
   * The direction that matters. Beside `waiting` the marker is deliberately not
   * drawn, so dropping the phase there too would take the block off the tile
   * entirely — a duplicate traded for a false absence.
   */
  it('keeps the phase when nothing else on the tile is carrying the block', () => {
    expect(phaseRepeatsBlock('blocked', false)).toBe(false)
    const standing = declaredStanding({ declared: { known: true, blocked: true, phase: 'blocked' } })
    expect(blockUnexpectedFrom('waiting', standing)).toBe(false)
    expect(phaseRepeatsBlock('blocked', blockUnexpectedFrom('waiting', standing))).toBe(false)
  })

  it('leaves any other phase alone', () => {
    expect(phaseRepeatsBlock('verify', true)).toBe(false)
    expect(phaseRepeatsBlock('blocked-on-review', true)).toBe(false)
    expect(phaseRepeatsBlock(null, true)).toBe(false)
  })

  it('never lets a declaration stand in for a measurement', () => {
    // A declaration that says nothing does not make an unknown state known, and
    // a declared block does not make a quiet agent "blocked" — the two fields
    // are reported side by side and this module has no path that merges them.
    const standing = declaredStanding({ declared: { known: true, blocked: true } })
    expect(declaresBlocked(standing)).toBe(true)
    expect(standing.kind === 'declared' && 'state' in standing).toBe(false)
  })

  it('ages a declaration, because it does not expire on its own', () => {
    const now = Date.parse('2026-08-19T12:00:00Z')
    expect(declarationAge('2026-08-19T11:00:00Z', now)).toBe(3600)
    expect(declarationAge(null, now)).toBeNull()
    expect(declarationAge('not a date', now)).toBeNull()
  })
})

describe('what the agent is working towards', () => {
  it('states the absence of a record rather than drawing an empty field', () => {
    expect(purposeStanding({ purpose: null }).kind).toBe('no-record')
    expect(purposeStanding({}).kind).toBe('no-record')
  })

  it('carries the change, the status and the counted progress', () => {
    const p = purposeStanding({ purpose: {
      change: 'fleet-view', group: 'ui', status: 'running',
      progress: { done: 3, total: 10, partial: 0, measured: true, fraction: 0.3 },
    } })
    expect(p).toMatchObject({ kind: 'purpose', change: 'fleet-view', status: 'running' })
    expect(p.kind === 'purpose' && p.progress).toEqual({ done: 3, total: 10, fraction: 0.3 })
  })

  /**
   * `measured: false` means the task file could not be counted. A `0/0` draws a
   * progress bar identical to a change nobody has started — the false-value
   * class, arriving through a field that looks like data.
   */
  it('reports no progress rather than zero progress when nothing was counted', () => {
    const p = purposeStanding({ purpose: {
      change: 'x', progress: { done: 0, total: 0, partial: 0, measured: false, fraction: null },
    } })
    expect(p.kind === 'purpose' && p.progress).toBeNull()
  })

  it('keeps `stale` and `pid_unverified` as facts the reader can see', () => {
    const p = purposeStanding({ purpose: { change: 'x', status: 'stale', pid_unverified: true } })
    expect(p).toMatchObject({ status: 'stale', pidUnverified: true })
  })
})
