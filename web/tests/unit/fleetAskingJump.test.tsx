/**
 * The header's jump-to-asking control (B-185).
 *
 * Rendering the whole Fleet page with a stubbed fetch is the same harness
 * `fleetAgentTree.test.tsx` proves out, because the control's guarantees are
 * RELATIONAL: it exists only while some agent is asking, a click switches the
 * view to THAT agent (through `goTo`, which owns project selection and latest
 * mode), and a further click cycles to the next asking agent. Asked for
 * 2026-11-19: "kapcsoljon át arra, ami kérdésre vár… amikor a gép előtt vagyok".
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

const agent = (pid: number, over: Json = {}): Json => ({
  pid, name: `a${pid}`, project: null, branch: 'main', session_id: `s${pid}`,
  binding_confirmed: true, sources: ['process'], kind: 'interactive', state: 'quiet',
  tool: null, tool_elapsed_seconds: null, other_tools: [],
  last_movement_seconds: 5, unknown_reason: null,
  ...over,
})

const stage = (position: string, over: Json = {}): Json => ({
  state: 'resolved', flow: ['proposal', 'design', 'apply', 'verify', 'archive'],
  position, reason: null, source: 'derived', outside: false,
  ...over,
})

const project = (name: string, agents: Json[] = []): Json => ({
  name, root: `/r/${name}`, sources: ['process'], archived: false, agents,
})

const asking = (pid: number): Json => agent(pid, {
  state: 'asking', tool: 'AskUserQuestion', tool_elapsed_seconds: 30,
})

const body = (agents: Json[]): Json => ({
  agents: agents.length, working: 0, unknown: 0, waiting: 0,
  quiet: agents.filter(a => a.state === 'quiet').length,
  projects: [project('alpha', agents)],
  quiet_means: 'no outstanding tool call',
})

const LAYOUT: Json = {
  version: 3,
  groups: [{ id: 'g-open', name: 'open', collapsed: false, projects: ['alpha'], missing: [] }],
  parked: [], parked_order: [], ungrouped: [], missing: [],
}

function install(body_: Json) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(LAYOUT) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [] }) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body_) } as Response)
  }))
}

beforeEach(() => { try { localStorage.clear() } catch { /* no storage */ } })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

const wait = (cb: () => void) => waitFor(cb, { timeout: 4000 })

const ready = async (c: HTMLElement) =>
  waitFor(() => {
    const el = c.querySelector('[data-fleet-group="g-open"]')
    expect(el).toBeTruthy()
    return el as HTMLElement
  })

const activeTab = (c: HTMLElement): string | null =>
  c.querySelector('[data-fleet-agent-tab-active="on"]')?.getAttribute('data-fleet-agent-tab') ?? null

describe('the jump-to-asking control', () => {
  it('does not exist while nobody asks — a control that goes nowhere is forbidden', async () => {
    install(body([agent(1), agent(2)]))
    const { container } = render(<Fleet />)
    await ready(container)
    expect(container.querySelector('[data-fleet-asking-jump]')).toBeNull()
  })

  it('appears with the asking agent\'s count, and one click switches to it', async () => {
    install(body([asking(1), agent(2)]))
    const { container } = render(<Fleet />)
    await ready(container)
    const jump = await wait(() => {
      const el = container.querySelector('[data-fleet-asking-jump]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(jump.getAttribute('data-fleet-asking-jump')).toBe('1')
    // Nothing is enlarged before the click — discovery picks no favourite.
    expect(activeTab(container)).toBeNull()
    fireEvent.click(jump)
    await wait(() => {
      // The enlarged agent is the ASKING one — pid 1 here, and the tab strip
      // marks it active, which is the view switch the user asked for.
      expect(activeTab(container)).toBe('1')
    })
  })

  it('cycles to the NEXT asking agent on the second click, not back to the first', async () => {
    install(body([asking(1), asking(2)]))
    const { container } = render(<Fleet />)
    await ready(container)
    const jump = await wait(() => {
      const el = container.querySelector('[data-fleet-asking-jump]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(jump.getAttribute('data-fleet-asking-jump')).toBe('2')
    fireEvent.click(jump)
    await wait(() => expect(activeTab(container)).toBe('1'))
    fireEvent.click(jump)
    await wait(() => expect(activeTab(container)).toBe('2'))
  })
})
