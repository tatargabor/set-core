/**
 * The usage strip on the screen — the things no test of the RULE can see.
 *
 * The strip rests COMPACT: bars for the working accounts, and an icon-and-count
 * for each state that has no bar. So every assertion below is made twice where
 * it matters — once on the resting header, once on the opened detail — because
 * a mark that only survives in one of them is a mark the reader will miss in the
 * other.
 *
 *  - the header must render when the usage read fails or never returns. This is
 *    the whole reason the strip fetches its own data, and it is invisible to a
 *    renderer test.
 *  - collapsing must not take a critical account with it. Any layout that hides
 *    something creates a place a broken thing can sit while the screen looks
 *    calm.
 *  - no consumption mark may appear on an agent tab or tile. Per-seat
 *    attribution is not measurable — 4 of 40 transcripts carry an owning
 *    account — so a mark there would be a claim the data cannot support.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import FleetUsageStrip from '../../src/components/FleetUsageStrip'
import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function usageWindow(over: Json = {}): Json {
  return {
    group: 'session',
    kind: 'session',
    utilization: 18,
    resets_at: new Date(Date.now() + 3_600_000).toISOString(),
    severity: 'normal',
    scope: null,
    window_seconds: 5 * 3600,
    ...over,
  }
}

function usageAccount(over: Json = {}): Json {
  return {
    name: 'alpha@example.invalid',
    kind: 'web',
    outcome: 'measured',
    active: false,
    windows: [usageWindow()],
    ...over,
  }
}

function snapshot(over: Json = {}): Json {
  return {
    accounts: [usageAccount()],
    measured_at: new Date().toISOString(),
    interval_seconds: 60,
    last_error: null,
    ...over,
  }
}

/** A fleet answer with one project and one agent — enough to draw tabs and tiles. */
const FLEET = {
  agents: 1,
  working: 0,
  unknown: 0,
  projects: [{
    name: 'demo',
    root: '/home/x/demo',
    sources: ['process'],
    archived: false,
    agents: [{
      pid: 1, name: 'demo-a', terminal_label: 'demo-a', project: 'demo', branch: 'main',
      session_id: 's-1', binding_confirmed: true, sources: ['process'], kind: 'interactive',
      state: 'quiet', tool: null, tool_elapsed_seconds: null, other_tools: [],
      last_movement_seconds: 12, unknown_reason: null,
    }],
  }],
}

function installFetch(usage: Json | 'fail' | 'never') {
  const stub = vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/usage/accounts')) {
      if (usage === 'fail') return Promise.reject(new Error('network down'))
      if (usage === 'never') return new Promise(() => {}) as Promise<Response>
      return Promise.resolve({ ok: true, json: () => Promise.resolve(usage) } as Response)
    }
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ version: 1, groups: [], parked: [], ungrouped: [], missing: [], agent_order: {} }),
      } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({
        ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }),
      } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(FLEET) } as Response)
  })
  vi.stubGlobal('fetch', stub)
  return stub
}

beforeEach(() => { vi.useRealTimers() })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('the strip on screen', () => {
  it('draws one wordless mark per WORKING account while compact', async () => {
    installFetch(snapshot({
      accounts: [usageAccount(), usageAccount({ name: 'beta@example.invalid' })],
    }))
    const { container } = render(<FleetUsageStrip />)

    await waitFor(() => {
      expect(container.querySelectorAll('[data-fleet-usage-compact]').length).toBe(2)
    })
    // No name, no percentage, no sentence — the request was bars only.
    expect(container.textContent).not.toContain('alpha@example.invalid')
    // But the subject is still recoverable, on the tooltip.
    expect(container.querySelector('[data-fleet-usage-compact]')!.getAttribute('title'))
      .toContain('alpha@example.invalid')
  })

  it('names every account once opened', async () => {
    installFetch(snapshot({
      accounts: [usageAccount(), usageAccount({ name: 'beta@example.invalid' })],
    }))
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-toggle]')).toBeTruthy())

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    expect(container.querySelectorAll('[data-fleet-usage-account]').length).toBe(2)
    expect(container.textContent).toContain('beta@example.invalid')
  })

  it('draws both stripes of a measured window', async () => {
    installFetch(snapshot({
      accounts: [usageAccount({ windows: [usageWindow({ utilization: 60 })] })],
    }))
    const { container } = render(<FleetUsageStrip />)

    await waitFor(() => {
      const window = container.querySelector('[data-fleet-usage-window="measured"]')!
      expect(window.getAttribute('data-fleet-usage-consumed')).toBe('0.600')
      expect(window.getAttribute('data-fleet-usage-elapsed')).not.toBe('unknown')
    })
  })

  it('marks a null window instead of drawing it at zero, compact AND opened', async () => {
    installFetch(snapshot({
      accounts: [usageAccount({
        outcome: 'unmeasured',
        windows: [usageWindow({ utilization: null, severity: null })],
      })],
    }))
    const { container } = render(<FleetUsageStrip />)

    // Compact: a count, and no bar anywhere — an empty bar would read as
    // "nothing consumed", which is the opposite of what is known.
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-usage-unmeasured-count]')?.getAttribute(
        'data-fleet-usage-unmeasured-count')).toBe('1')
    })
    expect(container.querySelector('[data-fleet-usage-window="measured"]')).toBeNull()
    expect(container.querySelector('[data-fleet-usage-compact]')).toBeNull()

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    expect(container.querySelector('[data-fleet-usage-window="unmeasured"]')).toBeTruthy()
    expect(container.querySelector('[data-fleet-usage-window="measured"]')).toBeNull()
  })

  it('says an account did not answer, distinguishably from one with no figures', async () => {
    installFetch(snapshot({
      accounts: [
        usageAccount({ outcome: 'unreachable', windows: [] }),
        usageAccount({ name: 'beta@example.invalid', outcome: 'unmeasured',
                       windows: [usageWindow({ utilization: null })] }),
      ],
    }))
    const { container } = render(<FleetUsageStrip />)

    // Two causes, two marks. Folded into one number the reader cannot tell an
    // expired credential from a service that answered nothing.
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-usage-silent]')?.getAttribute(
        'data-fleet-usage-silent')).toBe('1')
    })
    expect(container.querySelector('[data-fleet-usage-unmeasured-count]')?.getAttribute(
      'data-fleet-usage-unmeasured-count')).toBe('1')

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    const states = Array.from(container.querySelectorAll('[data-fleet-usage-state]'))
      .map(el => el.getAttribute('data-fleet-usage-state'))
    expect(states).toEqual(['unmeasured'])
  })

  it('names one cause once, however many accounts share it', async () => {
    // Measured on the built screen 2026-08-27: three expired credentials drew
    // three identical sentences, three rows deep, on the landing screen. That is
    // the same defect the header's owner chip already carries a note about.
    installFetch(snapshot({
      accounts: [
        usageAccount({ name: 'a@example.invalid', outcome: 'unreachable', windows: [] }),
        usageAccount({ name: 'b@example.invalid', outcome: 'unreachable', windows: [] }),
        usageAccount({ name: 'c@example.invalid', outcome: 'unreachable', windows: [] }),
      ],
    }))
    const { container } = render(<FleetUsageStrip />)

    await waitFor(() => {
      expect(container.querySelector('[data-fleet-usage-silent]')?.getAttribute(
        'data-fleet-usage-silent')).toBe('3')
    })
    expect(container.querySelectorAll('[data-fleet-usage-compact]').length).toBe(0)

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    // Every name is still reachable — on the tooltip, not as three rows.
    const line = container.querySelector('[data-fleet-usage-detail] [data-fleet-usage-silent]')!
    for (const name of ['a@example.invalid', 'b@example.invalid', 'c@example.invalid']) {
      expect(line.getAttribute('title')).toContain(name)
    }
    expect(container.querySelectorAll('[data-fleet-usage-account]').length).toBe(0)
  })

  it('says no account is configured rather than drawing empty rows', async () => {
    installFetch(snapshot({ accounts: [] }))
    const { container } = render(<FleetUsageStrip />)

    await waitFor(() => {
      expect(container.querySelector('[data-fleet-usage="no-accounts"]')).toBeTruthy()
    })
  })
})

describe('collapsing', () => {
  const critical = snapshot({
    accounts: [usageAccount({
      windows: [usageWindow(), usageWindow({ group: 'weekly', utilization: 96, severity: 'critical' })],
    })],
  })

  it('shows the critical count in the RESTING state, where the detail is hidden', async () => {
    installFetch(critical)
    const { container } = render(<FleetUsageStrip />)

    await waitFor(() => {
      expect(container.querySelector('[data-fleet-usage-open="collapsed"]')).toBeTruthy()
    })
    // The detail is not on screen, and the failure is.
    expect(container.querySelector('[data-fleet-usage-account]')).toBeNull()
    expect(container.querySelector('[data-fleet-usage-critical-count]')?.textContent).toContain('1')
  })

  it('keeps the critical count when the detail is opened and closed again', async () => {
    installFetch(critical)
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-toggle]')).toBeTruthy())

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)
    expect(container.querySelector('[data-fleet-usage-critical-count]')).toBeTruthy()

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)
    expect(container.querySelector('[data-fleet-usage-open="collapsed"]')).toBeTruthy()
    expect(container.querySelector('[data-fleet-usage-critical-count]')?.textContent).toContain('1')
  })

  it('shows no critical mark when nothing is critical', async () => {
    installFetch(snapshot())
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-toggle]')).toBeTruthy())

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    expect(container.querySelector('[data-fleet-usage-critical-count]')).toBeNull()
  })

  it('spends the critical colour on nothing else, in either state', async () => {
    installFetch(snapshot())
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-compact]')).toBeTruthy())

    const reds = () => Array.from(container.querySelectorAll('*')).filter(el =>
      /(^|\s)(bg|text|border)-red-/.test(el.className?.toString?.() ?? ''))
    expect(reds()).toEqual([])

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)
    expect(reds()).toEqual([])
  })
})

describe('the header does not wait for this', () => {
  it('renders the fleet screen when the usage read fails', async () => {
    installFetch('fail')
    const { container } = render(<Fleet />)

    // The tiles are what the screen is FOR — waiting on the phase alone would
    // pass on a screen that answered and then rendered nothing below it.
    await waitFor(() => expect(container.querySelector('[data-fleet-tile-head]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-usage="unavailable"]')).toBeTruthy()
  })

  it('renders the fleet screen while the usage read never returns', async () => {
    installFetch('never')
    const { container } = render(<Fleet />)

    await waitFor(() => expect(container.querySelector('[data-fleet-tile-head]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-usage="unavailable"]')).toBeTruthy()
  })

  it('puts no consumption mark on any agent tab or tile', async () => {
    installFetch(snapshot())
    const { container } = render(<Fleet />)

    await waitFor(() => expect(container.querySelector('[data-fleet-tile-head]')).toBeTruthy())

    const strip = container.querySelector('[data-fleet-usage]')
    const marks = Array.from(container.querySelectorAll('[data-fleet-usage-window]'))
    expect(marks.length).toBeGreaterThan(0)
    for (const mark of marks) expect(strip!.contains(mark)).toBe(true)
  })
})
