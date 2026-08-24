/**
 * The projects screen's view control, filter, and the live-session column.
 *
 * The model tests next door prove the counting. These prove the counting
 * reaches the screen — a distinction this repo has paid for: a change can be
 * fully green on its mechanism while the result on screen is empty.
 *
 * The assertion that matters most is the negative one: an unregistered live row
 * must carry no link, because the route it would point at does not resolve, and
 * a link that goes nowhere is worse than no affordance at all.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import Manager from '../../src/pages/Manager'

type Json = Record<string, unknown>

const projectsBody: Json[] = [
  { name: 'alpha', path: '/r/alpha', status: 'running', last_updated: '2026-08-24T10:00:00Z' },
  { name: 'beta', path: '/r/beta', status: 'stopped', last_updated: '2026-08-23T10:00:00Z' },
  { name: 'gamma', path: '/r/gamma', status: 'stopped', last_updated: '2026-08-22T10:00:00Z' },
]

const fleetBody = (over?: Json): Json => ({
  agents: 5, working: 0, unknown: 0, quiet: 5, unbucketed: 0,
  projects: [
    { name: 'alpha', root: '/r/alpha', sources: ['process'], archived: false,
      agents: [{ pid: 1 }, { pid: 2 }, { pid: 3 }] },
    { name: 'beta', root: '/r/beta', sources: ['registry'], archived: false, agents: [] },
    { name: 'stranger', root: '/r/stranger', sources: ['messaging'], archived: false,
      agents: [{ pid: 9 }, { pid: 10 }] },
  ],
  ...over,
})

/** `fleetOk: false` is the outage: the projects endpoint answers, the fleet does not. */
function install({ fleetOk = true }: { fleetOk?: boolean } = {}) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/agents')) {
      return fleetOk
        ? Promise.resolve({ ok: true, status: 200, headers: new Headers(),
                            json: () => Promise.resolve(fleetBody()) } as Response)
        : Promise.resolve({ ok: false, status: 503, headers: new Headers(),
                            text: () => Promise.resolve('down') } as Response)
    }
    return Promise.resolve({
      ok: true, status: 200,
      headers: new Headers({ 'X-Archived-Count': '0' }),
      json: () => Promise.resolve(projectsBody),
    } as Response)
  }))
}

const screen = () => render(<MemoryRouter><Manager /></MemoryRouter>)
const rows = (c: HTMLElement) => Array.from(c.querySelectorAll('tbody tr'))
const live = (c: HTMLElement, name: string) =>
  c.querySelector(`[data-projects-view]`) && rows(c).find(r => r.textContent?.includes(name))

beforeEach(() => { install() })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('the view control', () => {
  it('opens on the full listing, with both view sizes on screen', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))

    const all = container.querySelector('[data-projects-view="all"]')!
    const liveTab = container.querySelector('[data-projects-view="live"]')!
    expect(all.getAttribute('data-projects-view-active')).toBe('on')
    expect(all.textContent).toContain('3')
    // Two live: `alpha` (registered, 3 sessions) and `stranger` (unregistered).
    // Stated without switching — that is the point of putting it on the control.
    expect(liveTab.textContent).toContain('2')
  })

  it('switching narrows the rendered rows and states what it hid', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))

    fireEvent.click(container.querySelector('[data-projects-view="live"]')!)
    await waitFor(() => expect(rows(container)).toHaveLength(2))
    expect(container.textContent).toContain('alpha')
    expect(container.textContent).toContain('stranger')
    expect(container.textContent).not.toContain('gamma')

    const hidden = container.querySelector('[data-projects-hidden]')!
    expect(hidden.getAttribute('data-projects-hidden')).toBe('2')
    expect(hidden.textContent).toContain('without a live session')
  })

  it('says nothing about hidden rows while nothing is hidden', async () => {
    // The false-absence direction. A screen that always shows the line teaches
    // the reader to stop reading it.
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))
    expect(container.querySelector('[data-projects-hidden]')).toBeNull()
  })
})

describe('the name filter', () => {
  it('narrows in the all view and counts what it dropped', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))

    fireEvent.change(container.querySelector('[data-projects-filter]')!, { target: { value: 'AL' } })
    await waitFor(() => expect(rows(container)).toHaveLength(1))
    expect(container.querySelector('[data-projects-hidden]')!.textContent).toContain('2 filtered out')
  })

  it('survives a view switch, and one control clears everything', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))

    fireEvent.change(container.querySelector('[data-projects-filter]')!, { target: { value: 'alpha' } })
    fireEvent.click(container.querySelector('[data-projects-view="live"]')!)
    await waitFor(() => expect(rows(container)).toHaveLength(1))
    expect((container.querySelector('[data-projects-filter]') as HTMLInputElement).value).toBe('alpha')

    fireEvent.click(container.querySelector('[data-projects-clear]')!)
    await waitFor(() => expect(rows(container)).toHaveLength(3))
    expect((container.querySelector('[data-projects-filter]') as HTMLInputElement).value).toBe('')
  })

  it('an empty result says which narrowing emptied it, and stays escapable', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))

    fireEvent.change(container.querySelector('[data-projects-filter]')!, { target: { value: 'zzz' } })
    await waitFor(() => expect(container.querySelector('[data-projects-empty]')).toBeTruthy())
    expect(container.querySelector('[data-projects-empty]')!.textContent).toContain('zzz')
    expect(container.querySelector('[data-projects-clear]')).toBeTruthy()
  })
})

describe('the live-session column', () => {
  it('shows the count in the DEFAULT view, not only the live one', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))
    const alpha = live(container, 'alpha')!
    expect(alpha.querySelector('[data-projects-live]')!.getAttribute('data-projects-live')).toBe('3')
  })

  it('renders a measured zero as a zero, distinct from unmeasured', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))
    const beta = live(container, 'beta')!
    expect(beta.querySelector('[data-projects-live]')!.getAttribute('data-projects-live')).toBe('0')
    expect(container.querySelector('[data-projects-live-unmeasured]')).toBeNull()
  })
})

describe('when the fleet does not answer', () => {
  beforeEach(() => { install({ fleetOk: false }) })

  it('says the counts are unmeasured instead of showing zeros', async () => {
    const { container } = screen()
    await waitFor(() => expect(container.querySelector('[data-projects-live-unmeasured]')).toBeTruthy())
    const cells = Array.from(container.querySelectorAll('[data-projects-live]'))
    expect(cells).toHaveLength(3)
    expect(cells.every(c => c.getAttribute('data-projects-live') === 'unmeasured')).toBe(true)
  })

  it('leaves the listing intact', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))
  })

  it('does not present an empty live view as an absence of live work', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))
    fireEvent.click(container.querySelector('[data-projects-view="live"]')!)
    await waitFor(() => expect(container.querySelector('[data-projects-empty]')).toBeTruthy())
    const said = container.querySelector('[data-projects-empty]')!.textContent ?? ''
    expect(said).toContain('could not be measured')
    // The sentence that must NOT appear: the calm one.
    expect(said).not.toContain('No project has a live agent session')
  })

  it('the live tab does not claim a size it did not measure', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))
    expect(container.querySelector('[data-projects-view="live"]')!.textContent).toContain('?')
  })
})

describe('a live project the registry does not hold', () => {
  it('is listed in the live view, marked, and carries no link', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))
    fireEvent.click(container.querySelector('[data-projects-view="live"]')!)

    await waitFor(() => expect(container.querySelector('[data-projects-unregistered]')).toBeTruthy())
    const row = container.querySelector('[data-projects-unregistered="stranger"]')!
    expect(row.textContent).toContain('not registered')
    expect(row.querySelector('a')).toBeNull()
    expect(row.querySelector('[data-projects-live]')!.getAttribute('data-projects-live')).toBe('2')
  })

  it('does not appear in the default listing', async () => {
    const { container } = screen()
    await waitFor(() => expect(rows(container)).toHaveLength(3))
    expect(container.querySelector('[data-projects-unregistered]')).toBeNull()
  })
})
