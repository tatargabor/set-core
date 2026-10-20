/**
 * fleet-latest-mode §3 — the mode on the fleet screen.
 *
 * Driven through the page with the same fetch stub the PM toggle's tests use,
 * because every requirement here is about WIRING: which project a tile acts on,
 * what the column shows selected, where the layout is remembered. The pure
 * selection rules are in `fleetLatest.test.ts`.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react'

/* The terminal is replaced by a stub that shows what it was handed and can ask
   for a file — the page's routing of that request is what AC-12 is about, not
   xterm's link detection, which has its own tests. */
vi.mock('../../src/components/FleetTerminal', () => ({
  default: (props: {
    label: string; projectRoot?: string
    onOpenFile?: (f: { path: string }, from: string) => void
  }) => (
    <button
      data-test-terminal={props.label}
      data-test-terminal-root={props.projectRoot ?? ''}
      onClick={() => props.onOpenFile?.({ path: 'src/app.ts' }, 'src/app.ts')}
    >terminal</button>
  ),
}))

import Fleet from '../../src/pages/Fleet'
import { VIEW_KEY_FOR_TESTS } from '../../src/lib/fleetViewState'
import { LATEST_VIEW_KEY } from '../../src/lib/fleetLatest'

type Json = Record<string, unknown>

const agent = (pid: number, project: string, recency: number | null, extra: Json = {}): Json => ({
  pid, name: `a${pid}`, project, branch: 'main', session_id: `s${pid}`,
  binding_confirmed: true, sources: ['process'], kind: 'interactive', state: 'quiet',
  tool: null, tool_elapsed_seconds: null, other_tools: [], last_movement_seconds: 5,
  unknown_reason: null, waiting_for: null, declaration_ignored: null,
  population: 'foreign', terminal_label: null, last_human_input_seconds: recency,
  project_root: `/r/${project}`, cwd: `/r/${project}`, ...extra,
})

function fleet(projects: { name: string; agents: Json[] }[]): Json {
  const all = projects.flatMap(p => p.agents)
  return {
    agents: all.length, working: 0, unknown: 0, waiting: 0, asking: 0, quiet: all.length, unbucketed: 0,
    owner_reachable: true,
    projects: projects.map(p => ({
      name: p.name, root: `/r/${p.name}`, sources: ['process'], archived: false, agents: p.agents,
      checkouts: [`/r/${p.name}`],
    })),
    quiet_means: 'no outstanding tool call',
  }
}

let body: Json = fleet([])
let pmEnabled = false
let calls: string[] = []

function install() {
  calls = []
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    const method = init?.method ?? 'GET'
    calls.push(`${method} ${u}`)
    if (u.includes('/api/fleet/layout')) {
      const names = ((body.projects as Json[]) ?? []).map(p => p.name)
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({
        version: 1, groups: [], parked: [], parked_missing: [], parked_order: [], ungrouped: names, missing: [],
      }) } as Response)
    }
    if (u.includes('/log')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [] }) } as Response)
    if (u.includes('/api/fleet/files')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ files: ['src/app.ts'] }) } as Response)
    }
    if (u.includes('/api/fleet/owner')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ available: true, held: 0 }) } as Response)
    }
    if (u.includes('/api/fleet/pm')) {
      if (method === 'POST') pmEnabled = JSON.parse(String(init?.body ?? '{}')).enabled === true
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({
        enabled: pmEnabled, presented: null, queued: [],
        counts: { queued: 0, idle: 0, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: true, judgment_reason: null, counted: true },
        can_go_back: false, can_go_forward: false, pending_switch: null, last_cycle: 1, last_error: null, cycling: false,
      }) } as Response)
    }
    if (u.includes('/api/fleet/agents')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response)
  }))
}

const three = () => fleet([
  { name: 'p', agents: [agent(1, 'p', 300)] },
  { name: 'q', agents: [agent(2, 'q', 10)] },
  { name: 'r', agents: [agent(3, 'r', null), agent(4, 'r', 60)] },
])

beforeEach(() => {
  body = three()
  pmEnabled = false
  install()
  try { localStorage.clear() } catch { /* no storage */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers() })

const q = (c: HTMLElement, sel: string) => c.querySelector(sel) as HTMLElement | null
const tilePids = (c: HTMLElement) =>
  [...c.querySelectorAll('[data-fleet-tile-head]')].map(e => Number(e.getAttribute('data-fleet-tile-head')))

async function ready() {
  const view = render(<Fleet />)
  await waitFor(() => expect(q(view.container, '[data-fleet-latest-toggle]')).toBeTruthy())
  // The column has picked its first project.
  await waitFor(() => expect(q(view.container, '[data-fleet-area="project"]')).toBeTruthy())
  return view
}

async function turnOn(c: HTMLElement) {
  fireEvent.click(q(c, '[data-fleet-latest-toggle]')!)
  await waitFor(() => expect(q(c, '[data-fleet-area="latest"]')).toBeTruthy())
}

describe('the toggle changes nothing about the agents', () => {
  it('AC-1: turning it on instructs nobody and starts or stops nothing', async () => {
    const { container } = await ready()
    const before = calls.length
    await turnOn(container)
    const writes = calls.slice(before).filter(c => !c.startsWith('GET '))
    expect(writes).toEqual([])
  })

  it('AC-2: turning it off restores the project that was selected', async () => {
    const { container } = await ready()
    const name = q(container, '[data-fleet-area="project"] span')!.textContent
    await turnOn(container)
    fireEvent.click(q(container, '[data-fleet-latest-toggle]')!)
    await waitFor(() => expect(q(container, '[data-fleet-area="project"]')).toBeTruthy())
    expect(q(container, '[data-fleet-area="project"] span')!.textContent).toBe(name)
  })
})

describe('which agents it shows', () => {
  it('AC-3 / AC-4: every project, most recent first, unmeasured last and not called old', async () => {
    const { container } = await ready()
    await turnOn(container)
    await waitFor(() => expect(tilePids(container)).toEqual([2, 4, 1, 3]))
    const none = container.querySelectorAll('[data-fleet-latest-recency="none"]')
    expect(none).toHaveLength(1)
    expect(none[0].textContent).toMatch(/no message from you found/)
    expect(none[0].textContent).not.toMatch(/\d/)
  })

  it('AC-5: the count is honoured', async () => {
    const { container } = await ready()
    await turnOn(container)
    fireEvent.change(q(container, '[data-fleet-latest-count]')!, { target: { value: '2' } })
    await waitFor(() => expect(tilePids(container)).toEqual([2, 4]))
  })

  it('typing a two-digit count does not pass through its first digit', async () => {
    // Measured on the running screen: per-keystroke, "12" went through 1, which
    // dropped every tile but one and refilled them in recency order.
    // Fake timers BEFORE render: the poll interval is created on mount, and one
    // created under real timers is not advanced — the first version of this
    // test never loaded the new answer and passed on the per-keystroke build.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { container } = await ready()
    await turnOn(container)
    fireEvent.change(q(container, '[data-fleet-latest-count]')!, { target: { value: '3' } })
    fireEvent.keyDown(q(container, '[data-fleet-latest-count]')!, { key: 'Enter' })
    await waitFor(() => expect(tilePids(container)).toEqual([2, 4, 1]))
    // Agent 1 becomes the most recent; a pass through count 1 would put it first.
    body = fleet([
      { name: 'p', agents: [agent(1, 'p', 0)] },
      { name: 'q', agents: [agent(2, 'q', 15)] },
      { name: 'r', agents: [agent(3, 'r', null), agent(4, 'r', 65)] },
    ])
    const polls = calls.filter(c => c.includes('/api/fleet/agents')).length
    await act(async () => { vi.advanceTimersByTime(5100) })
    await waitFor(() => expect(calls.filter(c => c.includes('/api/fleet/agents')).length).toBeGreaterThan(polls))
    // The new answer is on screen: agent 1's tile now says it was written just now.
    await waitFor(() => expect(q(container, '[data-fleet-tile-head="1"] [data-fleet-latest-recency]')!.textContent).toMatch(/you: 0s|you: now|you: 0/))
    fireEvent.change(q(container, '[data-fleet-latest-count]')!, { target: { value: '1' } })
    fireEvent.change(q(container, '[data-fleet-latest-count]')!, { target: { value: '12' } })
    await act(async () => { vi.advanceTimersByTime(800) })
    await waitFor(() => expect(tilePids(container)).toEqual([2, 4, 1, 3]))
  })

  it('AC-9: two agents with the same name are told apart by their project', async () => {
    body = fleet([
      { name: 'p', agents: [agent(1, 'p', 5, { name: 'worker' })] },
      { name: 'q', agents: [agent(2, 'q', 6, { name: 'worker' })] },
    ])
    const { container } = await ready()
    await turnOn(container)
    await waitFor(() => expect(container.querySelectorAll('[data-fleet-tile-project]')).toHaveLength(2))
    const named = [...container.querySelectorAll('[data-fleet-tile-project]')].map(e => e.getAttribute('data-fleet-tile-project'))
    expect(named).toEqual(['p', 'q'])
  })
})

describe('placement is stable', () => {
  it('AC-6 / AC-7 on the page: a poll that reorders recency moves nothing; a newcomer takes the oldest slot', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { container } = await ready()
    await turnOn(container)
    fireEvent.change(q(container, '[data-fleet-latest-count]')!, { target: { value: '3' } })
    await waitFor(() => expect(tilePids(container)).toEqual([2, 4, 1]))

    // The reader writes into the third tile: agent 1 is now the most recent.
    body = fleet([
      { name: 'p', agents: [agent(1, 'p', 0)] },
      { name: 'q', agents: [agent(2, 'q', 15)] },
      { name: 'r', agents: [agent(3, 'r', null), agent(4, 'r', 65)] },
    ])
    await act(async () => { vi.advanceTimersByTime(5100) })
    await waitFor(() => expect(calls.filter(c => c.includes('/api/fleet/agents')).length).toBeGreaterThan(1))
    expect(tilePids(container)).toEqual([2, 4, 1])

    // Then into agent 3, which is not shown: it takes agent 4's slot (the oldest).
    body = fleet([
      { name: 'p', agents: [agent(1, 'p', 5)] },
      { name: 'q', agents: [agent(2, 'q', 20)] },
      { name: 'r', agents: [agent(3, 'r', 0), agent(4, 'r', 70)] },
    ])
    await act(async () => { vi.advanceTimersByTime(5100) })
    await waitFor(() => expect(tilePids(container)).toEqual([2, 3, 1]))
  })

  it('AC-8: re-sort orders most recent first', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const { container } = await ready()
    await turnOn(container)
    body = fleet([
      { name: 'p', agents: [agent(1, 'p', 0)] },
      { name: 'q', agents: [agent(2, 'q', 15)] },
      { name: 'r', agents: [agent(3, 'r', null), agent(4, 'r', 65)] },
    ])
    await act(async () => { vi.advanceTimersByTime(5100) })
    await waitFor(() => expect(calls.filter(c => c.includes('/api/fleet/agents')).length).toBeGreaterThan(1))
    expect(tilePids(container)).toEqual([2, 4, 1, 3])
    fireEvent.click(q(container, '[data-fleet-latest-resort]')!)
    await waitFor(() => expect(tilePids(container)).toEqual([1, 2, 4, 3]))
  })
})

describe('the project column and the view memory', () => {
  it('AC-10: no project shows selected, and choosing one leaves the mode', async () => {
    const { container } = await ready()
    expect(container.querySelectorAll('[data-fleet-project-selected]')).toHaveLength(1)
    await turnOn(container)
    expect(container.querySelectorAll('[data-fleet-project-selected]')).toHaveLength(0)
    fireEvent.click(q(container, '[data-fleet-project="r"] button.flex-1')!)
    await waitFor(() => expect(q(container, '[data-fleet-area="project"]')).toBeTruthy())
    expect(q(container, '[data-fleet-area="project"] span')!.textContent).toBe('r')
    expect(q(container, '[data-fleet-latest-toggle]')!.getAttribute('data-fleet-latest-toggle')).toBe('off')
  })

  it("AC-11: the mode's column choice does not leak into a project", async () => {
    const { container } = await ready()
    const projectChoice = q(container, '[data-fleet-columns-choice]')!.getAttribute('data-fleet-columns-choice')
    await turnOn(container)
    fireEvent.click(q(container, '[data-fleet-columns="3"]')!)
    await waitFor(() => expect(q(container, '[data-fleet-columns-choice]')!.getAttribute('data-fleet-columns-choice')).toBe('3'))
    fireEvent.click(q(container, '[data-fleet-latest-toggle]')!)
    await waitFor(() => expect(q(container, '[data-fleet-area="project"]')).toBeTruthy())
    expect(q(container, '[data-fleet-columns-choice]')!.getAttribute('data-fleet-columns-choice')).toBe(projectChoice)
    const stored = JSON.parse(localStorage.getItem(VIEW_KEY_FOR_TESTS) ?? '{}')
    expect(stored[LATEST_VIEW_KEY]?.columns).toBe(3)
  })

  it('offers no per-project controls in the mode: no files, board, start or dock', async () => {
    const { container } = await ready()
    expect(q(container, '[data-fleet-files-open]')).toBeTruthy()
    await turnOn(container)
    expect(q(container, '[data-fleet-files-open]')).toBeNull()
    expect(q(container, '[data-fleet-board-open]')).toBeNull()
    expect(q(container, '[data-fleet-work-cycle-open]')).toBeNull()
  })
})

describe('every tile acts on its own project', () => {
  it("AC-12: a file link from project q's tile resolves against q's root while p was selected", async () => {
    body = fleet([
      { name: 'p', agents: [agent(1, 'p', 300)] },
      { name: 'q', agents: [agent(2, 'q', 10, { population: 'started-here', terminal_label: 'lab-q' })] },
    ])
    // The mode remembers lab-q's terminal as open — its own memory, not p's.
    localStorage.setItem(VIEW_KEY_FOR_TESTS, JSON.stringify({ [LATEST_VIEW_KEY]: { terminals: ['lab-q'] } }))
    const { container } = await ready()
    expect(q(container, '[data-fleet-area="project"] span')!.textContent).toBe('p')
    await turnOn(container)
    const term = await waitFor(() => {
      const el = q(container, '[data-test-terminal="lab-q"]')
      expect(el).toBeTruthy()
      return el!
    })
    expect(term.getAttribute('data-test-terminal-root')).toBe('/r/q')
    fireEvent.click(term)
    await waitFor(() => expect(q(container, '[data-fleet-file-tile="/r/q"]')).toBeTruthy())
    expect(q(container, '[data-fleet-file-tile="/r/p"]')).toBeNull()
  })

  it('AC-13: an enlarged agent with no terminal opens its log', async () => {
    localStorage.setItem(VIEW_KEY_FOR_TESTS, JSON.stringify({ [LATEST_VIEW_KEY]: { logs: [] } }))
    const { container } = await ready()
    await turnOn(container)
    await waitFor(() => expect(q(container, '[data-fleet-opens="2"]')).toBeTruthy())
    const before = calls.filter(c => c.includes('/log')).length
    fireEvent.click(q(container, '[data-fleet-opens="2"]')!)
    await waitFor(() => expect(calls.filter(c => /\/2\/log|pid=2|\/log.*2/.test(c)).length).toBeGreaterThan(0))
    expect(calls.filter(c => c.includes('/log')).length).toBeGreaterThan(before)
    const stored = JSON.parse(localStorage.getItem(VIEW_KEY_FOR_TESTS) ?? '{}')
    expect(stored[LATEST_VIEW_KEY].logs).toContain(2)
  })
})

describe('latest mode and PM mode are mutually exclusive', () => {
  it('AC-14: turning latest mode on turns PM mode off, through the PM switch', async () => {
    const { container } = await ready()
    fireEvent.click(q(container, '[data-fleet-pm-toggle]')!)
    await waitFor(() => expect(q(container, '[data-fleet-pm-toggle]')!.getAttribute('data-fleet-pm-toggle')).toBe('on'))
    await turnOn(container)
    await waitFor(() => expect(q(container, '[data-fleet-pm-toggle]')!.getAttribute('data-fleet-pm-toggle')).toBe('off'))
    expect(calls.filter(c => c === 'POST /api/fleet/pm').length).toBe(2)
    expect(pmEnabled).toBe(false)
  })

  it('AC-15: turning PM mode on turns latest mode off', async () => {
    const { container } = await ready()
    await turnOn(container)
    fireEvent.click(q(container, '[data-fleet-pm-toggle]')!)
    await waitFor(() => expect(q(container, '[data-fleet-latest-toggle]')!.getAttribute('data-fleet-latest-toggle')).toBe('off'))
    expect(q(container, '[data-fleet-pm-toggle]')!.getAttribute('data-fleet-pm-toggle')).toBe('on')
  })

  it('a PM mode already on at the server wins over a remembered latest mode', async () => {
    pmEnabled = true
    localStorage.setItem('set-fleet-latest', JSON.stringify({ on: true, count: 10 }))
    const { container } = render(<Fleet />)
    await waitFor(() => expect(q(container, '[data-fleet-pm-toggle]')?.getAttribute('data-fleet-pm-toggle')).toBe('on'))
    await waitFor(() => expect(q(container, '[data-fleet-latest-toggle]')!.getAttribute('data-fleet-latest-toggle')).toBe('off'))
  })
})
