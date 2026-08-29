/**
 * What the header's usage strip draws — and what it draws when it knows nothing.
 *
 * Three of these tests exist because the three not-a-number states look
 * identical once drawn as an empty bar: no account configured, an account that
 * did not answer, and an account that answered with no figures. Only the last
 * one was measured live (2026-08-27, one of three accounts, `200` with both
 * windows null), and it is the one that would read as "nothing consumed".
 */
import { describe, expect, it } from 'vitest'

import {
  criticalCount,
  elapsedFraction,
  shortLabel,
  markWindow,
  stripState,
  toneFor,
  type UsageAccount,
  type UsageSnapshot,
  type UsageWindow,
} from '../../src/lib/fleetUsageBars'

const NOW = Date.parse('2026-08-27T18:00:00+00:00')

function window(over: Partial<UsageWindow> = {}): UsageWindow {
  return {
    group: 'session',
    kind: 'session',
    utilization: 18,
    // One hour left of a five-hour window: 80 % of it has run.
    resets_at: '2026-08-27T19:00:00+00:00',
    severity: 'normal',
    scope: null,
    window_seconds: 5 * 3600,
    ...over,
  }
}

function account(over: Partial<UsageAccount> = {}): UsageAccount {
  return {
    name: 'alpha@example.invalid',
    kind: 'web',
    outcome: 'measured',
    active: false,
    windows: [window()],
    ...over,
  }
}

function snapshot(over: Partial<UsageSnapshot> = {}): UsageSnapshot {
  return {
    accounts: [account()],
    measured_at: '2026-08-27T17:59:30+00:00',
    interval_seconds: 60,
    last_error: null,
    ...over,
  }
}

describe('the two stripes', () => {
  it('draws consumption and elapsed time as separate fractions', () => {
    const mark = markWindow(window({ utilization: 60 }), NOW)

    expect(mark.kind).toBe('measured')
    if (mark.kind !== 'measured') return
    expect(mark.consumed).toBeCloseTo(0.6)
    expect(mark.elapsed).toBeCloseTo(0.8)
  })

  it('reads consumption as AHEAD of the window when it outruns the elapsed share', () => {
    const ahead = markWindow(window({ utilization: 95 }), NOW)
    const behind = markWindow(window({ utilization: 20 }), NOW)

    if (ahead.kind !== 'measured' || behind.kind !== 'measured') throw new Error('measured')
    expect(ahead.consumed).toBeGreaterThan(ahead.elapsed!)
    expect(behind.consumed).toBeLessThan(behind.elapsed!)
  })

  it('labels each window with the span it stands for', () => {
    expect(markWindow(window(), NOW).label).toBe('5h')
    expect(markWindow(window({ group: 'weekly' }), NOW).label).toBe('7d')
  })

  it('names the model on a scoped window, so it cannot be read as the account-wide one', () => {
    const scoped = markWindow(
      window({ group: 'weekly', kind: 'weekly_scoped', scope: { model: 'Fable', surface: null } }),
      NOW,
    )

    expect(scoped.label).toBe('7d (Fable)')
  })

  it('draws both windows of an account', () => {
    const state = stripState(
      snapshot({ accounts: [account({ windows: [window(), window({ group: 'weekly' })] })] }),
      NOW,
    )

    if (state.kind !== 'ready') throw new Error('ready')
    expect(state.rows[0].windows.map((w) => w.label)).toEqual(['5h', '7d'])
  })
})

describe('the elapsed stripe is not guessed', () => {
  it('is null when the reset time is missing', () => {
    expect(elapsedFraction(window({ resets_at: null }), NOW)).toBeNull()
  })

  it('is null when the reset time cannot be parsed', () => {
    expect(elapsedFraction(window({ resets_at: 'soon' }), NOW)).toBeNull()
  })

  it('falls back to the known window length when the server omits it', () => {
    expect(elapsedFraction(window({ window_seconds: null }), NOW)).toBeCloseTo(0.8)
  })

  it('clamps rather than reporting a window more than fully run', () => {
    expect(elapsedFraction(window({ resets_at: '2026-08-27T10:00:00+00:00' }), NOW)).toBe(1)
  })
})

describe('colour states the severity, and nothing else', () => {
  it('uses the critical colour when the service says critical', () => {
    const mark = markWindow(window({ utilization: 96, severity: 'critical' }), NOW)

    if (mark.kind !== 'measured') throw new Error('measured')
    expect(mark.tone).toBe('bg-red-400')
    expect(mark.critical).toBe(true)
  })

  it('never uses the critical colour on a normal window, however high the percentage', () => {
    const mark = markWindow(window({ utilization: 99, severity: 'normal' }), NOW)

    if (mark.kind !== 'measured') throw new Error('measured')
    expect(mark.tone).not.toBe('bg-red-400')
    expect(mark.critical).toBe(false)
  })

  it('does not band by percentage when the severity is absent', () => {
    expect(toneFor(null)).toBe(toneFor('normal'))
  })
})

describe('the three ways of knowing nothing stay apart', () => {
  it('marks a null window unmeasured rather than drawing it at zero', () => {
    const mark = markWindow(window({ utilization: null }), NOW)

    expect(mark.kind).toBe('unmeasured')
    expect(mark).not.toHaveProperty('consumed')
  })

  it('keeps a measured zero distinct from an unmeasured window', () => {
    const zero = markWindow(window({ utilization: 0 }), NOW)
    const absent = markWindow(window({ utilization: null }), NOW)

    expect(zero.kind).toBe('measured')
    expect(absent.kind).toBe('unmeasured')
  })

  it('says an unreachable account did not answer, and draws no window for it', () => {
    const state = stripState(
      snapshot({ accounts: [account({ outcome: 'unreachable', windows: [] })] }), NOW)

    if (state.kind !== 'ready') throw new Error('ready')
    expect(state.rows[0].windows).toEqual([])
    expect(state.rows[0].note).toMatch(/did not answer/)
  })

  it('says an account that answered with no figures is a different case', () => {
    const state = stripState(
      snapshot({
        accounts: [account({
          outcome: 'unmeasured',
          windows: [window({ utilization: null }), window({ group: 'weekly', utilization: null })],
        })],
      }),
      NOW,
    )

    if (state.kind !== 'ready') throw new Error('ready')
    expect(state.rows[0].note).toMatch(/carried no figures/)
    expect(state.rows[0].windows.every((w) => w.kind === 'unmeasured')).toBe(true)
  })

  it('says so when no account is configured, rather than rendering empty rows', () => {
    const state = stripState(snapshot({ accounts: [] }), NOW)

    expect(state.kind).toBe('no-accounts')
  })

  it('says so when nothing has been measured yet', () => {
    const state = stripState(snapshot({ measured_at: null }), NOW)

    expect(state.kind).toBe('unavailable')
  })

  it('renders as unavailable when there is no snapshot at all', () => {
    expect(stripState(null, NOW).kind).toBe('unavailable')
    expect(stripState(undefined, NOW).kind).toBe('unavailable')
  })

  it('carries the reason when the server named one', () => {
    const state = stripState(
      snapshot({ measured_at: null, last_error: 'poller-not-running' }), NOW)

    if (state.kind !== 'unavailable') throw new Error('unavailable')
    expect(state.note).toContain('poller-not-running')
  })
})

describe('age', () => {
  it('is not stale within one polling interval', () => {
    const state = stripState(snapshot(), NOW)

    if (state.kind !== 'ready') throw new Error('ready')
    expect(state.stale).toBe(false)
  })

  it('is stale once older than one interval, and still carries its figures', () => {
    const state = stripState(snapshot({ measured_at: '2026-08-27T17:50:00+00:00' }), NOW)

    if (state.kind !== 'ready') throw new Error('ready')
    expect(state.stale).toBe(true)
    expect(state.rows[0].windows[0].kind).toBe('measured')
    expect(state.measuredAt).toBe('2026-08-27T17:50:00+00:00')
  })

  it('measures staleness against the interval the SERVER reports', () => {
    const slow = stripState(
      snapshot({ measured_at: '2026-08-27T17:50:00+00:00', interval_seconds: 3600 }), NOW)

    if (slow.kind !== 'ready') throw new Error('ready')
    expect(slow.stale).toBe(false)
  })
})

describe('the collapsed strip', () => {
  it('counts a critical window so the mark can survive a collapse', () => {
    const state = snapshot({
      accounts: [
        account({ windows: [window(), window({ group: 'weekly', severity: 'critical' })] }),
        account({ name: 'beta@example.invalid' }),
      ],
    })

    expect(criticalCount(state)).toBe(1)
  })

  it('counts nothing when nothing is critical', () => {
    expect(criticalCount(snapshot())).toBe(0)
  })

  it('counts nothing when there is no snapshot', () => {
    expect(criticalCount(null)).toBe(0)
  })
})

describe('a GLM account beside the Claude accounts', () => {
  const glmWindow = (over: Partial<UsageWindow> = {}): UsageWindow => window({
    group: 'session', kind: 'CREDIT_LIMIT', ...over,
  })

  it('draws a GLM account as another row beside the Claude accounts', () => {
    const state = stripState(snapshot({
      accounts: [
        account(),
        account({ name: 'GLM', kind: 'glm', windows: [glmWindow()] }),
      ],
    }), NOW)

    if (state.kind !== 'ready') throw new Error('ready')
    expect(state.rows.map(r => `${r.kind}:${r.name}`)).toEqual([
      'web:alpha@example.invalid', 'glm:GLM',
    ])
    expect(state.measuredRows.length).toBe(2)
  })

  it('labels a window whose group is unknown by the span its seconds state', () => {
    // A window shape z.ai might add; the table has no name for it, so the
    // length the server reported becomes the label instead of a raw group.
    const mark = markWindow(glmWindow({ group: 'unit3x1', window_seconds: 3600 }), NOW)

    expect(mark.label.startsWith('1h')).toBe(true)
  })

  it('keeps the label on the table for the two known groups', () => {
    expect(markWindow(glmWindow()).label.startsWith('5h')).toBe(true)
    expect(markWindow(glmWindow({ group: 'weekly', window_seconds: 7 * 24 * 3600 }))
      .label.startsWith('7d')).toBe(true)
  })

  it('draws no elapsed stripe when the window length is unknown', () => {
    const mark = markWindow(glmWindow({ group: 'unit9x9', window_seconds: null }), NOW)

    if (mark.kind !== 'measured') throw new Error('measured')
    expect(mark.elapsed).toBeNull()
  })

  it('colours a GLM window by the severity the server reported', () => {
    // The banding happened at measurement (glm-usage-source); the screen's rule
    // is unchanged — take the severity the record carries, nothing else.
    expect(toneFor('critical')).toBe('bg-red-400')
    expect(markWindow(glmWindow({ severity: 'critical' })).kind === 'measured'
      && (markWindow(glmWindow({ severity: 'critical' })) as { tone?: string }).tone
        === 'bg-red-400').toBe(true)
  })

  it('counts a GLM critical window in the critical mark', () => {
    const state = snapshot({
      accounts: [account({
        name: 'GLM', kind: 'glm',
        windows: [glmWindow({ group: 'weekly', severity: 'critical' })],
      })],
    })

    expect(criticalCount(state)).toBe(1)
  })
})

describe('the compact label before the bars', () => {
  it('uses the domain label of an email, which is what distinguishes accounts', () => {
    expect(shortLabel('tatar.gabor@gmail.com')).toBe('gmail')
    expect(shortLabel('info@tgholsters.hu')).toBe('tgholsters')
    expect(shortLabel('tatar.gabor@itline.hu')).toBe('itline')
  })

  it('keeps a provider name as itself, capped', () => {
    expect(shortLabel('GLM')).toBe('GLM')
    expect(shortLabel('a-very-long-account-name')).toBe('a-very-long-')
  })

  it('falls back to the name when there is nothing after the at-sign', () => {
    expect(shortLabel('weird@')).toBe('weird@')
  })
})
