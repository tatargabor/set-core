/**
 * The distinctions the work-cycle panel must not flatten.
 *
 * Every case here is one this repository has already paid for somewhere else:
 * a waiting unit rendered as a broken one, a zero that came from a list nobody
 * could read, and a `null` rendered as a `false`.
 */
import { describe, it, expect } from 'vitest'
import {
  attentionLabel, attentionMark, needsAttention, originLabel, runState, runnableLabel,
  type WorkRun,
} from '../../src/lib/fleetWorkCycle'

const run = (over: Partial<WorkRun> = {}): WorkRun => ({
  unit_id: 'u1', change: 'demo', status: 'finished', ...over,
})

describe('runState', () => {
  it('a unit waiting for a person is not a failed one', () => {
    // The two have the IDENTICAL shape on disk — no gate, no commit.
    const waiting = run({ set_aside: { kind: 'human-decision', question: 'which?', task: '2.2' },
                          verdict: { outcome: 'NEEDS_INPUT' } })
    const failed = run({ verdict: { outcome: 'BLOCKED' } })
    expect(runState(waiting)).toBe('waiting')
    expect(runState(failed)).toBe('failed')
  })

  it('a stale claim is not a slow run', () => {
    expect(runState(run({ status: 'stale' }))).toBe('stale')
  })

  it('a live claim whose pid could not be confirmed says so', () => {
    // "a process holds that number" is a different answer from "your run is alive".
    expect(runState(run({ status: 'running' }))).toBe('running')
    expect(runState(run({ status: 'running', pid_unverified: true }))).toBe('unconfirmed')
  })

  it('a run that never reported a verdict gets its own state', () => {
    expect(runState(run({ verdict: null }))).toBe('unreported')
  })

  it('a red gate is a failure even with a verdict that says otherwise', () => {
    expect(runState(run({ verdict: { outcome: 'GROUP_DONE' },
                          gate: { state: 'failed', failures: ['tsc'] } }))).toBe('failed')
  })

  it('a finished, green run is done', () => {
    expect(runState(run({ verdict: { outcome: 'GROUP_DONE' },
                          gate: { state: 'passed' } }))).toBe('done')
  })
})

describe('attentionMark', () => {
  it('counts what a reader must be told about behind a collapsed band', () => {
    const mark = attentionMark([
      run({ verdict: { outcome: 'GROUP_DONE' }, gate: { state: 'passed' } }),
      run({ verdict: { outcome: 'BLOCKED' } }),
      run({ status: 'stale' }),
      run({ set_aside: { question: 'q' }, verdict: { outcome: 'NEEDS_INPUT' } }),
    ])
    expect(mark.count).toBe(3)
    expect(mark.measured).toBe(true)
    expect(mark.byState).toEqual({ failed: 1, stale: 1, waiting: 1 })
  })

  it('a zero from an unread list is NOT a zero from a healthy one', () => {
    // The whole reason `measured` exists. Both have count 0 and they mean
    // opposite things; a screen that shows only the number says "all well" about
    // a project it could not look at.
    const healthy = attentionMark([run({ verdict: { outcome: 'GROUP_DONE' },
                                         gate: { state: 'passed' } })])
    const unread = attentionMark(null)
    expect(healthy.count).toBe(0)
    expect(unread.count).toBe(0)
    expect(healthy.measured).toBe(true)
    expect(unread.measured).toBe(false)
    expect(attentionLabel(healthy)).toBe('')
    expect(attentionLabel(unread)).toContain('could not read')
  })

  it('the label names how many of each, not merely that there is one', () => {
    const mark = attentionMark([run({ verdict: { outcome: 'BLOCKED' } }),
                                run({ verdict: { outcome: 'BLOCKED' } }),
                                run({ status: 'stale' })])
    expect(attentionLabel(mark)).toBe('2 failed, 1 stale')
  })

  it('needsAttention agrees with the states it is built from', () => {
    expect(needsAttention(run({ status: 'stale' }))).toBe(true)
    expect(needsAttention(run({ status: 'running' }))).toBe(false)
    expect(needsAttention(run({ verdict: { outcome: 'GROUP_DONE' },
                                gate: { state: 'passed' } }))).toBe(false)
  })
})

describe('runnableLabel', () => {
  it('null is unknown, never "not runnable"', () => {
    const got = runnableLabel({ runnable: null, available: false,
                                reason: 'set-work-cycle is not installed' })
    expect(got.tone).toBe('unknown')
    expect(got.text).toContain('not installed')
  })

  it('a blocked change carries the engine’s own reason, not a generic one', () => {
    const got = runnableLabel({ runnable: false,
                                reasons: { '2': 'blocked by 1 [declared]' } })
    expect(got.tone).toBe('blocked')
    expect(got.text).toBe('2: blocked by 1 [declared]')
  })

  it('does not summarise a single reason — naming the group is shorter and says more', () => {
    const got = runnableLabel({ runnable: false, reasons: { '2': 'blocked by 1 [declared]' } })
    expect(got.text).toBe('2: blocked by 1 [declared]')
  })

  it('summarises when every group says the same thing, keeping the detail', () => {
    // ⚠ Seen on the real screen, not imagined: a finished change rendered as
    // `1: complete · 2: complete · … · acceptance-…: complete` — one fact stated
    // eight times, wide enough to push the start button out of view.
    const got = runnableLabel({
      runnable: false,
      reasons: { '1': 'complete', '2': 'complete', '3': 'complete' },
    })
    expect(got.text).toBe('all 3 groups complete')
    expect(got.detail).toBe('1: complete · 2: complete · 3: complete')
  })

  it('does NOT summarise when the groups differ — that would hide the difference', () => {
    const got = runnableLabel({
      runnable: false,
      reasons: { '1': 'complete', '2': 'blocked by 1 [declared]' },
    })
    expect(got.text).toBe('1: complete · 2: blocked by 1 [declared]')
  })

  it('a runnable change names the group the engine would run', () => {
    expect(runnableLabel({ runnable: true, selected: '3' }))
      .toEqual({ tone: 'ready', text: 'group 3' })
  })
})

describe('originLabel', () => {
  it('marks the origin as a claim, because nothing verified it', () => {
    expect(originLabel(run({ started_by: 'set-core#abc' }))).toBe('set-core#abc (claimed)')
  })

  it('says nobody said, rather than inventing a starter', () => {
    expect(originLabel(run({ started_by: null }))).toBe('nobody said who asked')
  })
})
