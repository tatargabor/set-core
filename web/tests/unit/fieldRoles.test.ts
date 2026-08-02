/**
 * The surface half: a role applies because the project DECLARED it, never because of a field's
 * name and never from the declaration alone.
 *
 * The negative tests are the load-bearing ones. A renderer that recognised `pid` as an identifier
 * would pass every positive test here and would have moved one project's vocabulary into a
 * framework meant to serve the next one too.
 */

import { describe, expect, it } from 'vitest'
import { resolveRole, humanDuration } from '../../src/components/statusShape'

describe('resolveRole', () => {
  it('applies a declared simple role', () => {
    expect(resolveRole({ pid: 'id' }, { pid: 3218705 }, 'pid')).toEqual({ kind: 'id' })
    expect(resolveRole({ p: 'path' }, { p: 'a/b.log' }, 'p')).toEqual({ kind: 'path' })
    expect(resolveRole({ t: 'count' }, { t: 4 }, 't')).toEqual({ kind: 'count' })
    expect(resolveRole({ e: 'duration-seconds' }, { e: 1151 }, 'e'))
      .toEqual({ kind: 'duration-seconds' })
  })

  it('gives an UNDECLARED field named pid no role at all', () => {
    // The load-bearing negative. Make the renderer recognise the name and this is what fails.
    expect(resolveRole({}, { pid: 3218705 }, 'pid')).toBeNull()
    expect(resolveRole({ turns: 'count' }, { pid: 3218705 }, 'pid')).toBeNull()
  })

  it('drops an unknown role silently rather than refusing it', () => {
    // The fail direction is the whole point: a producer shipping a new role must never blank a
    // working surface. The value renders as it does today and improves when we learn the role.
    expect(resolveRole({ size: 'bytes' }, { size: 100 }, 'size')).toBeNull()
  })

  it('refuses a style request — display carries meaning, never appearance', () => {
    for (const style of ['bold', 'red', '%.2f', 'right', 'monospace']) {
      expect(resolveRole({ f: style }, { f: 1 }, 'f')).toBeNull()
    }
  })

  it('resolves a pair from a SIBLING key', () => {
    const owner = { tasksDone: 6, tasksTotal: 7 }
    expect(resolveRole({ tasksDone: { progressOf: 'tasksTotal' } }, owner, 'tasksDone'))
      .toEqual({ kind: 'progress', partner: 'tasksTotal', partnerValue: 7 })
  })

  it('drops a pair whose partner is absent, rather than inventing a denominator', () => {
    expect(resolveRole({ tasksDone: { progressOf: 'tasksTotal' } }, { tasksDone: 6 }, 'tasksDone'))
      .toBeNull()
  })

  it('drops a pair whose partner is not a number', () => {
    const owner = { tasksDone: 6, tasksTotal: 'seven' }
    expect(resolveRole({ tasksDone: { progressOf: 'tasksTotal' } }, owner, 'tasksDone')).toBeNull()
  })

  it('keeps a ZERO partner — a run with no tasks is a real state', () => {
    // A truthiness check would drop this and the role would vanish with no sign it ever existed.
    const owner = { tasksDone: 0, tasksTotal: 0 }
    expect(resolveRole({ tasksDone: { progressOf: 'tasksTotal' } }, owner, 'tasksDone'))
      .toEqual({ kind: 'progress', partner: 'tasksTotal', partnerValue: 0 })
  })

  it('never reaches outside the owning object for a partner', () => {
    // The dangerous direction: a bar built from ANOTHER run's total is wrong and plausible. Only
    // the owner is consulted, so a partner one level up cannot be borrowed.
    const owner = { tasksDone: 6 }
    expect(resolveRole({ tasksDone: { progressOf: 'tasksTotal' } }, owner, 'tasksDone')).toBeNull()
  })

  it('gives no role when there is no owner to resolve a pair against', () => {
    expect(resolveRole({ a: { progressOf: 'b' } }, null, 'a')).toBeNull()
  })

  it('resolves a limit pair the same way', () => {
    const owner = { contextTokens: 90, contextHardLimit: 100 }
    expect(resolveRole({ contextTokens: { limitOf: 'contextHardLimit' } }, owner, 'contextTokens'))
      .toEqual({ kind: 'limit', partner: 'contextHardLimit', partnerValue: 100 })
  })

  it('a dotted declaration matches nothing, and that is the documented selector', () => {
    // The shape a producer reaches for first, and its failure is SILENT — no role, no error,
    // and the declaration looks correct on their side. Held as a test, not a comment.
    expect(resolveRole({ 'running.pid': 'id' }, { pid: 1 }, 'pid')).toBeNull()
  })

  it('an empty declaration is the behaviour every project has today', () => {
    expect(resolveRole({}, { pid: 1, elapsedSec: 1151, tasksDone: 6 }, 'elapsedSec')).toBeNull()
  })
})

describe('humanDuration', () => {
  it('reads as a duration rather than as a quantity of seconds', () => {
    expect(humanDuration(45)).toBe('45s')
    expect(humanDuration(1151)).toBe('19m 11s')
    expect(humanDuration(3600)).toBe('1h 0m')
    expect(humanDuration(90061)).toBe('1d 1h')
  })

  it('passes through anything that is not a duration instead of inventing one', () => {
    expect(humanDuration(-5)).toBe('-5')
    expect(humanDuration(NaN)).toBe('NaN')
  })
})
