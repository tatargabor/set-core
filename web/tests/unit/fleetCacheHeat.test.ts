/**
 * What a tab draws about its cache, and what it draws when nobody measured one.
 *
 * The absent case is the one worth testing hardest. A seat with no transcript
 * rendered as cold tells the reader to avoid a tab for a cost nobody computed;
 * rendered as live it invites a bill nobody predicted. Both look fine on screen.
 */
import { describe, expect, it } from 'vitest'

import { GROUP_SEPARATOR, mark, money, thicknessFor, tokens, type CacheState } from '../../src/lib/fleetCacheHeat'

/** `141\u202f403` — written with the separator the module actually uses, rather
 *  than with whatever a locale happens to produce. */
const grouped = (n: number) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, GROUP_SEPARATOR)

function state(over: Partial<CacheState> = {}): CacheState {
  return {
    started_at: '2026-08-27T12:00:00+00:00',
    tokens: 141_403,
    ttl_seconds: 3600,
    model: 'claude-opus-5',
    rewrite_usd: 1.414,
    seconds_remaining: 1800,
    cooled: 0.5,
    cold: false,
    ...over,
  }
}

describe('the bar fills with the cooling', () => {
  it('is empty on a freshly used seat', () => {
    const m = mark(state({ cooled: 0, seconds_remaining: 3600 }))
    expect(m.kind).toBe('live')
    if (m.kind === 'unmeasured') throw new Error('unreachable')
    expect(m.fill).toBe(0)
  })

  it('is drawn to the cooled fraction partway through', () => {
    const m = mark(state({ cooled: 0.5 }))
    if (m.kind === 'unmeasured') throw new Error('unreachable')
    expect(m.fill).toBeCloseTo(0.5)
  })

  it('STAYS fully drawn once cold, rather than disappearing', () => {
    // The countdown design vanished exactly when the tab became expensive,
    // leaving a cold seat looking identical to an unmeasured one.
    const m = mark(state({ cooled: 1, cold: true, seconds_remaining: 0 }))
    if (m.kind === 'unmeasured') throw new Error('unreachable')
    expect(m.kind).toBe('cold')
    expect(m.fill).toBe(1)
  })

  it('clamps a fraction outside 0..1 rather than drawing past the tab', () => {
    const over = mark(state({ cooled: 1.4 }))
    const under = mark(state({ cooled: -0.2 }))
    if (over.kind === 'unmeasured' || under.kind === 'unmeasured') throw new Error('unreachable')
    expect(over.fill).toBe(1)
    expect(under.fill).toBe(0)
  })

  it('crosses three colour bands as it cools', () => {
    const hue = (c: number) => {
      const m = mark(state({ cooled: c }))
      if (m.kind === 'unmeasured') throw new Error('unreachable')
      return m.colour
    }
    expect(hue(0.1)).toContain('emerald')
    expect(hue(0.6)).toContain('amber')
    expect(hue(0.9)).toContain('red')
  })
})

describe('thickness carries the stake', () => {
  it('draws a bigger cache thicker at the same age', () => {
    const small = mark(state({ tokens: 15_044 }))
    const large = mark(state({ tokens: 195_889 }))
    if (small.kind === 'unmeasured' || large.kind === 'unmeasured') throw new Error('unreachable')
    expect(large.thickness).toBeGreaterThan(small.thickness)
  })

  it('stays within its range for an enormous cache', () => {
    const huge = mark(state({ tokens: 5_000_000 }))
    const tiny = mark(state({ tokens: 1 }))
    if (huge.kind === 'unmeasured' || tiny.kind === 'unmeasured') throw new Error('unreachable')
    expect(huge.thickness).toBe(5)
    expect(tiny.thickness).toBe(1)
  })

  it('is independent of the cooling — the two channels do not interfere', () => {
    const fresh = mark(state({ tokens: 195_889, cooled: 0 }))
    const cold = mark(state({ tokens: 195_889, cooled: 1, cold: true }))
    if (fresh.kind === 'unmeasured' || cold.kind === 'unmeasured') throw new Error('unreachable')
    expect(cold.thickness).toBe(fresh.thickness)
  })
})

describe('the cold marks cannot disagree', () => {
  it('a cold seat is full, red-banded AND priced, together', () => {
    const m = mark(state({ cooled: 1, cold: true, seconds_remaining: 0, rewrite_usd: 1.96 }))
    if (m.kind === 'unmeasured') throw new Error('unreachable')
    expect(m.kind).toBe('cold')
    expect(m.fill).toBe(1)
    expect(m.colour).toContain('red')
    expect(m.price).toBe('$1.96')
  })

  it('a live seat shows no price, whatever its colour band', () => {
    for (const cooled of [0, 0.4, 0.6, 0.9, 0.999]) {
      const m = mark(state({ cooled, cold: false }))
      if (m.kind === 'unmeasured') throw new Error('unreachable')
      expect(m.kind).toBe('live')
      expect(m.price).toBeNull()
    }
  })

  it('takes `cold` from the server rather than re-deriving it from the fraction', () => {
    // The clock is the server's. A tab computing its own expiry could disagree
    // with the ordering PM mode does from the same record — so the flag wins
    // even when the fraction alone would say otherwise.
    const m = mark(state({ cooled: 0.99, cold: true }))
    if (m.kind === 'unmeasured') throw new Error('unreachable')
    expect(m.kind).toBe('cold')
    expect(m.fill).toBe(1)
  })
})

describe('an unpriced model', () => {
  it('says so in the tooltip and shows no invented figure', () => {
    const m = mark(state({ model: 'claude-nonesuch-9', rewrite_usd: null, cold: true, cooled: 1 }))
    if (m.kind === 'unmeasured') throw new Error('unreachable')
    expect(m.price).toBeNull()
    expect(m.title).toContain('not priced')
    // The size still reaches the reader — it is what is left to judge by.
    expect(m.title).toContain(grouped(141403))
  })
})

describe('a seat nothing was measured on', () => {
  it('is unmeasured, not cold and not live', () => {
    expect(mark(undefined).kind).toBe('unmeasured')
    expect(mark(null).kind).toBe('unmeasured')
  })

  it('carries no bar, no thickness and no price to render', () => {
    const m = mark(undefined)
    expect(m).toEqual({ kind: 'unmeasured' })
  })
})

describe('the figures a reader acts on', () => {
  it('states the remaining time and the cost while live', () => {
    const m = mark(state({ seconds_remaining: 480, rewrite_usd: 1.96 }))
    if (m.kind === 'unmeasured') throw new Error('unreachable')
    expect(m.title).toContain('8m')
    expect(m.title).toContain('$1.96')
    expect(m.title).toContain(grouped(141403))
  })

  it('states hours for a long lifetime rather than a three-digit minute count', () => {
    const m = mark(state({ seconds_remaining: 5400 }))
    if (m.kind === 'unmeasured') throw new Error('unreachable')
    expect(m.title).toContain('1h 30m')
  })

  it('formats a sub-dollar price without a leading zero, to fit a tab', () => {
    expect(money(0.15)).toBe('$.15')
    expect(money(1.96)).toBe('$1.96')
    expect(money(12.5)).toBe('$12.50')
  })

  /**
   * Measured on the running dashboard 2026-08-27: a seat holding 99 685 tokens
   * priced at $0.9969 rendered as `$.00`. The leading zero was stripped from a
   * string that no longer had one — the branch asked the raw value, the slice
   * cut the rounded one, and they disagree exactly on [0.995, 1).
   *
   * The fail direction is what makes it worth a test rather than a tidy-up: a
   * dollar of stake reads as nothing, on a screen whose whole job is to say how
   * much money a cold cache costs.
   */
  it('does not eat the leading digit of a price that rounds up to a dollar', () => {
    expect(money(0.9969)).toBe('$1.00')
    expect(money(0.996)).toBe('$1.00')
    // The neighbours either side must keep behaving.
    expect(money(0.994)).toBe('$.99')
    expect(money(0.999999)).toBe('$1.00')
    // Not asserted: 0.995. Its binary representation sits just BELOW the
    // decimal it is written as, so `toFixed(2)` yields '0.99' — a fact about
    // IEEE-754, not about this formatter.
  })

  it('groups token counts so the eye reads a magnitude', () => {
    expect(tokens(195_889)).toBe(`195${GROUP_SEPARATOR}889`)
    expect(tokens(1_044)).toBe(`1${GROUP_SEPARATOR}044`)
    // Under a thousand: no separator at all.
    expect(tokens(999)).toBe('999')
  })
})


describe('the thickness scale against sizes this repo actually produces', () => {
  /**
   * The linear scale this replaced passed every test above and was DEAD on the
   * screen: measured 2026-08-27, all fourteen live sessions held between 15 044
   * and 554 959 tokens, and every one of them rendered at maximum thickness
   * because the ceiling was 200 000.
   *
   * The tests could not see it because they compared 15k against 195k — a range
   * no seat on this machine occupies. So this one asserts the SPREAD across the
   * measured sizes, which is the property the mark exists for.
   */
  const MEASURED = [15_044, 83_451, 99_685, 190_994, 205_822, 287_204,
                    314_443, 387_987, 462_275, 554_959]

  it('gives the real fleet more than one thickness', () => {
    const spread = new Set(MEASURED.map(thicknessFor))
    expect(spread.size).toBeGreaterThanOrEqual(4)
  })

  it('never collapses every seat onto the maximum', () => {
    // The exact failure of the linear version.
    expect(MEASURED.every(t => thicknessFor(t) === 5)).toBe(false)
  })

  it('is monotonic — a bigger cache is never drawn thinner', () => {
    for (let i = 1; i < MEASURED.length; i++) {
      expect(thicknessFor(MEASURED[i])).toBeGreaterThanOrEqual(thicknessFor(MEASURED[i - 1]))
    }
  })

  it('clamps at both ends rather than leaving the bar invisible or huge', () => {
    expect(thicknessFor(0)).toBe(1)
    expect(thicknessFor(1)).toBe(1)
    expect(thicknessFor(50_000_000)).toBe(5)
  })
})
