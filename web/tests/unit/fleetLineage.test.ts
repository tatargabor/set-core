/**
 * Lineage in both directions — 7.8 upwards, 7.18 downwards.
 *
 * Each direction has one claim it is not allowed to make, and both are the
 * false-value shape this screen exists against:
 *
 *  - **upwards**: a record and a process-tree walk are two different claims,
 *    and flattening them into one "parent" reports an inference as a fact. The
 *    screen is the last place they can still be told apart;
 *  - **downwards**: the count covers recorded starts that are still running. A
 *    bare `2` reads as *this agent has two children*, which nobody measured —
 *    and `known: false` is not zero, because without a seat there was no key to
 *    look anything up by.
 */
import { describe, expect, it } from 'vitest'

import {
  ANCESTRY_NOTE,
  RECORDED_NOTE,
  countIsComplete,
  descendantStanding,
  parentClaim,
} from '../../src/lib/fleetLineage'

describe('who started this agent — two sources, two claims', () => {
  it('marks the owner’s record as a record', () => {
    const c = parentClaim({ parent: { seat: 'set-core#f1afe440', source: 'recorded' } })
    expect(c).toMatchObject({ kind: 'parent', label: 'set-core#f1afe440', measured: true, note: RECORDED_NOTE })
  })

  it('marks the process-tree walk as the inference it is', () => {
    const c = parentClaim({ parent: { seat: 'other#123', source: 'ancestry' } })
    expect(c).toMatchObject({ kind: 'parent', measured: false, note: ANCESTRY_NOTE })
  })

  /**
   * The refuted implementation: one "parent" field, one weight. It type-checks,
   * reads as a simplification, and turns a guess into a fact on screen.
   */
  it('gives the two sources different notes — a flattened parent would not', () => {
    const rec = parentClaim({ parent: { seat: 'a', source: 'recorded' } })
    const anc = parentClaim({ parent: { seat: 'a', source: 'ancestry' } })
    expect(rec.kind === 'parent' && anc.kind === 'parent' && rec.note === anc.note).toBe(false)
    expect(rec.kind === 'parent' && rec.measured).toBe(true)
    expect(anc.kind === 'parent' && anc.measured).toBe(false)
  })

  /**
   * An ancestor with no session record has no seat name. Reporting nothing
   * there loses the relation entirely, which is a false absence: the relation
   * IS known, only the name is missing.
   */
  it('falls back to the bare pid rather than dropping a parent with no seat', () => {
    const c = parentClaim({ parent: { seat: null, source: 'ancestry', pid_without_seat: 4242 } })
    expect(c).toMatchObject({ kind: 'parent', label: 'pid 4242', seat: null })
  })

  it('says nothing when there is no parent at all', () => {
    expect(parentClaim({}).kind).toBe('none')
    expect(parentClaim({ parent: null }).kind).toBe('none')
    expect(parentClaim({ parent: { seat: null, source: 'ancestry' } }).kind).toBe('none')
  })
})

describe('who runs under it — a bounded count that says so', () => {
  const some = {
    known: true, live: 2, pids: [11, 22], live_only: true,
    reason: 'counted from RECORDED starts that are still running; a child that has already exited is not here',
  }

  it('carries the count with the pids that make it up', () => {
    const s = descendantStanding({ descendants: some })
    expect(s).toMatchObject({ kind: 'some', live: 2, pids: [11, 22] })
  })

  /**
   * The load-bearing one. The producer's own caveat travels with the number, so
   * the surface cannot show a figure that reads as complete.
   */
  it('never reports the count as complete while it counts only live children', () => {
    const s = descendantStanding({ descendants: some })
    expect(s.kind === 'some' && s.caveat).toBeTruthy()
    expect(countIsComplete(s)).toBe(false)
  })

  it('stops apologising the day the producer can see exited children', () => {
    const s = descendantStanding({ descendants: { known: true, live: 1, pids: [7], live_only: false } })
    expect(countIsComplete(s)).toBe(true)
  })

  /**
   * `known: false` means there was no key to look this agent up by. A zero
   * there states "nothing runs under it" about an agent that may have started
   * five — the false-absence direction, and the expensive one.
   */
  it('says we could not look, rather than none', () => {
    const s = descendantStanding({ descendants: { known: false, live: 0, pids: [], reason: 'no seat' } })
    expect(s.kind).toBe('unknown')
    expect(s.kind === 'unknown' && s.reason).toBe('no seat')
  })

  it('treats an absent field as unknown, not as none', () => {
    expect(descendantStanding({}).kind).toBe('unknown')
    expect(descendantStanding({ descendants: null }).kind).toBe('unknown')
  })

  it('reports a measured none as none, with its caveat kept', () => {
    const s = descendantStanding({ descendants: { known: true, live: 0, pids: [], live_only: true, reason: 'r' } })
    expect(s.kind).toBe('none')
    expect(s.kind === 'none' && s.caveat).toBe('r')
  })

  /**
   * Counted from the LIST, not from the reported number: a count and its own
   * breakdown disagreeing is exactly the shape that turns a wrong zero into a
   * proof. Here the list wins, because it is the thing the surface can show.
   */
  it('counts the pids it can name when the number disagrees with them', () => {
    const s = descendantStanding({ descendants: { known: true, live: 9, pids: [1, 2], live_only: true } })
    expect(s.kind === 'some' && s.live).toBe(2)
  })
})
