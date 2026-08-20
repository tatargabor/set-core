/**
 * The toggle: it is a way of LOOKING at the fleet, not a way of operating it.
 *
 * A control that also acted on agents is one nobody dares press to find out
 * what it does, so the load-bearing assertion here is a negative — that no
 * request touching an agent's lifecycle is made when the mode is turned on.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

const agent = (pid: number, extra: Json = {}): Json => ({
  pid, name: `a${pid}`, project: 'p', branch: 'main', session_id: `s${pid}`,
  binding_confirmed: true, sources: ['process'], kind: 'interactive', state: 'quiet',
  tool: null, tool_elapsed_seconds: null, other_tools: [], last_movement_seconds: 5,
  unknown_reason: null, waiting_for: null, declaration_ignored: null,
  population: 'foreign', terminal_label: null, ...extra,
})

const body: Json = {
  agents: 1, working: 0, unknown: 0, waiting: 0, asking: 0, quiet: 1, unbucketed: 0,
  projects: [{ name: 'p', root: '/r/p', sources: ['process'], archived: false, agents: [agent(1)] }],
  quiet_means: 'no outstanding tool call',
}

// `enabled: false` on purpose. The page now READS the server's state on
// mount — added after the running screen showed "PM mode off" while the
// server was enabled and quietly running cycles — so a snapshot saying
// `true` here would start the test with the overlay already open and
// invert what the click does.
const pmSnapshot: Json = {
  enabled: false, presented: null, queued: [],
  counts: { queued: 0, idle: 1, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: true, judgment_reason: null, counted: true },
  can_go_back: false, can_go_forward: false, pending_switch: null, last_cycle: 1, last_error: null, cycling: false,
}

let calls: string[] = []

function install() {
  calls = []
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    calls.push(`${init?.method ?? 'GET'} ${u}`)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({
        version: 1, groups: [], parked: [], parked_missing: [], parked_order: [], ungrouped: ['p'], missing: [],
      }) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [] }) } as Response)
    }
    if (u.includes('/api/fleet/owner')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ available: true, held: 0 }) } as Response)
    }
    if (u.includes('/api/fleet/pm')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(pmSnapshot) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  }))
}

beforeEach(() => { install(); try { localStorage.clear() } catch { /* no storage */ } })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('PM mode is a toggle and it changes nothing about the agents', () => {
  it('turning it on instructs nobody and starts or stops nothing', async () => {
    const { container } = render(<Fleet />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-toggle]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-pm-toggle]')!)
    await waitFor(() => expect(calls.some(c => c === 'POST /api/fleet/pm')).toBe(true))

    const touching = calls.filter(c =>
      /POST \/api\/fleet\/agents/.test(c) || /\/stop\b/.test(c) || /\/instruct\b/.test(c) || /POST \/api\/fleet\/units/.test(c))
    expect(touching).toEqual([])
  })

  it('shows the overlay while on and removes it when off, leaving the screen underneath', async () => {
    const { container } = render(<Fleet />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-toggle]')).toBeTruthy())

    fireEvent.click(container.querySelector('[data-fleet-pm-toggle]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm="on"]')).toBeTruthy())
    expect((container.querySelector('[data-fleet-pm-toggle]') as HTMLElement)
      .getAttribute('data-fleet-pm-toggle')).toBe('on')

    fireEvent.click(container.querySelector('[data-fleet-pm-toggle]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm="on"]')).toBeNull())
    // The arrangement was never unmounted — leaving the mode is a state
    // change, not a rebuild.
    expect(container.querySelector('[data-fleet-phase]')).toBeTruthy()
  })
})
