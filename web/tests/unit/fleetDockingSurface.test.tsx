/**
 * Docking, on the real screen, driven by clicking the control a person clicks.
 *
 * The geometry module and the band component each have their own tests. What
 * neither can show is the claim that actually matters here — that docking MOVES
 * a panel rather than copying it, and that the space comes back when it is
 * undocked. Both are properties of the page, and both fail in the reassuring
 * direction: a duplicated panel looks like a working feature until you notice
 * the two copies disagree, and space that never returns looks like a layout.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function agent(pid: number, name: string, over: Json = {}): Json {
  return {
    pid, name, project: 'demo', branch: 'main', session_id: 'abc',
    binding_confirmed: true, sources: ['process'], kind: 'interactive',
    state: 'quiet', tool: null, tool_elapsed_seconds: null, other_tools: [],
    last_movement_seconds: 12, unknown_reason: null,
    population: 'started-here', terminal_label: `t-${pid}`, ...over,
  }
}

const body = {
  agents: 2, working: 0, unknown: 0,
  owner_reachable: true,
  projects: [{
    name: 'demo', root: '/home/x/demo', sources: ['process'], archived: false,
    agents: [agent(1, 'one'), agent(2, 'two')],
  }],
  quiet_means: 'x',
}

/** Layout answers, and every write recorded so the test can inspect them. */
function installFetch(layout: Json = {}) {
  const writes: { url: string; body: Json }[] = []
  let current: Json = {
    version: 1, groups: [], parked: [], ungrouped: ['demo'], missing: [],
    splits: {}, docks: {}, docks_legacy: [], ...layout,
  }
  const stub = vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout/docks') && init?.method === 'PUT') {
      const sent = JSON.parse(String(init.body)) as Json
      writes.push({ url: u, body: sent })
      current = {
        ...current,
        // Per project since 2026-08-20: the write replaces ONE key.
        docks: { ...(current.docks as Json), [String(sent.project)]: sent.docks },
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve(sent) } as unknown as Response)
    }
    if (u.includes('/api/fleet/layout/splits') && init?.method === 'PUT') {
      const sent = JSON.parse(String(init.body)) as Json
      writes.push({ url: u, body: sent })
      return Promise.resolve({ ok: true, json: () => Promise.resolve(sent) } as unknown as Response)
    }
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(current) } as unknown as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({
        ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }),
      } as unknown as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response)
  })
  vi.stubGlobal('fetch', stub)
  return { writes }
}

beforeEach(() => {
  vi.useRealTimers()
  try { localStorage.clear() } catch { /* no storage here */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

async function ready(container: HTMLElement) {
  await screen.findByText('demo')
  await waitFor(() => {
    if (!container.querySelector('[data-tile-dock]')) throw new Error('no dock control yet')
  })
}

describe('sending a panel to an edge', () => {
  it('offers one control per edge, so the reader picks and the screen does not', async () => {
    installFetch()
    const { container } = render(<Fleet />)
    await ready(container)
    const controls = container.querySelector('[data-tile-dock]') as HTMLElement
    for (const edge of ['left', 'right', 'top', 'bottom']) {
      expect(controls.querySelector(`[data-tile-control="dock-${edge}"]`)).not.toBeNull()
    }
  })

  it('persists the docking to its own route, not to the version-guarded PUT', async () => {
    const { writes } = installFetch()
    const { container } = render(<Fleet />)
    await ready(container)
    ;(container.querySelector('[data-tile-control="dock-right"]') as HTMLElement).click()
    await waitFor(() => expect(writes.length).toBeGreaterThan(0))
    expect(writes[0].url).toContain('/api/fleet/layout/docks')
    expect(writes[0].body).toEqual({
      // The project rides with it: docking used to be screen-wide, and a write
      // that can omit the project is the shape that made it so.
      project: 'demo',
      docks: [{ kind: 'agent', id: 't-1', edge: 'right' }],
    })
  })

  it('MOVES the panel — it does not leave a copy in the grid', async () => {
    // The claim neither module test can make. A duplicated panel looks like a
    // working feature until the two copies disagree, and the one nobody is
    // watching is the one that goes stale.
    installFetch({ docks: { demo: [{ kind: 'agent', id: 't-1', edge: 'right' }] } })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    await waitFor(() => {
      if (!container.querySelector('[data-fleet-dock]')) throw new Error('not docked yet')
    })
    const tiles = container.querySelectorAll('[data-tile-controls]')
    // Two agents, one docked: exactly two tiles in total, not three.
    expect(tiles.length).toBe(2)
    expect(container.querySelectorAll('[data-fleet-dock]').length).toBe(1)
  })

  it('renders the band on the edge it was docked to', async () => {
    installFetch({ docks: { demo: [{ kind: 'agent', id: 't-2', edge: 'bottom' }] } })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const band = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock]')
      if (!el) throw new Error('no band')
      return el
    })
    expect(band.getAttribute('data-fleet-dock-edge')).toBe('bottom')
    expect(band.getAttribute('data-fleet-dock')).toBe('t-2')
  })
})

describe('bringing it back', () => {
  it('undocks by pressing the edge it is already on, so the control is never a dead end', async () => {
    const { writes } = installFetch({ docks: { demo: [{ kind: 'agent', id: 't-1', edge: 'right' }] } })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const band = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock]')
      if (!el) throw new Error('no band')
      return el as HTMLElement
    })
    // The docked panel's own tile carries the control, showing the edge as active.
    const active = band.querySelector('[data-tile-control="dock-right"][data-tile-control-active="on"]')
    expect(active).not.toBeNull()
    ;(active as HTMLElement).click()
    await waitFor(() => expect(writes.length).toBeGreaterThan(0))
    expect(writes[writes.length - 1].body).toEqual({ project: 'demo', docks: [] })
  })

  it('returns the space — the band is gone and the agent is back in the grid', async () => {
    installFetch({ docks: { demo: [{ kind: 'agent', id: 't-1', edge: 'right' }] } })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const band = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock]')
      if (!el) throw new Error('no band')
      return el as HTMLElement
    })
    ;(band.querySelector('[data-tile-control="dock-right"]') as HTMLElement).click()
    await waitFor(() => {
      if (container.querySelector('[data-fleet-dock]')) throw new Error('still docked')
    })
    expect(container.querySelectorAll('[data-tile-controls]').length).toBe(2)
  })
})

describe('two edges at once', () => {
  it('renders a band on each and leaves the grid what is left', async () => {
    installFetch({
      docks: {
        demo: [
          { kind: 'agent', id: 't-1', edge: 'right' },
          { kind: 'agent', id: 't-2', edge: 'top' },
        ],
      },
    })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    await waitFor(() => {
      if (container.querySelectorAll('[data-fleet-dock]').length !== 2) throw new Error('not both')
    })
    const edges = [...container.querySelectorAll('[data-fleet-dock]')]
      .map(el => el.getAttribute('data-fleet-dock-edge'))
    expect(new Set(edges)).toEqual(new Set(['right', 'top']))
  })
})

describe('docking belongs to ONE project', () => {
  /**
   * The defect the user reported by looking at the screen on 2026-08-20:
   * *"layout nem projekt szinten van hanem globálisan. ez nem jó, projekt
   * szinten kell értelmezni"*.
   *
   * Docking was stored screen-wide, so a terminal docked while looking at one
   * project held the same edge in every other project. Nothing there could
   * render in it, so the band could only say *"no running agent with this
   * terminal in <the project you are looking at>"* — the whole right-hand side
   * of the screen taken by an empty band naming somebody else's project. It
   * fails in the reassuring direction: nothing throws, nothing is counted, and
   * the screen still looks like a layout.
   */
  it('does not render another project\'s docked panel', async () => {
    installFetch({ docks: { 'somewhere-else': [{ kind: 'agent', id: 't-1', edge: 'right' }] } })
    const { container } = render(<Fleet />)
    await ready(container)
    // Both agents are in the GRID, and no band belongs to this screen.
    expect(container.querySelectorAll('[data-fleet-dock]').length).toBe(0)
    expect(container.querySelectorAll('[data-tile-controls]').length).toBe(2)
    expect(container.textContent).not.toMatch(/kept, not closed/i)
  })

  it('reads a pre-2026-08-20 flat list as NOTHING docked, never as this project\'s', async () => {
    // The old shape carries no project, so adopting it into whichever project
    // happens to be selected would put a band where nobody put it. The server
    // keeps the list under `docks_legacy`, so refusing it here loses nothing.
    installFetch({ docks: [{ kind: 'agent', id: 't-1', edge: 'right' }] as unknown as Json })
    const { container } = render(<Fleet />)
    await ready(container)
    expect(container.querySelectorAll('[data-fleet-dock]').length).toBe(0)
  })
})

describe('a docked panel is not also a tab', () => {
  /**
   * Asked for on 2026-08-20: *"ha ki van téve layoutba fixen egy view akkor ne
   * hozza a view tabs listaban az altalanos view sorban"*.
   *
   * The tab strip named every agent in the project, so a docked one appeared
   * both in its band and in the strip — two ways to reach one panel, and
   * clicking the tab enlarges a tile the grid does not contain. Docking is a
   * MOVE; the strip lists what the grid holds.
   */
  it('drops the docked agent from the tab strip, and says so in the count', async () => {
    localStorage.setItem('set-fleet-view', JSON.stringify({ demo: { enlarged: 2 } }))
    installFetch({ docks: { demo: [{ kind: 'agent', id: 't-1', edge: 'right' }] } })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    await waitFor(() => {
      if (!container.querySelector('[data-fleet-dock]')) throw new Error('not docked yet')
    })
    // Two agents, one docked, one enlarged: nothing left to tab between, so the
    // strip is not rendered at all — and the header does not claim one either.
    expect(container.querySelector('[data-fleet-agent-tab="1"]')).toBeNull()
    expect(container.querySelector('[data-fleet-chip="as-tabs"]')).toBeNull()
  })

  it('still lists the agents that ARE in the grid', async () => {
    // The other direction, so the fix cannot be "never show tabs".
    localStorage.setItem('set-fleet-view', JSON.stringify({ demo: { enlarged: 1 } }))
    installFetch()
    const { container } = render(<Fleet />)
    await ready(container)
    await waitFor(() => {
      if (!container.querySelector('[data-fleet-agent-tabs]')) throw new Error('no strip')
    })
    expect(container.querySelector('[data-fleet-agent-tab="2"]')).not.toBeNull()
    // Marks and numbers on this strip now; the sentence is on `aria-label`.
    expect(container.querySelector('[data-fleet-chip="as-tabs"]')!.getAttribute('aria-label'))
      .toMatch(/1 as tabs/i)
  })
})

describe('a docked panel whose agent is gone', () => {
  it('says the panel was kept rather than rendering an empty band', async () => {
    // A blank band is indistinguishable from a broken one, and the reader would
    // conclude the screen lost something.
    installFetch({ docks: { demo: [{ kind: 'agent', id: 't-999', edge: 'right' }] } })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const band = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock]')
      if (!el) throw new Error('no band')
      return el as HTMLElement
    })
    expect(band.textContent).toMatch(/kept, not closed/i)
  })

  it('reports its failing count as UNKNOWN, not as zero', async () => {
    // There is no agent to ask, so "nothing is wrong" would be a claim of calm
    // nobody measured — the false-absence class.
    installFetch({ docks: { demo: [{ kind: 'agent', id: 't-999', edge: 'right' }] } })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    const marker = await waitFor(() => {
      const el = container.querySelector('[data-fleet-dock-marker]')
      if (!el) throw new Error('no marker')
      return el
    })
    expect(marker.getAttribute('data-fleet-dock-failing')).toBe('unknown')
  })
})

describe('docking a panel that the grid was treating specially', () => {
  /**
   * The defect found by LOOKING at the screen on 2026-08-20, which every
   * structural and behavioural check in this change missed.
   *
   * `enlarged` named a pid the grid no longer contained, so every remaining
   * tile took the "somebody else is enlarged, so I am a tab" branch and
   * rendered nothing. The panel went entirely black under a header still
   * claiming three agents and two tabs — a screen contradicting itself, with no
   * error thrown and nothing to count.
   */
  it('does not empty the grid when the ENLARGED panel is the one docked', async () => {
    localStorage.setItem('set-fleet-view', JSON.stringify({ demo: { enlarged: 1 } }))
    installFetch({ docks: { demo: [{ kind: 'agent', id: 't-1', edge: 'right' }] } })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    await waitFor(() => {
      if (!container.querySelector('[data-fleet-dock]')) throw new Error('not docked yet')
    })
    // The other agent must still be on screen. Before the fix this was zero.
    const tiles = container.querySelectorAll('[data-tile-controls]')
    expect(tiles.length).toBe(2)   // one in the band, one in the grid
    const grid = container.querySelector('[data-fleet-docked]')
    expect(grid?.querySelectorAll('[data-tile-controls]').length).toBeGreaterThan(0)
  })

  it('does not render a FOCUSED panel twice when it is docked', async () => {
    // The mirror image: focus resolved against every agent would put one agent
    // in the band and full-screen over the grid at the same time.
    localStorage.setItem('set-fleet-view', JSON.stringify({ demo: { focus: 1 } }))
    installFetch({ docks: { demo: [{ kind: 'agent', id: 't-1', edge: 'right' }] } })
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    await waitFor(() => {
      if (!container.querySelector('[data-fleet-dock]')) throw new Error('not docked yet')
    })
    expect(container.querySelectorAll('[data-tile-controls="1"]').length).toBe(1)
  })

  it('an enlarged panel that is NOT docked still gets its layout', async () => {
    // The other direction, so the fix cannot be "ignore enlarged entirely".
    localStorage.setItem('set-fleet-view', JSON.stringify({ demo: { enlarged: 1 } }))
    installFetch()
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    await waitFor(() => {
      if (!container.querySelector('[data-tile-controls]')) throw new Error('no tiles')
    })
    // Enlarged means one card plus a tab strip — the strip's own hint is on screen.
    expect(container.querySelector('[data-fleet-chip="as-tabs"]')).not.toBeNull()
  })
})
