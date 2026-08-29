/**
 * The agent tree in the project column, on screen.
 *
 * Rendering the whole Fleet page with a stubbed fetch is deliberate — the
 * same harness `fleetColumnMode.test.tsx` proves out — because the tree's
 * guarantees are about RELATIONS a component-isolated test cannot see:
 * sub-rows hide with their project when the filter runs, a click focuses the
 * agent through the shell's own selection path, and the focus survives
 * leaving and returning because the shell remembers it per project.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

const FLOW = ['proposal', 'design', 'apply', 'verify', 'archive']

const agent = (pid: number, over: Json = {}): Json => ({
  pid, name: `a${pid}`, project: null, branch: 'main', session_id: `s${pid}`,
  binding_confirmed: true, sources: ['process'], kind: 'interactive', state: 'quiet',
  tool: null, tool_elapsed_seconds: null, other_tools: [],
  last_movement_seconds: 5, unknown_reason: null,
  ...over,
})

const stage = (position: string, over: Json = {}): Json => ({
  state: 'resolved', flow: FLOW, position, reason: null, source: 'derived', outside: false,
  ...over,
})

const project = (name: string, agents: Json[] = []): Json => ({
  name, root: `/r/${name}`, sources: ['process'], archived: false, agents,
})

const BODY: Json = {
  agents: 3, working: 0, unknown: 0, waiting: 0, quiet: 3,
  projects: [
    project('alpha', [
      agent(1, { stage: stage('apply') }),
      agent(2, { stage: stage('design'), cwd: '/r/alpha-wt-feat', branch: 'change/feat', project_root: '/r/alpha' }),
    ]),
    project('idle', [agent(3, { stage: stage(null, { state: 'gap', reason: 'nothing-started' }) })]),
    project('bare'),
  ],
  quiet_means: 'no outstanding tool call',
}

const LAYOUT = {
  version: 3,
  groups: [
    { id: 'g-open', name: 'open', collapsed: false, projects: ['alpha', 'idle', 'bare'], missing: [] },
  ],
  parked: [], parked_order: [], ungrouped: [], missing: [],
}

function install(body: Json = BODY) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(LAYOUT) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [] }) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  }))
}

beforeEach(() => { install(); try { localStorage.clear() } catch { /* no storage */ } })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

/**
 * waitFor with room to spare. The FULL suite runs its files in parallel, and
 * one flake at the default 1 s was measured under exactly that load (5/5 green
 * in isolation, then a timeout in the run). The assertions are unchanged; this
 * only says they may take a few seconds on a busy machine.
 */
const wait = (cb: () => void) => waitFor(cb, { timeout: 4000 })

const ready = async (c: HTMLElement) =>
  waitFor(() => {
    const el = c.querySelector('[data-fleet-group="g-open"]')
    expect(el).toBeTruthy()
    return el as HTMLElement
  })

describe('the tree', () => {
  it('shows the selected project\'s agents as indented sub-rows, with their stages', async () => {
    const { container } = render(<Fleet />)
    await ready(container)
    // Sub-rows are ALWAYS visible (the user's rule — no selection needed).
    // They render with the first payload, so wait rather than assert racing.
    const rows = await wait(() => {
      const els = container.querySelectorAll('[data-fleet-agent-rows="alpha"] [data-fleet-agent-row]')
      expect(els.length).toBe(2)
      return els
    })
    // The strip is NUMBERED CIRCLES with the current stage's name beside them.
    const strip = rows[0].querySelector('[data-testid="fleet-stage-strip"]')!
    expect(strip).toBeTruthy()
    const indexes = Array.from(strip.querySelectorAll('[data-stage-chip]'))
      .map(el => el.getAttribute('data-stage-index'))
    expect(indexes).toEqual(['1', '2', '3', '4', '5'])
    expect(strip.querySelector('[data-stage-chip="apply"]')!.getAttribute('data-stage-state')).toBe('running')
    expect(strip.querySelector('[data-testid="fleet-stage-current"]')!.textContent).toBe('apply')
  })

  it('shows branch and worktree on the line between name and pipeline', async () => {
    const { container } = render(<Fleet />)
    const rows = await wait(() => {
      const els = container.querySelectorAll('[data-fleet-agent-rows="alpha"] [data-fleet-agent-row]')
      expect(els.length).toBe(2)
      return els
    })
    // Agent 1 stands in the root checkout: branch only, no worktree word.
    const where1 = rows[0].querySelector('[data-fleet-agent-where="1"]')!
    expect(where1).toBeTruthy()
    expect(where1.textContent).toContain('main')
    expect(where1.textContent).not.toContain(' \u00b7 ')
    // Agent 2 stands in a worktree: branch, then the worktree's own name.
    const where2 = rows[1].querySelector('[data-fleet-agent-where="2"]')!
    expect(where2.textContent).toContain('change/feat')
    expect(where2.textContent).toContain('alpha-wt-feat')
    // And the pipeline still renders for the worktree agent too.
    expect(rows[1].querySelector('[data-testid="fleet-stage-strip"]')).toBeTruthy()
  })

  it('shows sub-rows for projects that are NOT selected', async () => {
    // The user: "subprojects tree must be shown all the time — don't hide
    // not-selected subprojects." Without clicking anything, every project
    // holding agents shows its tree.
    const { container } = render(<Fleet />)
    await wait(() => {
      expect(container.querySelector('[data-fleet-agent-rows="idle"]')).toBeTruthy()
    })
    expect(container.querySelectorAll('[data-fleet-agent-rows="alpha"] [data-fleet-agent-row]').length).toBe(2)
    expect(container.querySelectorAll('[data-fleet-agent-rows="idle"] [data-fleet-agent-row]').length).toBe(1)
  })

  it('suppresses sub-rows for a project with no live agents', async () => {
    const { container } = render(<Fleet />)
    await ready(container)
    expect(container.querySelector('[data-fleet-agent-rows="bare"]')).toBeNull()
  })

  it('marks the nothing-started agent as EMPTY, not as a failure', async () => {
    const { container } = render(<Fleet />)
    await ready(container)
    // The row's SELECT button — the flex-1 one, not the drag grip or the ⋯ menu.
    fireEvent.click(container.querySelector('[data-fleet-project="idle"] button.flex-1')!)
    await wait(() => expect(container.querySelector('[data-fleet-agent-rows="idle"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-agent-rows="idle"] [data-testid="fleet-stage-empty"]')).toBeTruthy()
    expect(container.querySelector('[data-fleet-agent-rows="idle"] [data-testid="fleet-stage-gap"]')).toBeNull()
  })

  it('hides sub-rows with their project when the filter runs — no orphans', async () => {
    const { container } = render(<Fleet />)
    const bar = await wait(() => {
      const el = container.querySelector('[data-fleet-column-controls]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    fireEvent.change(bar.querySelector('[data-fleet-column-filter]')!, { target: { value: 'alp' } })
    await wait(() => expect(container.querySelector('[data-fleet-column-flat]')).toBeTruthy())
    // idle is filtered OUT — its sub-rows are gone with it, and no sub-row
    // survives whose project row does not. alpha still matches the filter, so
    // its sub-rows legitimately remain (a selected project's tree renders in
    // the flat list too).
    expect(container.querySelector('[data-fleet-agent-rows="idle"]')).toBeNull()
    const flatNames = Array.from(container.querySelectorAll('[data-fleet-column-flat] [data-fleet-project]'))
      .map(el => el.getAttribute('data-fleet-project'))
    for (const name of flatNames) {
      const parent = container.querySelector(`[data-fleet-agent-rows="${name}"]`)
      expect(parent).toBeTruthy()
    }
  })
})

describe('the tree shortcut', () => {
  it('clicking a sub-row focuses that agent, exactly like its tile', async () => {
    const { container } = render(<Fleet />)
    await ready(container)
    const row = container.querySelector('[data-fleet-agent-rows="alpha"] [data-fleet-agent-row="2"]') as HTMLElement
    fireEvent.click(row)
    // The shell stores the enlarged pid per project — the same memory a tile
    // click writes — and marks the row focused.
    await wait(() => {
      const stored = JSON.parse(localStorage.getItem('set-fleet-view') ?? '{}')
      expect(stored.alpha?.enlarged).toBe(2)
    })
    await wait(() => {
      const r2 = container.querySelector('[data-fleet-agent-row="2"]')
      expect(r2?.getAttribute('data-fleet-agent-row-focused')).toBe('true')
    })
  })

  it('the focus survives leaving and returning', async () => {
    const { container } = render(<Fleet />)
    await ready(container)
    // Same effect-timing rule as the first test: the sub-rows exist only once
    // the shell's auto-selection has rendered them, so wait for the target.
    const row = await wait(() => {
      const el = container.querySelector('[data-fleet-agent-rows="alpha"] [data-fleet-agent-row="2"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    fireEvent.click(row)
    await wait(() => {
      expect(JSON.parse(localStorage.getItem('set-fleet-view') ?? '{}').alpha?.enlarged).toBe(2)
    })
    // Leave…
    fireEvent.click(container.querySelector('[data-fleet-project="idle"] button.flex-1')!)
    await wait(() => expect(container.querySelector('[data-fleet-agent-rows="idle"]')).toBeTruthy())
    // …and return: the remembered pid is resolved against the live answer and
    // the same agent is focused again, without another click.
    fireEvent.click(container.querySelector('[data-fleet-project="alpha"] button.flex-1')!)
    await wait(() => {
      expect(container.querySelector('[data-fleet-agent-row="2"]')
        ?.getAttribute('data-fleet-agent-row-focused')).toBe('true')
    })
  })
})
