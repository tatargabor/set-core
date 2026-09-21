/**
 * The fleet-wide reopen — one dialog over every project's record.
 *
 * What is under test is the blast radius and the honesty of the sum: nothing is
 * posted on the first click, each project receives exactly its own ticks, and a
 * project that could not be asked makes the whole result partial rather than
 * vanishing into a count of zero.
 */

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RestoreAcrossProjects } from '../../src/components/FleetRestore'
import {
  offerAcross, summariseAcross, summarise,
  type RestoreResult, type RosterEntry,
} from '../../src/lib/fleetRoster'

const entry = (project: string, key: string, over: Partial<RosterEntry> = {}): RosterEntry => ({
  key, session_id: key, label: `${project}-${key}`, cwd: `/${project}`, project,
  kind: 'interactive', first_seen: 1, last_seen: 2, session_log: '/l',
  resumable: true, not_resumable_reason: null, running: false, ...over,
})

const result = (project: string, started: string[], skipped: string[] = [], complete = !skipped.length): RestoreResult => ({
  project, attempted: started.length + skipped.length, complete, record_exists: true,
  started: started.map(k => ({ key: k, session_id: k, label: k, cwd: '/', last_seen: 1, status: 'started', reason: null })),
  skipped: skipped.map(k => ({ key: k, session_id: k, label: k, cwd: '/', last_seen: 1, status: 'skipped', reason: 'no transcript' })),
  failed: [],
})

function mockFetch(routes: Record<string, unknown>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const body = routes[`${method} ${url}`]
    if (body === undefined) return { ok: false, status: 404, json: async () => ({}) } as Response
    if (body === 'ERROR-503') {
      return { ok: false, status: 503, json: async () => ({ detail: 'the agent owner is not running' }) } as Response
    }
    return { ok: true, status: 200, json: async () => body } as Response
  })
}

const listing = {
  projects: [
    { project: 'alpha', entries: 2, last_seen: 10, running: 0 },
    { project: 'beta', entries: 1, last_seen: 5, running: 0 },
  ],
  liveness_known: true,
}
const answer = (project: string, entries: RosterEntry[]) =>
  ({ project, entries, record_exists: true, unreadable: false, liveness_known: true })

const routes = (extra: Record<string, unknown> = {}) => ({
  'GET /api/fleet/roster': listing,
  'GET /api/fleet/roster/alpha': answer('alpha', [entry('alpha', 'A1'), entry('alpha', 'A2')]),
  'GET /api/fleet/roster/beta': answer('beta', [entry('beta', 'B1')]),
  ...extra,
})

const posts = (m: ReturnType<typeof mockFetch>) =>
  m.mock.calls.filter((c: unknown[]) => (c[1] as RequestInit | undefined)?.method === 'POST')

async function openDialog(container: HTMLElement) {
  const chip = await waitFor(() => {
    const el = container.querySelector('[data-fleet-across-open]') as HTMLElement
    expect(el).toBeTruthy()
    return el
  })
  await act(async () => { fireEvent.click(chip) })
}

async function openProject(container: HTMLElement, name: string) {
  const row = container.querySelector(`[data-fleet-across-project="${name}"] [data-fleet-across-toggle]`) as HTMLElement
  await act(async () => { fireEvent.click(row) })
  await waitFor(() => expect(
    container.querySelector(`[data-fleet-across-project="${name}"] [data-fleet-restore-lineages]`)).toBeTruthy())
}

async function tick(label: string) {
  await act(async () => { fireEvent.click(screen.getByLabelText(label)) })
}

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('offerAcross / summariseAcross', () => {
  it('counts only what can start, per project, and drops projects with nothing', () => {
    const o = offerAcross({
      alpha: [entry('alpha', 'A1'), entry('alpha', 'A2', { running: true })],
      beta: [entry('beta', 'B1', { resumable: false })],
    })
    expect(o.parts).toEqual([{ project: 'alpha', keys: ['A1'] }])
    expect(o.restorable).toBe(1)
    expect(o.projects).toBe(1)
  })

  it('a project that could not be asked makes the sum partial, and is not a zero', () => {
    const s = summariseAcross([
      { project: 'alpha', summary: summarise(result('alpha', ['A1'])) },
      { project: 'beta', error: 'the agent owner is not running' },
    ])
    expect(s.complete).toBe(false)
    expect(s.failedProjects).toEqual(['beta'])
    expect(s.started).toBe(1)
    expect(s.headline).not.toMatch(/^All/)
  })

  it('one incomplete project makes the sum partial', () => {
    const s = summariseAcross([
      { project: 'alpha', summary: summarise(result('alpha', ['A1'])) },
      { project: 'beta', summary: summarise(result('beta', [], ['B1'])) },
    ])
    expect(s.complete).toBe(false)
    expect(s.unfinished).toBe(1)
  })

  it('reads as complete only when every part was', () => {
    const s = summariseAcross([
      { project: 'alpha', summary: summarise(result('alpha', ['A1', 'A2'])) },
      { project: 'beta', summary: summarise(result('beta', ['B1'])) },
    ])
    expect(s.complete).toBe(true)
    expect(s.headline).toBe('All 3 restored across 2 projects.')
  })
})

describe('the fleet-wide reopen surface', () => {
  it('draws nothing when no project is recorded, or the listing cannot be read', async () => {
    vi.stubGlobal('fetch', mockFetch({ 'GET /api/fleet/roster': { projects: [] } }))
    const a = render(<RestoreAcrossProjects />)
    await act(async () => {})
    expect(a.container.querySelector('[data-fleet-across]')).toBeNull()
    a.unmount()

    vi.stubGlobal('fetch', mockFetch({}))
    const b = render(<RestoreAcrossProjects />)
    await act(async () => {})
    expect(b.container.querySelector('[data-fleet-across]')).toBeNull()
  })

  it('reads no project record until that project is opened, then only that one', async () => {
    const f = mockFetch(routes())
    vi.stubGlobal('fetch', f)
    const { container } = render(<RestoreAcrossProjects />)
    await openDialog(container)
    expect(container.querySelector('[data-fleet-across-dialog]')).toBeTruthy()
    const perProject = () => f.mock.calls.map(c => c[0] as string).filter(u => /\/api\/fleet\/roster\/./.test(u))
    expect(perProject()).toEqual([])
    await openProject(container, 'alpha')
    expect(perProject()).toEqual(['/api/fleet/roster/alpha'])
  })

  it('one click states both numbers and posts nothing', async () => {
    const f = mockFetch(routes())
    vi.stubGlobal('fetch', f)
    const { container } = render(<RestoreAcrossProjects />)
    await openDialog(container)
    await openProject(container, 'alpha')
    await openProject(container, 'beta')
    await tick('alpha-A1')
    await tick('beta-B1')
    const offer = container.querySelector('[data-fleet-across-selection]') as HTMLElement
    expect(offer.textContent).toContain('Restore 2 selected in 2 projects')
    await act(async () => { fireEvent.click(offer) })
    expect(screen.getByText('Start 2 agents in 2 projects?')).toBeTruthy()
    expect(posts(f)).toEqual([])
  })

  it('a confirmed selection posts exactly each project\'s ticks, and nothing else', async () => {
    const f = mockFetch(routes({
      'POST /api/fleet/roster/alpha/restore': result('alpha', ['A2']),
      'POST /api/fleet/roster/beta/restore': result('beta', ['B1']),
    }))
    vi.stubGlobal('fetch', f)
    const { container } = render(<RestoreAcrossProjects />)
    await openDialog(container)
    await openProject(container, 'alpha')
    await openProject(container, 'beta')
    await tick('alpha-A2')
    await tick('beta-B1')
    await act(async () => { fireEvent.click(container.querySelector('[data-fleet-across-selection]') as HTMLElement) })
    await act(async () => { fireEvent.click(screen.getByText(/yes, restore 2/)) })
    await waitFor(() => expect(container.querySelector('[data-fleet-across-result]')).toBeTruthy())
    const sent = posts(f).map(c => [c[0], JSON.parse((c[1] as RequestInit).body as string)])
    expect(sent).toEqual([
      ['/api/fleet/roster/alpha/restore', { keys: ['A2'] }],
      ['/api/fleet/roster/beta/restore', { keys: ['B1'] }],
    ])
    expect(container.querySelector('[data-fleet-across-result]')!.getAttribute('data-fleet-across-result')).toBe('complete')
  })

  it('a project answered with 503 is named with its error, and the result is partial', async () => {
    const f = mockFetch(routes({
      'POST /api/fleet/roster/alpha/restore': result('alpha', ['A1']),
      'POST /api/fleet/roster/beta/restore': 'ERROR-503',
    }))
    vi.stubGlobal('fetch', f)
    const { container } = render(<RestoreAcrossProjects />)
    await openDialog(container)
    await openProject(container, 'alpha')
    await openProject(container, 'beta')
    await tick('alpha-A1')
    await tick('beta-B1')
    await act(async () => { fireEvent.click(container.querySelector('[data-fleet-across-selection]') as HTMLElement) })
    await act(async () => { fireEvent.click(screen.getByText(/yes, restore 2/)) })
    const res = await waitFor(() => {
      const el = container.querySelector('[data-fleet-across-result]') as HTMLElement
      expect(el).toBeTruthy()
      return el
    })
    expect(res.getAttribute('data-fleet-across-result')).toBe('partial')
    const beta = container.querySelector('[data-fleet-across-part="beta"]') as HTMLElement
    expect(beta.querySelector('[data-fleet-across-part-error]')!.textContent).toContain('the agent owner is not running')
  })

  it('closes on ×, on Escape and on the backdrop — not on a click inside', async () => {
    vi.stubGlobal('fetch', mockFetch(routes()))
    const { container } = render(<RestoreAcrossProjects />)
    const dialog = () => container.querySelector('[data-fleet-across-dialog]') as HTMLElement | null

    await openDialog(container)
    expect(dialog()).toBeTruthy()
    await act(async () => { fireEvent.click(container.querySelector('[data-fleet-across-project="alpha"]') as HTMLElement) })
    expect(dialog()).toBeTruthy()
    await act(async () => { fireEvent.click(dialog()!) })
    expect(dialog()).toBeNull()

    await openDialog(container)
    await act(async () => { fireEvent.keyDown(window, { key: 'Escape' }) })
    expect(dialog()).toBeNull()

    await openDialog(container)
    await act(async () => { fireEvent.click(container.querySelector('[data-fleet-across-close]') as HTMLElement) })
    expect(dialog()).toBeNull()
  })
})
