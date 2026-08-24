/**
 * The project column's way-of-looking control, on screen.
 *
 * The model tests next door prove the counting. This file proves two things
 * only a render can:
 *
 *  - a live project sitting inside a COLLAPSED group, or in the parked section,
 *    reaches the live list. That is the whole reason the mode exists, and it is
 *    the property a flat list built from the rendered tree would silently lose;
 *  - the attention header keeps counting the WHOLE column in every mode. A view
 *    that narrows the list and the alarm together is the exact failure
 *    `ui-quality.md` names — a tidy screen reporting calm it has not verified.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

const agent = (pid: number, state = 'quiet'): Json => ({
  pid, name: `a${pid}`, project: null, branch: 'main', session_id: `s${pid}`,
  binding_confirmed: true, sources: ['process'], kind: 'interactive', state,
  tool: null, tool_elapsed_seconds: null, other_tools: [],
  last_movement_seconds: 5, unknown_reason: null,
})

const project = (name: string, agents: Json[] = []): Json => ({
  name, root: `/r/${name}`, sources: ['process'], archived: false, agents,
})

const LAYOUT = {
  version: 3,
  groups: [
    { id: 'g-open', name: 'open', collapsed: false, projects: ['alpha', 'beta'], missing: [] },
    // The load-bearing one: a project with a live agent, filed out of sight.
    { id: 'g-closed', name: 'closed', collapsed: true, projects: ['buried'], missing: [] },
  ],
  parked: ['parked-live'],
  parked_order: ['parked-live'],
  ungrouped: ['idle-tail'],
  missing: [],
}

const BODY = {
  agents: 3, working: 0, unknown: 0, waiting: 1, quiet: 2,
  projects: [
    project('alpha', [agent(1)]),
    project('beta'),
    project('buried', [agent(2)]),
    project('parked-live', [agent(3, 'waiting')]),
    // Agent-less AND needing a human. This is the row the live view removes,
    // and the one the attention header must keep counting anyway.
    { ...project('idle-tail'),
      awaiting: { manual: ['a change waiting for approval'], stalled: [], orphaned: [],
                  decision: [], unverifiable: [], source_missing: false, total: 1 } },
  ],
  quiet_means: 'no outstanding tool call',
}

function install(body: Json = BODY) {
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      if (init?.method === 'PUT') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(LAYOUT) } as Response)
      }
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

const controls = async (c: HTMLElement) =>
  waitFor(() => {
    const el = c.querySelector('[data-fleet-column-controls]')
    expect(el).toBeTruthy()
    return el as HTMLElement
  })

const flatNames = (c: HTMLElement) =>
  Array.from(c.querySelectorAll('[data-fleet-column-flat] [data-fleet-project]'))
    .map(el => el.getAttribute('data-fleet-project'))

describe('the column opens on the arrangement', () => {
  it('renders the group tree, not a flat list, and no hidden claim', async () => {
    const { container } = render(<Fleet />)
    await controls(container)
    // Wait for the ARRANGEMENT, not merely for the control bar: the bar renders
    // before the layout request answers, and asserting the tree at that moment
    // is asserting against a column that has not been told its shape yet. It
    // passed alone and failed in the full run, which is how that reads from
    // outside — an ordering-dependent test, not a defect in the product.
    await waitFor(() => expect(container.querySelector('[data-fleet-group="__ungrouped__"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-column-flat]')).toBeNull()
    expect(container.querySelector('[data-fleet-column-hidden]')).toBeNull()
  })

  it('states both sizes on the control, so neither needs switching to learn', async () => {
    const { container } = render(<Fleet />)
    const bar = await controls(container)
    expect(bar.querySelector('[data-fleet-column-mode="arrangement"]')!.textContent).toContain('5')
    expect(bar.querySelector('[data-fleet-column-mode="live"]')!.textContent).toContain('3')
  })
})

describe('the live mode', () => {
  it('reaches a live project inside a collapsed group and in the parked section', async () => {
    const { container } = render(<Fleet />)
    const bar = await controls(container)
    fireEvent.click(bar.querySelector('[data-fleet-column-mode="live"]')!)

    await waitFor(() => expect(container.querySelector('[data-fleet-column-flat]')).toBeTruthy())
    const names = flatNames(container)
    expect(names).toContain('alpha')
    // Neither of these is reachable from the rendered tree: one is collapsed
    // out of sight, one is in the parked section.
    expect(names).toContain('buried')
    expect(names).toContain('parked-live')
    expect(names).not.toContain('beta')
    expect(names).not.toContain('idle-tail')
  })

  it('says how many projects it dropped, and one control puts them back', async () => {
    const { container } = render(<Fleet />)
    const bar = await controls(container)
    fireEvent.click(bar.querySelector('[data-fleet-column-mode="live"]')!)

    const hidden = await waitFor(() => {
      const el = container.querySelector('[data-fleet-column-hidden]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(hidden.getAttribute('data-fleet-column-hidden')).toBe('2')
    expect(hidden.textContent).toContain('with no live session')

    fireEvent.click(container.querySelector('[data-fleet-column-clear]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-column-flat]')).toBeNull())
  })

  it('leaves the attention header counting the whole column', async () => {
    // Asserted as a VALUE, not as "it did not change when I clicked". The first
    // version of this test compared the header before and after the switch and
    // passed against a build whose header counted only live projects — the
    // mutation broke both readings equally, so the comparison held. A test that
    // watches the mechanism is silent about the result.
    const { container } = render(<Fleet />)
    const bar = await controls(container)
    const header = () => container.querySelector('[data-fleet-attention]') as HTMLElement

    // `idle-tail` has no agent and is awaiting a human: precisely the row the
    // live view removes, and precisely the one whose alarm must survive it.
    await waitFor(() => expect(header().querySelector('[data-fleet-jump="awaiting"]')).toBeTruthy())
    expect(header().querySelector('[data-fleet-jump="awaiting"]')!.textContent).toContain('1 waiting for a human')

    fireEvent.click(bar.querySelector('[data-fleet-column-mode="live"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-column-flat]')).toBeTruthy())
    expect(flatNames(container)).not.toContain('idle-tail')

    // The row is gone from the list; the alarm it raised is not.
    expect(header().querySelector('[data-fleet-jump="awaiting"]')!.textContent).toContain('1 waiting for a human')
    expect(header().querySelector('[data-fleet-jump="waiting"]')).toBeTruthy()
  })

  it('says so when nothing is live, rather than showing an empty column', async () => {
    install({ ...BODY, agents: 0, waiting: 0, projects: (BODY.projects as Json[]).map(p => ({ ...p, agents: [] })) })
    const { container } = render(<Fleet />)
    const bar = await controls(container)
    fireEvent.click(bar.querySelector('[data-fleet-column-mode="live"]')!)

    const empty = await waitFor(() => {
      const el = container.querySelector('[data-fleet-column-empty]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(empty.textContent).toContain('No project holds a live agent session')
    expect(empty.querySelector('[data-fleet-column-clear]')).toBeTruthy()
  })
})

describe('the filter', () => {
  it('flattens the tree while typed, matching case-insensitively', async () => {
    const { container } = render(<Fleet />)
    const bar = await controls(container)
    fireEvent.change(bar.querySelector('[data-fleet-column-filter]')!, { target: { value: 'BUR' } })

    await waitFor(() => expect(flatNames(container)).toEqual(['buried']))
    // A group tree with one row left is not the arrangement any more, so the
    // groups do not stay on screen pretending to be it.
    expect(container.querySelector('[data-fleet-group="__ungrouped__"]')).toBeNull()
    expect(container.querySelector('[data-fleet-column-hidden]')!.textContent).toContain('filtered out')
  })

  it('combines with the live mode and names both causes separately', async () => {
    const { container } = render(<Fleet />)
    const bar = await controls(container)
    fireEvent.click(bar.querySelector('[data-fleet-column-mode="live"]')!)
    fireEvent.change(bar.querySelector('[data-fleet-column-filter]')!, { target: { value: 'alpha' } })

    await waitFor(() => expect(flatNames(container)).toEqual(['alpha']))
    const said = container.querySelector('[data-fleet-column-hidden]')!.textContent ?? ''
    expect(said).toContain('with no live session')
    expect(said).toContain('filtered out')
  })

  it('clearing the filter restores the tree', async () => {
    const { container } = render(<Fleet />)
    const bar = await controls(container)
    fireEvent.change(bar.querySelector('[data-fleet-column-filter]')!, { target: { value: 'alpha' } })
    await waitFor(() => expect(container.querySelector('[data-fleet-column-flat]')).toBeTruthy())

    fireEvent.click(bar.querySelector('[aria-label="Clear the name filter"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-column-flat]')).toBeNull())
  })
})
