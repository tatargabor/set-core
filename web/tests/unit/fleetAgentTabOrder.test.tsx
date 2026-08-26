/**
 * Ordering the agent tabs by hand — the wiring, not the rule.
 *
 * `fleetAgentOrder.test.ts` decides what an order MEANS. This file asserts what
 * the screen does with one, and it exists for the three behaviours that are
 * invisible to any test of the rule:
 *
 *  - a stored order must reach the GRID, not only the strip. The reader asked
 *    for both in one sentence, and two surfaces reading one list is the only
 *    thing that keeps them from disagreeing.
 *  - a keyboard move must WRITE. An order that looks right until the page is
 *    reloaded is worse than none, because it is discovered later.
 *  - a click must NOT write, and must still select. On the project column the
 *    same gesture once moved a row six positions and saved it, silently.
 *
 * The keyboard path is what is driven here rather than the pointer one. That is
 * not a compromise: jsdom has no layout, so `getBoundingClientRect` answers
 * zeroes and a synthetic pointer drag would measure the test's own arithmetic.
 * The keyboard path is a real way to reorder, and it is the one that can be
 * asserted.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function agent(pid: number, name: string, over: Json = {}): Json {
  return {
    pid,
    name,
    terminal_label: name,
    project: 'demo',
    branch: 'main',
    session_id: `s-${pid}`,
    binding_confirmed: true,
    sources: ['process'],
    kind: 'interactive',
    state: 'quiet',
    tool: null,
    tool_elapsed_seconds: null,
    other_tools: [],
    last_movement_seconds: 12,
    unknown_reason: null,
    ...over,
  }
}

const three = {
  agents: 3,
  working: 0,
  unknown: 0,
  projects: [{
    name: 'demo',
    root: '/home/x/demo',
    sources: ['process'],
    archived: false,
    agents: [agent(1, 'demo-a'), agent(2, 'demo-b'), agent(3, 'demo-c')],
  }],
}

/** Every PUT the screen made to the order route. */
let orderWrites: Json[]

function installFetch(agentOrder: Record<string, string[]> = {}) {
  orderWrites = []
  const layout = {
    version: 1, groups: [], parked: [], ungrouped: [], missing: [],
    agent_order: agentOrder,
  }
  const stub = vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout/agent-order')) {
      orderWrites.push(JSON.parse(String(init?.body)) as Json)
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
    }
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(layout) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({
        ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }),
      } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(three) } as Response)
  })
  vi.stubGlobal('fetch', stub)
  return stub
}

/** The tab strip appears once an agent is enlarged. */
function enlargeFirst(container: HTMLElement) {
  fireEvent.click(container.querySelector(
    '[data-fleet-enlarged-toggle="1"], [data-tile-controls="1"] [data-tile-control="enlarge"]',
  )!)
}

const tabNames = (container: HTMLElement) =>
  Array.from(container.querySelectorAll('[data-fleet-agent-tab]'))
    .map(el => el.getAttribute('data-drag-handle'))

/** The tiles in the grid, by the agent they hold — `data-fleet-tile-head` is a pid. */
const NAMES: Record<string, string> = { '1': 'demo-a', '2': 'demo-b', '3': 'demo-c' }
const tileNames = (container: HTMLElement) =>
  Array.from(container.querySelectorAll('[data-fleet-tile-head]'))
    .map(el => NAMES[el.getAttribute('data-fleet-tile-head') ?? ''] ?? '?')

beforeEach(() => {
  vi.useRealTimers()
  try { localStorage.clear() } catch { /* no storage in this environment */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('a stored order on arrival', () => {
  it('lays the GRID out in it, before anything is enlarged', async () => {
    installFetch({ demo: ['demo-c', 'demo-a', 'demo-b'] })
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a')

    // The half the reader asked for in the same sentence as the tabs: *"a
    // gridben is, hogy hova tartozik"*.
    await waitFor(() => expect(tileNames(container)).toEqual(['demo-c', 'demo-a', 'demo-b']))
  })

  it('lays the STRIP out in the same order', async () => {
    installFetch({ demo: ['demo-c', 'demo-a', 'demo-b'] })
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a')
    await waitFor(() => expect(tileNames(container)[0]).toBe('demo-c'))

    enlargeFirst(container)
    expect(tabNames(container)).toEqual(['demo-c', 'demo-a', 'demo-b'])
  })

  it('leaves discovery order alone when nothing is stored', async () => {
    installFetch({})
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a')
    await waitFor(() => expect(tileNames(container)).toEqual(['demo-a', 'demo-b', 'demo-c']))
  })
})

describe('moving a tab', () => {
  it('moves the agent and WRITES the new order', async () => {
    installFetch({})
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a')
    enlargeFirst(container)
    expect(tabNames(container)).toEqual(['demo-a', 'demo-b', 'demo-c'])

    const last = container.querySelector('[data-drag-handle="demo-c"]') as HTMLElement
    fireEvent.keyDown(last, { key: 'ArrowLeft' })

    await waitFor(() => expect(orderWrites.length).toBe(1))
    expect(orderWrites[0]).toEqual({ project: 'demo', order: ['demo-a', 'demo-c', 'demo-b'] })
    // Optimistic: the strip shows it before the write returned.
    expect(tabNames(container)).toEqual(['demo-a', 'demo-c', 'demo-b'])
  })

  it('moves the GRID with it', async () => {
    installFetch({})
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a')
    enlargeFirst(container)
    fireEvent.keyDown(container.querySelector('[data-drag-handle="demo-c"]') as HTMLElement,
                      { key: 'ArrowLeft' })
    await waitFor(() => expect(orderWrites.length).toBe(1))

    // Back to the grid — the tiles follow the strip, because they are the same
    // array.
    fireEvent.click(container.querySelector('[data-tile-control="enlarge"]') as HTMLElement)
    await waitFor(() => expect(tileNames(container)).toEqual(['demo-a', 'demo-c', 'demo-b']))
  })

  it('does not move past either end', async () => {
    installFetch({})
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a')
    enlargeFirst(container)

    fireEvent.keyDown(container.querySelector('[data-drag-handle="demo-a"]') as HTMLElement,
                      { key: 'ArrowLeft' })
    fireEvent.keyDown(container.querySelector('[data-drag-handle="demo-c"]') as HTMLElement,
                      { key: 'ArrowRight' })
    await Promise.resolve()
    expect(orderWrites).toEqual([])
    expect(tabNames(container)).toEqual(['demo-a', 'demo-b', 'demo-c'])
  })

  it('ignores the arrows that do not belong to this axis', async () => {
    // Up and down on a horizontal strip would move a tab while the reader was
    // doing something else entirely.
    installFetch({})
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a')
    enlargeFirst(container)

    const tab = container.querySelector('[data-drag-handle="demo-c"]') as HTMLElement
    fireEvent.keyDown(tab, { key: 'ArrowUp' })
    fireEvent.keyDown(tab, { key: 'ArrowDown' })
    await Promise.resolve()
    expect(orderWrites).toEqual([])
  })
})

describe('a click is not a move', () => {
  it('selects the agent and writes nothing', async () => {
    installFetch({})
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a')
    enlargeFirst(container)

    const other = container.querySelector('[data-fleet-agent-tab="3"]') as HTMLElement
    fireEvent.pointerDown(other, { button: 0, pointerId: 1, clientX: 100, clientY: 10 })
    fireEvent.pointerUp(other, { pointerId: 1, clientX: 100, clientY: 10 })
    fireEvent.click(other)

    await waitFor(() => expect(
      container.querySelector('[data-fleet-agent-tab="3"]')!.getAttribute('data-fleet-agent-tab-active'),
    ).toBe('on'))
    // The defect this guards is the expensive one: a gesture that looks like
    // nothing happening rewriting a hand-made arrangement.
    expect(orderWrites).toEqual([])
    expect(tabNames(container)).toEqual(['demo-a', 'demo-b', 'demo-c'])
  })
})
