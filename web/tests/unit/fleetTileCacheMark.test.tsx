/**
 * The cache mark on the TILE header, not only on the tab strip.
 *
 * Reported by the user 2026-08-27 with two screenshots: *"nem latszik a normal
 * grid-es ablak title-ben csak ha fullscrenelem és a tabokban nézem"*. The mark
 * hung off the tab strip, and the strip is drawn in one view mode only, and
 * only where a project holds several agents — so in the grid view, and for
 * every seat alone on its project, the change presented nothing at all.
 *
 * Why these particular assertions. The unit tests for `mark()` already decide
 * what a cache state MEANS; they passed throughout, and could not have caught
 * this, because the defect was in which surfaces call it. So this file asserts
 * the wiring on the rendered screen, and its load-bearing case is the one that
 * draws no strip: a single-agent project, where a test written against the tab
 * would find nothing and report a pass.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'

vi.mock('../../src/components/FleetTerminal', () => ({
  default: ({ label }: { label: string }) => <div data-fleet-terminal={label} />,
}))

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear() })

/** A cache state as the fleet API serializes one. */
function cache(over: Json = {}): Json {
  return {
    started_at: '2026-08-27T12:00:00+00:00',
    tokens: 141_403,
    ttl_seconds: 3600,
    model: 'claude-opus-5',
    rewrite_usd: 1.4140,
    seconds_remaining: 1800,
    cooled: 0.5,
    cold: false,
    ...over,
  }
}

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
    waiting_for: null,
    declaration_ignored: null,
    population: 'started-here',
    cache: cache(),
    ...over,
  }
}

function installFetch(projects: Json[]) {
  const payload = {
    // The screen branches on this count — a payload declaring zero agents
    // renders the empty state, whatever the projects hold.
    agents: projects.reduce((n, p) => n + (p.agents as Json[]).length, 0),
    working: 0, unknown: 0, owner_reachable: true, projects,
    quiet_means: 'no outstanding tool call as of the session log’s last flush',
  }
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ version: 1, groups: [], parked: [], ungrouped: [], missing: [] }),
      } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({
        ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }),
      } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(payload) } as Response)
  }))
}

function project(name: string, agents: Json[]): Json {
  return { name, root: `/home/x/${name}`, sources: ['process'], archived: false, agents }
}

/** The tile header for one pid, once the screen has loaded it. */
async function head(container: HTMLElement, pid: number): Promise<HTMLElement> {
  await waitFor(() => {
    expect(container.querySelector(`[data-fleet-tile-head="${pid}"]`)).not.toBeNull()
  })
  return container.querySelector(`[data-fleet-tile-head="${pid}"]`) as HTMLElement
}

const bar = (el: HTMLElement) => el.querySelector('[data-fleet-tile-cache]')
const price = (el: HTMLElement) => el.querySelector('[data-fleet-tile-cache-price]')
/**
 * The NAME element specifically — not "something red in the header".
 *
 * Written this way after a mutation SURVIVED: flipping the cold condition on
 * the name to its opposite failed no test, because the price beside it is red
 * too and `.text-red-400` found that instead. The assertion was measuring that
 * the header contained a red thing, which it did either way.
 */
const name = (el: HTMLElement) => el.querySelector('span.text-sm') as HTMLElement

describe('the tile header carries the cache mark', () => {
  it('draws a live seat partway, in a band, with no price', async () => {
    installFetch([project('demo', [agent(1, 'demo-a')])])
    const { container } = render(<Fleet />)
    const h = await head(container, 1)

    const b = bar(h)!
    expect(b.getAttribute('data-fleet-tile-cache')).toBe('live')
    expect(Number(b.getAttribute('data-fleet-tile-cache-fill'))).toBeCloseTo(0.5)
    // A live seat states no cost: while the cache lives, its read price is what
    // the reader pays whatever they do.
    expect(price(h)).toBeNull()
    // And its name is NOT red — asserted here rather than only on the cold
    // case, because a name that is always red passes every cold-only test.
    expect(name(h).className).not.toContain('text-red-400')
  })

  it('draws a cold seat full, with a red name and the rewrite price', async () => {
    installFetch([project('demo', [
      agent(1, 'demo-a', { cache: cache({ cooled: 1, cold: true, seconds_remaining: 0, rewrite_usd: 1.96 }) }),
    ])])
    const { container } = render(<Fleet />)
    const h = await head(container, 1)

    expect(bar(h)!.getAttribute('data-fleet-tile-cache')).toBe('cold')
    expect(Number(bar(h)!.getAttribute('data-fleet-tile-cache-fill'))).toBe(1)
    expect(price(h)!.textContent).toBe('$1.96')
    // The name and the bar are two marks of one condition — the name must be
    // red exactly when the bar is full, never one without the other.
    expect(name(h).className).toContain('text-red-400')
    expect(name(h).className).not.toContain('text-fg-strong')
  })

  it('marks an unmeasured seat as unknown, with no bar and no price', async () => {
    installFetch([project('demo', [agent(1, 'demo-a', { cache: null })])])
    const { container } = render(<Fleet />)
    const h = await head(container, 1)

    expect(h.querySelector('[data-fleet-tile-cache="unmeasured"]')).not.toBeNull()
    // Absent, not zero-length: a bar drawn at 0 would say "measured, and cold in
    // an hour", which is a claim nobody made.
    expect(h.querySelector('[data-fleet-tile-cache-fill]')).toBeNull()
    expect(price(h)).toBeNull()
  })

  /**
   * The case the reported defect actually lived in. A project with one agent
   * draws no tab strip at all, so every assertion written against
   * `[data-fleet-agent-tab]` passes vacuously here — which is what "covered by
   * unit tests" meant before this file existed.
   */
  it('shows the mark for a seat alone on its project, where no tab strip exists', async () => {
    installFetch([project('solo', [agent(7, 'solo-a', { project: 'solo' })])])
    const { container } = render(<Fleet />)
    const h = await head(container, 7)

    expect(container.querySelector('[data-fleet-agent-tab]')).toBeNull()
    expect(bar(h)!.getAttribute('data-fleet-tile-cache')).toBe('live')
  })

  it('keeps the unmeasured mark apart from the binding-not-confirmed marker', async () => {
    installFetch([project('demo', [
      agent(1, 'demo-a', { cache: null, binding_confirmed: false }),
    ])])
    const { container } = render(<Fleet />)
    const h = await head(container, 1)

    const unmeasured = h.querySelector('[data-fleet-tile-cache="unmeasured"]')!
    // Both are amber, and on the tab strip both are a bare `?`. On this surface
    // the cache one says which `?` it is, so the two cannot be read as one.
    expect(unmeasured.textContent).toContain('cache')
    expect(unmeasured.textContent).not.toBe('?')
  })

  it('puts the same figures in the header title as the tab would', async () => {
    installFetch([project('demo', [agent(1, 'demo-a')])])
    const { container } = render(<Fleet />)
    const h = await head(container, 1)

    const title = h.getAttribute('title') ?? ''
    expect(title).toContain('30m')          // remaining
    expect(title).toContain('141')          // the size, grouped
    expect(title).toContain('$1.41')        // the rewrite cost
  })

  it('states that nothing was measured, rather than staying silent, in the title', async () => {
    installFetch([project('demo', [agent(1, 'demo-a', { cache: null })])])
    const { container } = render(<Fleet />)
    const h = await head(container, 1)

    expect(h.getAttribute('title') ?? '').toContain('not measured')
  })
})

describe('the tab and the tile header cannot disagree', () => {
  /**
   * Two surfaces, one condition. Asserted across a fleet that holds all three
   * states at once, so a wiring that fell back to a default on ONE surface
   * shows up as a mismatch rather than as a plausible-looking screen.
   */
  it('agrees on every seat, across live, cold and unmeasured', async () => {
    installFetch([project('demo', [
      agent(1, 'demo-live'),
      agent(2, 'demo-cold', { cache: cache({ cooled: 1, cold: true, seconds_remaining: 0 }) }),
      agent(3, 'demo-unknown', { cache: null }),
    ])])
    const { container } = render(<Fleet />)
    await head(container, 1)

    for (const pid of [1, 2, 3]) {
      const h = container.querySelector(`[data-fleet-tile-head="${pid}"]`) as HTMLElement
      const tab = container.querySelector(`[data-fleet-agent-tab="${pid}"]`)
      // The strip is not drawn in this view; when it is, the two read one
      // computation. Guard so this asserts something either way rather than
      // passing because it found nothing.
      const tileKind = h.querySelector('[data-fleet-tile-cache]')?.getAttribute('data-fleet-tile-cache')
        ?? 'unmeasured'
      if (tab) {
        const tabKind = tab.querySelector('[data-fleet-tab-cache]')?.getAttribute('data-fleet-tab-cache')
          ?? 'unmeasured'
        expect(tileKind).toBe(tabKind)
      }
      expect(tileKind).toBe(pid === 1 ? 'live' : pid === 2 ? 'cold' : 'unmeasured')
    }
  })
})
