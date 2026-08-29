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

describe('the GLM account and the purge offer', () => {
  const threeAccounts = () => snapshot({
    accounts: [
      usageAccount({ name: 'alpha@example.invalid' }),
      usageAccount({
        name: 'GLM', kind: 'glm',
        windows: [
          usageWindow({ group: 'session', kind: 'CREDIT_LIMIT', window_seconds: 5 * 3600 }),
          usageWindow({ group: 'weekly', kind: 'CREDIT_LIMIT', window_seconds: 7 * 24 * 3600 }),
        ],
      }),
      usageAccount({ name: 'dead@example.invalid', outcome: 'unreachable', windows: [] }),
    ],
  })

  it('shows the GLM bars beside the Claude bars while compact', async () => {
    installFetch(threeAccounts())
    const { container } = render(<FleetUsageStrip />)

    await waitFor(() => {
      const compact = container.querySelectorAll('[data-fleet-usage-compact]')
      expect(compact.length).toBe(2)
      expect(compact[1].getAttribute('data-fleet-usage-compact')).toBe('GLM')
    })
  })

  it('names GLM as a provider row in the detail', async () => {
    installFetch(threeAccounts())
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-toggle]')).toBeTruthy())

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    const rows = container.querySelectorAll('[data-fleet-usage-account]')
    expect(rows.length).toBe(2)
    expect(rows[1].getAttribute('data-fleet-usage-account')).toBe('GLM')
    // The windows are labelled by their span, the way the Claude windows are.
    expect(rows[1].textContent).toContain('5h')
    expect(rows[1].textContent).toContain('7d')
  })

  it('does not describe the critical band as the service\'s', async () => {
    // With GLM behind the same strip, set-core bands one source itself, so the
    // old wording — "windows the service calls critical" — was true of one
    // source and false of the other.
    installFetch(snapshot({
      accounts: [usageAccount({
        windows: [usageWindow({ group: 'weekly', utilization: 96, severity: 'critical' })],
      })],
    }))
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-critical-count]')).toBeTruthy())

    const title = container.querySelector('[data-fleet-usage-critical-count]')!.getAttribute('title')!
    expect(title).not.toContain('service')
    expect(title).toContain('critical threshold')
  })

  it('offers the purge exactly where the unanswered accounts are counted', async () => {
    installFetch(threeAccounts())
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-silent]')).toBeTruthy())

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    expect(container.querySelector('[data-fleet-usage-purge]')).toBeTruthy()
  })

  it('offers no purge when every account answered', async () => {
    installFetch(snapshot())
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-compact]')).toBeTruthy())

    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    expect(container.querySelector('[data-fleet-usage-purge]')).toBeNull()
  })

  it('confirms by name before anything is deleted', async () => {
    installFetch(threeAccounts())
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-silent]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    fireEvent.click(container.querySelector('[data-fleet-usage-purge]')!)

    expect(confirm).toHaveBeenCalledTimes(1)
    const message = confirm.mock.calls[0][0] ?? ''
    expect(message).toContain('dead@example.invalid')
    expect(message).toContain('deleted')
    // Declined: no POST was issued.
    expect(vi.mocked(globalThis.fetch).mock.calls.some(([u]) => String(u).includes('/purge'))).toBe(false)
    confirm.mockRestore()
  })

  it('refreshes the strip right after a confirmed purge', async () => {
    const reads: string[] = []
    const stub = vi.fn((url: string, init?: RequestInit) => {
      const u = String(url)
      if (u.includes('/api/usage/accounts/purge')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ results: [], removed: 1, refused: 0 }),
        } as Response)
      }
      if (u.includes('/api/usage/accounts')) {
        reads.push(String((init as RequestInit | undefined)?.method ?? 'GET'))
        return Promise.resolve({ ok: true, json: () => Promise.resolve(threeAccounts()) } as Response)
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
    })
    vi.stubGlobal('fetch', stub)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-silent]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)
    const readsBefore = reads.length

    fireEvent.click(container.querySelector('[data-fleet-usage-purge]')!)

    await waitFor(() => expect(reads.length).toBeGreaterThan(readsBefore))
    expect(reads[reads.length - 1]).toBe('GET')
  })

  it('says what failed and keeps the state when the purge does not go through', async () => {
    const stub = vi.fn((url: string) => {
      const u = String(url)
      if (u.includes('/api/usage/accounts/purge')) {
        return Promise.reject(new Error('network down'))
      }
      if (u.includes('/api/usage/accounts')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(threeAccounts()) } as Response)
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
    })
    vi.stubGlobal('fetch', stub)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const { container } = render(<FleetUsageStrip />)
    await waitFor(() => expect(container.querySelector('[data-fleet-usage-silent]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-usage-toggle]')!)

    fireEvent.click(container.querySelector('[data-fleet-usage-purge]')!)

    await waitFor(() => expect(container.querySelector('[data-fleet-usage-purge-error]')).toBeTruthy())
    // The silent count is still on screen: a failed purge removed nothing.
    expect(container.querySelector('[data-fleet-usage-silent]')).toBeTruthy()
  })
})
