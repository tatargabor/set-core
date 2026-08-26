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

/**
 * Restore takes TWO clicks now, and that is the behaviour under test.
 *
 * Reported by the user 2026-08-23 with a screenshot: this control sits in the
 * same header row as `+ start an agent`, and one mis-aimed click started 21
 * agents on a project they were not working on. Nothing undoes that except
 * stopping each one by hand.
 */
async function armAndRun() {
  const offer = await screen.findByRole('button')
  await act(async () => { fireEvent.click(offer) })
  const go = await screen.findByText(/yes, restore/)
  await act(async () => { fireEvent.click(go) })
}

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('the confirmation — one click must not start twenty-one agents', () => {
  /**
   * The load-bearing one. The old control ran on the FIRST click, and the count
   * it printed was the blast radius: "Restore 21 of 53" started twenty-one
   * agents on somebody else's project. This asserts the absence of a POST, not
   * the presence of a dialog — a confirmation that is drawn but not obeyed
   * looks identical from the outside.
   */
  it('sends nothing to the server on the first click', async () => {
    const fetchMock = mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A'), entry('B'), entry('C')]),
      'POST /api/fleet/roster/proj/restore': {
        project: 'proj', attempted: 3, complete: true, record_exists: true,
        started: [outcome('started', null, 'A')], skipped: [], failed: [],
      },
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<RestoreForProject project="proj" />)
    const offer = await screen.findByRole('button')
    await act(async () => { fireEvent.click(offer) })

    const posted = fetchMock.mock.calls.filter(
      (c: unknown[]) => (c[1] as RequestInit | undefined)?.method === 'POST')
    expect(posted).toEqual([])
  })

  it('names the number and the project before it acts', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A'), entry('B'), entry('C')]),
    }))
    render(<RestoreForProject project="proj" />)
    const offer = await screen.findByRole('button')
    await act(async () => { fireEvent.click(offer) })
    // The count is what makes this a decision rather than a reflex.
    expect(await screen.findByText(/Start 3 agents in proj\?/)).toBeTruthy()
    expect(screen.getByText(/yes, restore 3/)).toBeTruthy()
  })

  it('cancelling leaves the offer intact and starts nothing', async () => {
    const fetchMock = mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A'), entry('B')]),
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<RestoreForProject project="proj" />)
    const offer = await screen.findByRole('button')
    await act(async () => { fireEvent.click(offer) })
    const cancel = await screen.findByText(/cancel/)
    await act(async () => { fireEvent.click(cancel) })

    expect(await screen.findByText(/Restore 2 agents/)).toBeTruthy()
    const posted = fetchMock.mock.calls.filter(
      (c: unknown[]) => (c[1] as RequestInit | undefined)?.method === 'POST')
    expect(posted).toEqual([])
  })

  it('the second click is the one that runs it', async () => {
    const fetchMock = mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A')]),
      'POST /api/fleet/roster/proj/restore': {
        project: 'proj', attempted: 1, complete: true, record_exists: true,
        started: [outcome('started', null, 'A')], skipped: [], failed: [],
      },
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<RestoreForProject project="proj" />)
    await armAndRun()

    const posted = fetchMock.mock.calls.filter(
      (c: unknown[]) => (c[1] as RequestInit | undefined)?.method === 'POST')
    expect(posted.length).toBe(1)
  })
})

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
    await armAndRun()

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
    await armAndRun()
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
    await armAndRun()
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
    await armAndRun()
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
    await armAndRun()
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

/**
 * The composition on screen — the primary offer, and the twenty-one it no
 * longer starts.
 *
 * Reported by the user 2026-08-26 with a screenshot of `Restore 9 of 24`. The
 * assertions below are about what is NOT offered: the count on this control is
 * its blast radius, so an offer that is too large is not a cosmetic defect.
 */
const openEntry = (key: string) => ({ ...entry(key), in_last_round: true })
const pastEntry = (key: string, resumable = true) =>
  ({ ...entry(key, resumable), in_last_round: false })

const rosterWithRound = (entries: unknown[], last_round_at: number | null) =>
  ({ ...rosterAnswer(entries), last_round_at })

describe('the primary offer is the last composition', () => {
  it('offers the 3 that were open and not the 21 that were not', async () => {
    const rest = Array.from({ length: 21 }, (_, i) => pastEntry(`P${i}`))
    const fetchMock = mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound(
        [openEntry('A'), openEntry('B'), openEntry('C'), ...rest], Date.now() / 1000 - 600),
    })
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(<RestoreForProject project="proj" />)

    const primary = await waitFor(() => {
      const el = container.querySelector('[data-fleet-restore-composition]')
      if (!el) throw new Error('no composition offer')
      return el
    })
    expect(primary.getAttribute('data-fleet-restore-composition')).toBe('3')
    expect(primary.textContent).toContain('Restore 3 agents')
    // The age, because a composition from ten minutes ago and one from three
    // days ago deserve different confidence.
    expect(primary.textContent).toContain('open 10m ago')
    expect(container.querySelector('[data-fleet-restore-rest]')?.textContent)
      .toContain('21 more recorded here, not open')
  })

  it('posts exactly the composition keys, and no others', async () => {
    const fetchMock = mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound(
        [openEntry('A'), openEntry('B'), pastEntry('OLD')], 1000),
      'POST /api/fleet/roster/proj/restore': {
        project: 'proj', attempted: 2, complete: true, record_exists: true,
        started: [outcome('started', null, 'A'), outcome('started', null, 'B')],
        skipped: [], failed: [],
      },
    })
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(<RestoreForProject project="proj" />)
    const primary = await waitFor(() => {
      const el = container.querySelector('[data-fleet-restore-composition]') as HTMLElement | null
      if (!el) throw new Error('no composition offer')
      return el
    })
    await act(async () => { fireEvent.click(primary) })
    await act(async () => { fireEvent.click(await screen.findByText(/yes, restore 2/)) })

    const posted = fetchMock.mock.calls.find(
      (c: unknown[]) => (c[1] as RequestInit | undefined)?.method === 'POST')
    expect(JSON.parse(String((posted![1] as RequestInit).body))).toEqual({ keys: ['A', 'B'] })
  })

  it('says nothing was open, rather than offering an earlier round', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound(
        [pastEntry('A'), pastEntry('B')], Date.now() / 1000 - 3600),
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    await waitFor(() => expect(
      container.querySelector('[data-fleet-restore-composition-empty]')).toBeTruthy())
    expect(screen.getByText(/Nothing was open here when the fleet was last seen/)).toBeTruthy()
    expect(container.querySelector('[data-fleet-restore-composition]')).toBeNull()
    // The two are still reachable — the record holding more than the
    // composition is information, not clutter.
    expect(container.querySelector('[data-fleet-restore-rest="2"]')).toBeTruthy()
  })

  it('falls back to the whole list when the record cannot say — and says so', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterAnswer([entry('A'), entry('B')]),
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    await waitFor(() => expect(
      container.querySelector('[data-fleet-restore-whole-list="2"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-restore-unknown-composition]')?.textContent)
      .toContain('does not say which of these were open')
    expect(container.querySelector('[data-fleet-restore-composition]')).toBeNull()
  })
})

describe('the rest of the record is picked by hand', () => {
  it('posts only the ticked entries', async () => {
    const fetchMock = mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound(
        [openEntry('A'), pastEntry('OLD1'), pastEntry('OLD2')], 1000),
      'POST /api/fleet/roster/proj/restore': {
        project: 'proj', attempted: 1, complete: true, record_exists: true,
        started: [outcome('started', null, 'OLD2')], skipped: [], failed: [],
      },
    })
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(<RestoreForProject project="proj" />)
    const toggle = await waitFor(() => {
      const el = container.querySelector('[data-fleet-restore-rest-toggle]') as HTMLElement | null
      if (!el) throw new Error('no disclosure')
      return el
    })
    await act(async () => { fireEvent.click(toggle) })

    // Nothing ticked: no act is offered at all. A button promising to restore
    // zero agents is a control that does nothing.
    expect(container.querySelector('[data-fleet-restore-selection]')).toBeNull()

    await act(async () => { fireEvent.click(screen.getByLabelText('proj-OLD2')) })
    const selected = container.querySelector('[data-fleet-restore-selection]') as HTMLElement
    expect(selected.textContent).toContain('Restore 1 selected')
    await act(async () => { fireEvent.click(selected) })
    await act(async () => { fireEvent.click(await screen.findByText(/yes, restore 1/)) })

    const posted = fetchMock.mock.calls.find(
      (c: unknown[]) => (c[1] as RequestInit | undefined)?.method === 'POST')
    expect(JSON.parse(String((posted![1] as RequestInit).body))).toEqual({ keys: ['OLD2'] })
  })

  it('refuses to tick what cannot come back, and says why', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound(
        [openEntry('A'), pastEntry('GONE', false)], 1000),
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    const toggle = await waitFor(() => {
      const el = container.querySelector('[data-fleet-restore-rest-toggle]') as HTMLElement | null
      if (!el) throw new Error('no disclosure')
      return el
    })
    await act(async () => { fireEvent.click(toggle) })
    const box = screen.getByLabelText('proj-GONE') as HTMLInputElement
    expect(box.disabled).toBe(true)
    expect(screen.getByText(/no transcript on disk/)).toBeTruthy()
  })
})

/**
 * The lineage and the peek — B-80, and the question that decides which
 * conversation to bring back.
 */
const past = (key: string, label: string, last_seen: number, over: Record<string, unknown> = {}) =>
  ({ ...entry(key), label, last_seen, in_last_round: false, ...over })

async function openTheRest(container: HTMLElement) {
  const toggle = await waitFor(() => {
    const el = container.querySelector('[data-fleet-restore-rest-toggle]') as HTMLElement | null
    if (!el) throw new Error('no disclosure')
    return el
  })
  await act(async () => { fireEvent.click(toggle) })
}

describe('six entries under one label read as one lineage', () => {
  it('renders one row for the six, and opens to them', async () => {
    const six = Array.from({ length: 6 }, (_, i) => past(`B${i}`, 'proj-bugfix2', 100 - i))
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound([openEntry('A'), ...six, past('S', 'proj-solo', 5)], 1000),
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)

    // Two rows for seven entries: one lineage of six, one single entry.
    expect(container.querySelector('[data-fleet-restore-lineages]')?.getAttribute('data-fleet-restore-lineages'))
      .toBe('2')
    const lineage = container.querySelector('[data-fleet-lineage="proj-bugfix2"]') as HTMLElement
    expect(lineage.textContent).toContain('6 conversations')
    // Before opening, none of the six is a selectable row.
    expect(container.querySelectorAll('[data-fleet-recorded-entry]')).toHaveLength(1)

    await act(async () => {
      fireEvent.click(lineage.querySelector('[data-fleet-lineage-toggle]') as HTMLElement)
    })
    expect(container.querySelectorAll('[data-fleet-recorded-entry]')).toHaveLength(7)
  })

  it('a label with one entry has no group to open', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound([openEntry('A'), past('S', 'proj-solo', 5)], 1000),
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    expect(container.querySelector('[data-fleet-lineage]')).toBeNull()
    expect(container.querySelectorAll('[data-fleet-recorded-entry]')).toHaveLength(1)
  })

  it('selection inside a lineage is per entry, and posts only the ticked one', async () => {
    // There is deliberately no act that restores a lineage as a unit: it would
    // start six conversations of one agent at once, which is the defect the
    // composition offer just removed, coming back through another door.
    const fetchMock = mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound(
        [openEntry('A'), past('B1', 'proj-dup', 200), past('B2', 'proj-dup', 100)], 1000),
      'POST /api/fleet/roster/proj/restore': {
        project: 'proj', attempted: 1, complete: true, record_exists: true,
        started: [outcome('started', null, 'B2')], skipped: [], failed: [],
      },
    })
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    await act(async () => {
      fireEvent.click(container.querySelector('[data-fleet-lineage-toggle]') as HTMLElement)
    })
    const boxes = screen.getAllByLabelText('proj-dup')
    expect(boxes).toHaveLength(2)
    await act(async () => { fireEvent.click(boxes[1]) })
    const selected = container.querySelector('[data-fleet-restore-selection]') as HTMLElement
    await act(async () => { fireEvent.click(selected) })
    await act(async () => { fireEvent.click(await screen.findByText(/yes, restore 1/)) })

    const posted = fetchMock.mock.calls.find(
      (c: unknown[]) => (c[1] as RequestInit | undefined)?.method === 'POST')
    expect(JSON.parse(String((posted![1] as RequestInit).body))).toEqual({ keys: ['B2'] })
  })
})

describe('peeking at a recorded conversation', () => {
  const peekUrl = (key: string) => `GET /api/fleet/roster/proj/${key}/peek?limit=6`
  const turn = (role: string, text: string) =>
    ({ role, timestamp: null, text, thinking: '', tools: [], results: 0 })

  it('shows the last turns, states how many, and starts nothing', async () => {
    const fetchMock = mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound([openEntry('A'), past('OLD', 'proj-old', 5)], 1000),
      [peekUrl('OLD')]: { turns: [turn('user', 'what did we decide'), turn('assistant', 'the gate stays')],
                          total_read: 314, truncated: true, limit: 6 },
    })
    vi.stubGlobal('fetch', fetchMock)
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    await act(async () => {
      fireEvent.click(container.querySelector('[data-fleet-peek-toggle="OLD"]') as HTMLElement)
    })
    await waitFor(() => expect(container.querySelector('[data-fleet-peek="OLD"]')).toBeTruthy())

    expect(screen.getByText(/the gate stays/)).toBeTruthy()
    expect(screen.getByText(/the last 2 turns/)).toBeTruthy()
    // The bound must not read as the whole conversation.
    expect(screen.getByText(/of 314/)).toBeTruthy()
    // A read is a read: nothing was posted, and nothing was armed.
    expect(fetchMock.mock.calls.filter(
      (c: unknown[]) => (c[1] as RequestInit | undefined)?.method === 'POST')).toEqual([])
    expect(screen.queryByText(/yes, restore/)).toBeNull()
  })

  it('renders the stated problem instead of an empty conversation', async () => {
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound([openEntry('A'), past('GONE', 'proj-gone', 5)], 1000),
      [peekUrl('GONE')]: { turns: [], problem: 'no transcript on disk for session GONE' },
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    await act(async () => {
      fireEvent.click(container.querySelector('[data-fleet-peek-toggle="GONE"]') as HTMLElement)
    })
    await waitFor(() => expect(container.querySelector('[data-fleet-peek-problem]')).toBeTruthy())
    expect(screen.getByText(/no transcript on disk/)).toBeTruthy()
    expect(screen.getByText(/nothing to read/)).toBeTruthy()
  })

  it('a read that fails at the transport says so, rather than showing an empty session', async () => {
    // The route is not in the mock at all, so `readJson` answers null — a 404,
    // a proxy, a body that is not JSON. None of those is a conversation with
    // nothing in it.
    vi.stubGlobal('fetch', mockFetch({
      'GET /api/fleet/roster/proj': rosterWithRound([openEntry('A'), past('X', 'proj-x', 5)], 1000),
    }))
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    await act(async () => {
      fireEvent.click(container.querySelector('[data-fleet-peek-toggle="X"]') as HTMLElement)
    })
    await waitFor(() => expect(container.querySelector('[data-fleet-peek-problem]')).toBeTruthy())
    expect(screen.getByText(/could not be read/)).toBeTruthy()
  })
})

/**
 * The recorded list is a DIALOG, and a dialog owes the reader a way out.
 *
 * Reported by the user 2026-08-26, with the screen in front of them: *"funkcióban
 * jó de szerintem ez egy popup screen kellene legyen nagyban és nincs close most
 * pl hogy bezárjam"*. The list had opened inside a header row — as wide as a
 * header row, with a transcript excerpt read through a letterbox — and the only
 * way out was pressing the line that opened it, which is a toggle wearing the
 * clothes of a heading.
 */
describe('the recorded list opens as a dialog that can be closed', () => {
  const withRest = () => mockFetch({
    'GET /api/fleet/roster/proj': rosterWithRound(
      [openEntry('A'), past('OLD1', 'proj-a', 20), past('OLD2', 'proj-b', 10)], 1000),
  })

  it('is a dialog, not a drop-down', async () => {
    vi.stubGlobal('fetch', withRest())
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    const dialog = container.querySelector('[data-fleet-restore-dialog]') as HTMLElement
    expect(dialog).toBeTruthy()
    expect(dialog.getAttribute('role')).toBe('dialog')
    expect(dialog.getAttribute('aria-modal')).toBe('true')
  })

  it('closes on the × — the control whose absence was reported', async () => {
    vi.stubGlobal('fetch', withRest())
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    await act(async () => {
      fireEvent.click(container.querySelector('[data-fleet-restore-dialog-close]') as HTMLElement)
    })
    expect(container.querySelector('[data-fleet-restore-dialog]')).toBeNull()
    // And the trigger is still there, so it can be opened again.
    expect(container.querySelector('[data-fleet-restore-rest-toggle]')).toBeTruthy()
  })

  it('closes on Escape', async () => {
    // A layer that covers the page and can only be dismissed with the mouse is
    // a trap for anyone reading with the keyboard.
    vi.stubGlobal('fetch', withRest())
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    // Asserted PRESENT first. Without it this test passes on a build that has
    // no dialog at all — an absence that was already true, which is a dead test
    // wearing a passing one's clothes.
    expect(container.querySelector('[data-fleet-restore-dialog]')).toBeTruthy()
    await act(async () => { fireEvent.keyDown(window, { key: 'Escape' }) })
    expect(container.querySelector('[data-fleet-restore-dialog]')).toBeNull()
  })

  it('closes on a click outside it, and NOT on a click inside', async () => {
    vi.stubGlobal('fetch', withRest())
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    // Inside first: a click on the list must not throw the reader out mid-choice.
    await act(async () => {
      fireEvent.click(container.querySelector('[data-fleet-restore-lineages]') as HTMLElement)
    })
    expect(container.querySelector('[data-fleet-restore-dialog]')).toBeTruthy()
    await act(async () => {
      fireEvent.click(container.querySelector('[data-fleet-restore-dialog]') as HTMLElement)
    })
    expect(container.querySelector('[data-fleet-restore-dialog]')).toBeNull()
  })

  // A carry-over control rather than a new assertion: it passes on the previous
  // build too, and it is here so the act does not get lost while the list moves
  // into a dialog.
  it('the selection survives nothing being ticked, and the act is still in the dialog', async () => {
    vi.stubGlobal('fetch', withRest())
    const { container } = render(<RestoreForProject project="proj" />)
    await openTheRest(container)
    expect(container.querySelector('[data-fleet-restore-selected]')).toBeTruthy()
    await act(async () => { fireEvent.click(screen.getByLabelText('proj-a')) })
    expect((container.querySelector('[data-fleet-restore-selection]') as HTMLElement).textContent)
      .toContain('Restore 1 selected')
  })
})
