/**
 * The restore surface — what it offers, and what it refuses to claim afterwards.
 *
 * The defect under test is the one a passing suite is worst at catching: a
 * screen that reports a partial restore as a completed one. So the assertions
 * are about the SIX that did not come back, not the three that did.
 */

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { RestoreForProject, RestoreFromEmpty } from '../../src/components/FleetRestore'

const outcome = (status: string, reason: string | null, key: string, label = key) =>
  ({ key, session_id: key, label, cwd: '/p', last_seen: 1, status, reason })

function mockFetch(routes: Record<string, unknown>) {
  return vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const body = routes[`${method} ${url}`]
    if (body === undefined) return { ok: false, status: 404, json: async () => ({}) } as Response
    if (body === 'ERROR-503') {
      return { ok: false, status: 503,
               json: async () => ({ detail: 'the agent owner is not running' }) } as Response
    }
    return { ok: true, status: 200, json: async () => body } as Response
  })
}

const rosterAnswer = (entries: unknown[]) =>
  ({ project: 'proj', entries, record_exists: true, unreadable: false })

const entry = (key: string, resumable = true) => ({
  key, session_id: key, label: `proj-${key}`, cwd: '/p', project: 'proj',
  kind: 'interactive', first_seen: 1, last_seen: 2, session_log: resumable ? '/l' : null,
  resumable, not_resumable_reason: resumable ? null : 'no transcript on disk',
})

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('the offer', () => {
  it('states how many would be attempted before the act is taken', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A'), entry('B'), entry('C')]),
    }))
    render(<RestoreForProject project="proj" />)
    expect(await screen.findByText(/Restore 3 agents/)).toBeTruthy()
  })

  it('says how many of them cannot be resumed, rather than one flattering number', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A'), entry('B', false), entry('C', false)]),
    }))
    render(<RestoreForProject project="proj" />)
    const button = await screen.findByRole('button')
    expect(button.textContent).toContain('1 of 3')
    expect(button.textContent).toContain('cannot be resumed')
  })

  it('offers no control for a project with nothing recorded', async () => {
    vi.stubGlobal('fetch', mockFetch({ 'GET /api/fleet/roster/proj': rosterAnswer([]) }))
    const { container } = render(<RestoreForProject project="proj" />)
    await waitFor(() => expect(container.querySelector('[data-fleet-restore-project]')).toBeNull())
    expect(screen.queryByRole('button')).toBeNull()
  })
})

describe('the result', () => {
  it('shows every entry that did not start, with its reason', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A'), entry('B'), entry('C')]),
      'POST /api/fleet/roster/proj/restore': {
        project: 'proj', attempted: 3, complete: false, record_exists: true,
        started: [outcome('started', null, 'A')],
        skipped: [outcome('skipped', 'session B is bound to a live process', 'B')],
        failed: [outcome('failed', 'scope will not die', 'C')],
      },
    }))
    render(<RestoreForProject project="proj" />)
    const button = await screen.findByRole('button')
    await act(async () => { fireEvent.click(button) })

    expect(await screen.findByText(/1 of 3 restored/)).toBeTruthy()
    expect(screen.getByText(/bound to a live process/)).toBeTruthy()
    expect(screen.getByText(/scope will not die/)).toBeTruthy()
  })

  it('marks a partial result as partial in the DOM, not only in prose', async () => {
    // The marker is what a later reader — or a test, or a screenshot diff —
    // takes away. Prose that says "1 of 3" beside a success-coloured panel is
    // the marker-outranks-the-body defect.
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A'), entry('B')]),
      'POST /api/fleet/roster/proj/restore': {
        project: 'proj', attempted: 2, complete: false, record_exists: true,
        started: [outcome('started', null, 'A')],
        skipped: [outcome('skipped', 'no transcript', 'B')], failed: [],
      },
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    const button = await screen.findByRole('button')
    await act(async () => { fireEvent.click(button) })
    await waitFor(() =>
      expect(container.querySelector('[data-fleet-restore-result="partial"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-restore-result="complete"]')).toBeNull()
    expect(container.querySelector('[data-fleet-restore-unfinished="1"]')).toBeTruthy()
  })

  it('says which agents came back under a name nobody chose', async () => {
    // They started, so they are not in the unfinished list and carry no alarm.
    // But a name the framework invented looks exactly like one the reader gave,
    // and the name is the handle they navigate by.
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A'), entry('B')]),
      'POST /api/fleet/roster/proj/restore': {
        project: 'proj', attempted: 2, complete: true, record_exists: true,
        started: [
          { ...outcome('started', null, 'A'), name_source: 'restored', label_used: 'kept' },
          { ...outcome('started', null, 'B'), name_source: 'derived', label_used: 'proj-restored' },
        ],
        skipped: [], failed: [],
      },
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    const button = await screen.findByRole('button')
    await act(async () => { fireEvent.click(button) })
    await waitFor(() =>
      expect(container.querySelector('[data-fleet-restore-unnamed="1"]')).toBeTruthy())
    expect(screen.getByText(/no name was recorded for it/)).toBeTruthy()
    expect(container.querySelector('[data-fleet-restore-unfinished]')).toBeNull()
    expect(container.querySelector('[data-fleet-restore-result="complete"]')).toBeTruthy()
  })

  it('a clean restore is allowed to read as clean', async () => {
    // The negative control: without this, a component that ALWAYS rendered
    // "partial" would satisfy every test above.
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A')]),
      'POST /api/fleet/roster/proj/restore': {
        project: 'proj', attempted: 1, complete: true, record_exists: true,
        started: [outcome('started', null, 'A')], skipped: [], failed: [],
      },
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    const button = await screen.findByRole('button')
    await act(async () => { fireEvent.click(button) })
    await waitFor(() =>
      expect(container.querySelector('[data-fleet-restore-result="complete"]')).toBeTruthy())
    expect(screen.getByText('All 1 restored.')).toBeTruthy()
    expect(container.querySelector('[data-fleet-restore-unfinished]')).toBeNull()
  })

  it('an unreachable owner is shown as an error, never as zero restored', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A')]),
      'POST /api/fleet/roster/proj/restore': 'ERROR-503',
    }))
    render(<RestoreForProject project="proj" />)
    const button = await screen.findByRole('button')
    await act(async () => { fireEvent.click(button) })
    expect(await screen.findByText(/owner is not running/)).toBeTruthy()
    expect(screen.queryByText(/restored/)).toBeNull()
  })
})

describe('the empty screen — the placement a reboot lands on', () => {
  it('lists every project with a record, with its count and age', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster': { projects: [
        { project: 'alpha', entries: 6, last_seen: Date.now() / 1000 - 7200 },
        { project: 'beta', entries: 1, last_seen: Date.now() / 1000 - 600 },
      ] },
      'GET /api/fleet/roster/alpha': rosterAnswer([entry('A')]),
      'GET /api/fleet/roster/beta': rosterAnswer([entry('B')]),
    }))
    render(<RestoreFromEmpty />)
    expect(await screen.findByText('alpha')).toBeTruthy()
    expect(screen.getByText(/6 agents, last seen 2\.0h ago/)).toBeTruthy()
    expect(screen.getByText(/1 agent, last seen 10m ago/)).toBeTruthy()
  })

  it('renders NOTHING when no project has a record', async () => {
    // A machine that has never recorded anything must see the panel it saw
    // before — an empty box promising history it does not have is worse than
    // no box.
    vi.stubGlobal('fetch', mockFetch({ 'GET /api/fleet/roster': { projects: [] } }))
    const { container } = render(<RestoreFromEmpty />)
    await waitFor(() => expect(container.querySelector('[data-fleet-restore-panel]')).toBeNull())
    expect(container.textContent).toBe('')
  })

  it('says why nothing is running, so the empty screen is not read as data loss', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster': { projects: [{ project: 'alpha', entries: 2, last_seen: 1 }] },
      'GET /api/fleet/roster/alpha': rosterAnswer([entry('A')]),
    }))
    render(<RestoreFromEmpty />)
    expect(await screen.findByText(/a reboot ends every agent/)).toBeTruthy()
    expect(screen.getByText(/conversations are on disk and can be resumed/)).toBeTruthy()
  })
})
