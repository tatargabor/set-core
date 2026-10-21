/**
 * The browser tab badge — asked 2026-09-01: `SET (N)` in the tab while an
 * agent needs a person, per-reader because "just for me".
 *
 * The count is the screen's own "needs a person" classes, never a new
 * measurement; the preference is per-browser storage with a guarded read,
 * because a badge setting must never be able to take the screen down.
 */
import { describe, expect, it } from 'vitest'
import { askingYou, needsPerson, readyToRead, tabTitle, loadTabBadge, saveTabBadge, TAB_BADGE_KEY } from '../../src/lib/fleetTabBadge'
import { EMPTY_TALLY, tally } from '../../src/lib/fleetAttention'
import type { AttentionProject } from '../../src/lib/fleetAttention'

const A = (over: Record<string, unknown>): AttentionProject =>
  ({ name: 'p', agents: [{ pid: 1, state: 'quiet', ...over }], awaiting: { total: 0 } } as AttentionProject)

/** A storage double — the real one can throw, so the tests exercise that too. */
function fakeStorage(initial: Record<string, string> = {}, fail = false): Storage {
  const map = new Map(Object.entries(initial))
  return {
    getItem: (k: string) => {
      if (fail) throw new Error('site data blocked')
      return map.get(k) ?? null
    },
    setItem: (k: string, v: string) => {
      if (fail) throw new Error('site data blocked')
      map.set(k, v)
    },
  } as unknown as Storage
}

describe('the two counts — blocked on you, and finished — B-160', () => {
  it('splits a question from a finished turn', () => {
    const t = tally([
      A({ state: 'asking', attention: 'prompt' }),
      A({ attention: 'input' }),
      A({ attention: 'background' }),
      A({ attention: 'working' }),
      A({ attention: 'unmeasured' }),
    ])
    expect(needsPerson(t)).toBe(1)
    // A finished agent with a dev server still up is finished all the same.
    expect(readyToRead(t)).toBe(2)
  })

  it('a finished turn turns the tab GREEN, not the warning — the case that never fired', () => {
    const t = tally([A({ attention: 'input', input_wait_seconds: 5 })])
    expect(tabTitle('SET', needsPerson(t), readyToRead(t))).toBe('🟢 SET (1)')
  })

  it('a running agent between two log flushes turns NOTHING on — the false green', () => {
    // `quiet` in the log, `busy` in the runtime record: measured live, and the
    // only agents the old `totals.quiet` green ever fired for.
    const t = tally([A({ state: 'quiet', attention: 'working' })])
    expect(tabTitle('SET', needsPerson(t), readyToRead(t))).toBe('SET')
  })

  it('never double-counts a background waiter standing alone', () => {
    const t = tally([A({ attention: 'background' })])
    expect(t.background).toBe(1)
    expect(readyToRead(t)).toBe(1)
    expect(needsPerson(t)).toBe(0)
  })

  it('does NOT count a parked wait — a question nobody came for must not own the tab forever', () => {
    // 45 minutes: past the 2700 s parked threshold this screen already uses.
    const t = tally([
      A({ attention: 'input', input_wait_seconds: 2700 }),
      A({ attention: 'prompt', input_wait_seconds: 2700 }),
    ])
    expect(t.parked).toBe(2)
    expect(needsPerson(t)).toBe(0)
    expect(readyToRead(t)).toBe(0)
  })

  it('does NOT count work awaiting a human with no agent on it — a different fact', () => {
    const t = tally([{ name: 'p', agents: [], awaiting: { total: 4 } } as AttentionProject])
    expect(t.awaiting).toBe(4)
    expect(needsPerson(t)).toBe(0)
  })

  it('is zero on the empty tally, without touching unbucketed guards', () => {
    expect(needsPerson(EMPTY_TALLY)).toBe(0)
  })
})

describe('the question mark — an open question owns the tab', () => {
  it('a live question turns the tab into a red question mark, not the warning', () => {
    const t = tally([A({ state: 'asking', attention: 'prompt' })])
    expect(askingYou(t)).toBe(1)
    expect(tabTitle('SET', needsPerson(t), readyToRead(t), askingYou(t))).toBe('❓ SET (1)')
  })

  it('a permission prompt with no question stays the warning', () => {
    const t = tally([A({ state: 'waiting', attention: 'prompt' })])
    expect(askingYou(t)).toBe(0)
    expect(tabTitle('SET', needsPerson(t), readyToRead(t), askingYou(t))).toBe('⚠️ SET (1)')
  })

  it('the question wins over a permission prompt and a finished turn', () => {
    const t = tally([
      A({ state: 'asking', attention: 'prompt' }),
      A({ state: 'waiting', attention: 'prompt' }),
      A({ attention: 'input' }),
    ])
    expect(tabTitle('SET', needsPerson(t), readyToRead(t), askingYou(t))).toBe('❓ SET (1)')
  })

  it('a parked question does not hold the mark — the same 45 minutes as the Q marker', () => {
    const t = tally([A({ state: 'asking', attention: 'prompt', input_wait_seconds: 2700 })])
    expect(t.asking).toBe(1)
    expect(askingYou(t)).toBe(0)
    expect(tabTitle('SET', needsPerson(t), readyToRead(t), askingYou(t))).toBe('SET')
  })
})

describe('the title', () => {
  it('the question mark wins over the warning and the green', () => {
    expect(tabTitle('SET', 2, 3, 1)).toBe('❓ SET (1)')
  })
  it('carries the count in parentheses', () => {
    expect(tabTitle('SET', 2)).toBe('⚠️ SET (2)')
  })
  it('is the plain base at zero — never “SET (0)”', () => {
    expect(tabTitle('SET', 0)).toBe('SET')
  })
  it('turns green, with its count, when agents finished and nobody is blocked', () => {
    expect(tabTitle('SET', 0, 3)).toBe('🟢 SET (3)')
  })
  it('the warning wins over the green — a person needed outranks a result available', () => {
    expect(tabTitle('SET', 1, 5)).toBe('⚠️ SET (1)')
  })
  it('green at zero ready is still plain', () => {
    expect(tabTitle('SET', 0, 0)).toBe('SET')
  })
})

describe('the per-browser preference', () => {
  it('defaults ON — the person who asked should not hunt for a setting', () => {
    expect(loadTabBadge(fakeStorage())).toBe(true)
    expect(loadTabBadge(fakeStorage({ [TAB_BADGE_KEY]: 'on' }))).toBe(true)
  })

  it('reads this browser’s OFF and survives a throwing storage as ON', () => {
    expect(loadTabBadge(fakeStorage({ [TAB_BADGE_KEY]: 'off' }))).toBe(false)
    expect(loadTabBadge(fakeStorage({}, true))).toBe(true)
    expect(loadTabBadge(null)).toBe(true)
  })

  it('saves, and a throwing storage leaves the toggle working anyway', () => {
    const s = fakeStorage()
    saveTabBadge(false, s)
    expect(s.getItem(TAB_BADGE_KEY)).toBe('off')
    expect(() => saveTabBadge(true, fakeStorage({}, true))).not.toThrow()
  })
})
