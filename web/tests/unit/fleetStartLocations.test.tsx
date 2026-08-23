/**
 * Choosing where a new agent starts — the decisions, and the form that asks.
 *
 * Before this change the start form sent the project root and nothing else, so
 * a change/ worktree — the directory this framework's parallel-work discipline
 * exists to create — was the one place the screen could not start an agent.
 *
 * The decisions are asserted as functions AND through the rendered form,
 * because they fail differently: a rule that is right and never asked answers
 * nothing, which is the shape that let a fully-green change ship an empty
 * panel.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'
import {
  defaultLocation,
  locationLabel,
  offerable,
  selectorWorthShowing,
  type StartLocation,
} from '../../src/lib/fleetStartLocations'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const MAIN: StartLocation = { path: '/repo', branch: 'main', is_main: true, prunable: false }
const WT: StartLocation = { path: '/repo-add-auth', branch: 'change/add-auth', is_main: false, prunable: false }
const DETACHED: StartLocation = { path: '/tmp/base-e78', branch: '', is_main: false, prunable: false }
const GONE: StartLocation = { path: '/tmp/vanished', branch: 'change/old', is_main: false, prunable: true }

describe('the decisions', () => {
  it('never offers a prunable location — the endpoint refuses it', () => {
    expect(offerable([MAIN, WT, GONE])).toEqual([MAIN, WT])
  })

  it('defaults to the main checkout, not to whatever came back first', () => {
    expect(defaultLocation([WT, MAIN], '/fallback')).toBe('/repo')
  })

  it('falls back to the project root when no entry claims to be the checkout', () => {
    // Picking locations[0] here would present a worktree as the default while
    // looking exactly like a correct answer.
    expect(defaultLocation([WT], '/fallback')).toBe('/fallback')
  })

  it('never defaults to a prunable location even if it claims to be main', () => {
    expect(defaultLocation([{ ...GONE, is_main: true }], '/fallback')).toBe('/fallback')
  })

  it('labels a worktree by its branch, and a detached one by its directory', () => {
    expect(locationLabel(WT)).toBe('change/add-auth')
    expect(locationLabel(DETACHED)).toBe('base-e78')
    expect(locationLabel(MAIN)).toBe('main checkout (main)')
  })

  it('shows no selector when the checkout is the only place to start', () => {
    expect(selectorWorthShowing([MAIN])).toBe(false)
    expect(selectorWorthShowing([MAIN, GONE])).toBe(false)
    expect(selectorWorthShowing([MAIN, WT])).toBe(true)
  })
})

// --------------------------------------------------------------------------- //
// the form
// --------------------------------------------------------------------------- //

const PROJECT = { name: 'proj', root: '/repo', agents: [], sources: ['registry'] }

function stubFleet(locations: StartLocation[] | 'unreadable', onStart: (body: any) => void) {
  const started: any[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url)
    if (u === '/api/fleet/owner') {
      return { ok: true, json: async () => ({ available: true, held: 0 }) } as any
    }
    if (u.includes('/worktrees')) {
      if (locations === 'unreadable') return { ok: false, status: 500, json: async () => ({}) } as any
      return { ok: true, json: async () => ({ project: 'proj', root: '/repo', locations }) } as any
    }
    if (u === '/api/fleet/agents' && init?.method === 'POST') {
      const body = JSON.parse(String(init.body))
      started.push(body)
      onStart(body)
      return { ok: true, json: async () => ({ label: body.label }) } as any
    }
    if (u.startsWith('/api/fleet/agents')) {
      return { ok: true, json: async () => ({ agents: [], projects: [PROJECT], measured_at: new Date().toISOString() }) } as any
    }
    return { ok: true, json: async () => ({}) } as any
  }))
  return started
}

async function openStartForm() {
  render(<Fleet />)
  const button = await waitFor(() => {
    const el = document.querySelector('[data-fleet-start="offer"]')
    if (!el) throw new Error('no start control yet')
    return el as HTMLElement
  })
  fireEvent.click(button)
}

describe('the form', () => {
  it('offers the worktrees and starts in the one that was chosen', async () => {
    const started = stubFleet([MAIN, WT], () => {})
    await openStartForm()

    const select = await waitFor(() => {
      const el = document.querySelector('[data-fleet-start="location"]') as HTMLSelectElement | null
      if (!el) throw new Error('no selector yet')
      return el
    })
    expect(select.value).toBe('/repo')
    expect(Array.from(select.options).map(o => o.textContent)).toEqual([
      'main checkout (main)', 'change/add-auth',
    ])

    fireEvent.change(select, { target: { value: '/repo-add-auth' } })
    fireEvent.submit(document.querySelector('[data-fleet-start="form"]')!)

    await waitFor(() => expect(started.length).toBe(1))
    expect(started[0].cwd).toBe('/repo-add-auth')
  })

  it('omits a prunable worktree from the offer', async () => {
    stubFleet([MAIN, WT, GONE], () => {})
    await openStartForm()
    const select = await waitFor(() => {
      const el = document.querySelector('[data-fleet-start="location"]') as HTMLSelectElement | null
      if (!el) throw new Error('no selector yet')
      return el
    })
    expect(Array.from(select.options).map(o => o.value)).toEqual(['/repo', '/repo-add-auth'])
  })

  it('renders no selector for a project with a single checkout', async () => {
    const started = stubFleet([MAIN], () => {})
    await openStartForm()
    await waitFor(() => {
      expect(document.querySelector('[data-fleet-start="form"]')).toBeTruthy()
    })
    expect(document.querySelector('[data-fleet-start="location"]')).toBeNull()

    fireEvent.submit(document.querySelector('[data-fleet-start="form"]')!)
    await waitFor(() => expect(started.length).toBe(1))
    expect(started[0].cwd).toBe('/repo')
  })

  it('says the worktrees could not be read, and still starts in the root', async () => {
    const started = stubFleet('unreadable', () => {})
    await openStartForm()
    await waitFor(() => {
      expect(document.querySelector('[data-fleet-start="locations-unread"]')).toBeTruthy()
    })
    // A silent empty selector would read as "this project has no worktrees".
    expect(document.querySelector('[data-fleet-start="location"]')).toBeNull()

    fireEvent.submit(document.querySelector('[data-fleet-start="form"]')!)
    await waitFor(() => expect(started.length).toBe(1))
    expect(started[0].cwd).toBe('/repo')
  })
})
