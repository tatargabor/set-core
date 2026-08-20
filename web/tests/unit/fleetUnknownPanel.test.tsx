/**
 * A panel kind this build does not have, ON THE SCREEN — task 4.3.
 *
 * The module test beside this one proves `resolvePanels` keeps such a panel in
 * its list. That is a different claim from the one that matters, and the
 * difference is the mechanism-versus-result class this repository keeps
 * recording: a resolver can return a perfectly correct entry that nothing ever
 * renders, and every module test stays green while the reader sees a screen
 * that silently closed something for them.
 *
 * So these render the real page and assert what a person would see.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'
import { VIEW_KEY_FOR_TESTS } from '../../src/lib/fleetViewState'

type Json = Record<string, unknown>

function agent(pid: number, name: string, over: Json = {}): Json {
  return {
    pid, name, project: 'demo', branch: 'main', session_id: 'abc',
    binding_confirmed: true, sources: ['process'], kind: 'interactive',
    state: 'quiet', tool: null, tool_elapsed_seconds: null, other_tools: [],
    last_movement_seconds: 12, unknown_reason: null, ...over,
  }
}

const project = (name: string, agents: Json[]): Json => ({
  name, root: `/home/x/${name}`, sources: ['process'], archived: false, agents,
})

function installFetch(body: Json) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    if (String(url).includes('/api/fleet/layout')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ version: 1, groups: [], parked: [], ungrouped: [], missing: [], splits: {} }),
      } as unknown as Response)
    }
    if (String(url).includes('/log')) {
      return Promise.resolve({
        ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }),
      } as unknown as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response)
  }))
}

/** Write a per-project memory the way the surface itself stores one. */
function remember(project: string, view: Json) {
  localStorage.setItem(VIEW_KEY_FOR_TESTS, JSON.stringify({ [project]: view }))
}

const oneProject = {
  agents: 1, working: 0, unknown: 0,
  projects: [project('demo', [agent(1, 'demo-agent')])],
  quiet_means: 'x',
}

beforeEach(() => {
  vi.useRealTimers()
  try { localStorage.clear() } catch { /* no storage here */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('a stored panel whose kind this build does not have', () => {
  it('is reported on screen, naming the kind — not dropped', async () => {
    remember('demo', { panels: [{ kind: 'changes', id: 'v1' }] })
    installFetch(oneProject)
    const { container } = render(<Fleet />)

    const banner = await waitFor(() => {
      const el = container.querySelector('[data-fleet-unknown-panels]')
      if (!el) throw new Error('no report rendered')
      return el
    })
    expect(banner.getAttribute('data-fleet-unknown-panels')).toBe('1')
    // The KIND has to appear. "Something is missing" is not a report — a reader
    // cannot act on it, and cannot tell it from a bug in the screen itself.
    expect(banner.textContent).toContain('changes')
    expect(banner.textContent).toContain('v1')
  })

  it('says the panel was KEPT, so the reader does not read it as closed', async () => {
    // The direction that matters. A message reading "1 panel could not be
    // shown" leaves open the likeliest wrong conclusion — that it is gone —
    // and the reader then re-opens something that was never closed.
    remember('demo', { panels: [{ kind: 'changes', id: 'v1' }] })
    installFetch(oneProject)
    const { container } = render(<Fleet />)
    const banner = await waitFor(() => {
      const el = container.querySelector('[data-fleet-unknown-panels]')
      if (!el) throw new Error('no report rendered')
      return el
    })
    expect(banner.textContent).toMatch(/kept, not closed/i)
  })

  it('reports every unknown panel, not just the first', async () => {
    remember('demo', { panels: [{ kind: 'changes', id: 'v1' }, { kind: 'bugs', id: 'v2' }] })
    installFetch(oneProject)
    const { container } = render(<Fleet />)
    const banner = await waitFor(() => {
      const el = container.querySelector('[data-fleet-unknown-panels]')
      if (!el) throw new Error('no report rendered')
      return el
    })
    expect(banner.getAttribute('data-fleet-unknown-panels')).toBe('2')
    expect(banner.textContent).toContain('bugs')
  })

  it('says NOTHING when every stored panel is a kind this build has', async () => {
    // The other half, and the one that decides whether the report is worth
    // reading. A banner that appears on an ordinary screen is a banner people
    // learn to skip — the same failure as a gate that fires daily on nothing.
    remember('demo', { terminals: ['demo-label'], panels: [{ kind: 'agent', id: 'other' }] })
    installFetch(oneProject)
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    expect(container.querySelector('[data-fleet-unknown-panels]')).toBeNull()
  })

  it('says nothing on a screen with no stored panels at all', async () => {
    installFetch(oneProject)
    const { container } = render(<Fleet />)
    await screen.findByText('demo')
    expect(container.querySelector('[data-fleet-unknown-panels]')).toBeNull()
  })
})
