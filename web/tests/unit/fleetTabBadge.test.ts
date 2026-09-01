/**
 * The browser tab badge — asked 2026-09-01: `SET (N)` in the tab while an
 * agent needs a person, per-reader because "just for me".
 *
 * The count is the screen's own "needs a person" classes, never a new
 * measurement; the preference is per-browser storage with a guarded read,
 * because a badge setting must never be able to take the screen down.
 */
import { describe, expect, it } from 'vitest'
import { needsPerson, tabTitle, loadTabBadge, saveTabBadge, TAB_BADGE_KEY } from '../../src/lib/fleetTabBadge'
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

describe('the count — the screen’s own needs-a-person classes', () => {
  it('counts input, prompt and background — the three classes the row colours already mean', () => {
    const t = tally([
      A({ attention: 'input' }),
      A({ attention: 'prompt' }),
      A({ attention: 'background' }),
      A({ attention: 'working' }),
      A({ attention: 'unmeasured' }),
    ])
    // 3, not 4: `tally` counts a background waiter inside `input` as well, so
    // summing all three counters would double every background agent.
    expect(needsPerson(t)).toBe(3)
  })

  it('never double-counts a background waiter standing alone', () => {
    const t = tally([A({ attention: 'background' })])
    expect(t.background).toBe(1)
    expect(t.input).toBe(1)
    expect(needsPerson(t)).toBe(1)
  })

  it('does NOT count a parked wait — a question nobody came for must not own the tab forever', () => {
    // 45 minutes: past the 2700 s parked threshold this screen already uses.
    const t = tally([A({ attention: 'input', input_wait_seconds: 2700 })])
    expect(t.parked).toBe(1)
    expect(needsPerson(t)).toBe(0)
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

describe('the title', () => {
  it('carries the count in parentheses', () => {
    expect(tabTitle('SET', 2)).toBe('SET (2)')
  })
  it('is the plain base at zero — never “SET (0)”', () => {
    expect(tabTitle('SET', 0)).toBe('SET')
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
