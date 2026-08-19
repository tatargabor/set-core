/**
 * The fleet's landing-screen states, and the enlarged tile.
 *
 * Three of these tests exist because of the measurement that produced the whole
 * change: the previous landing screen reported absence it had not measured. So
 * the assertions are written against the DIRECTION the screen may not fail in —
 * a screen that has not heard back must not read as a screen that heard back
 * and found nothing — and the negative half is asserted explicitly. A test that
 * only checks "the looking text appears" passes on a build that renders the
 * looking text *and* a count of zero underneath it, which is the defect.
 *
 * Task 7.11 (pre-answer vs answered-empty), 7.12 (the log view leaves room for
 * the timeline without building it), 7.4 (one tile enlarged, the rest as rows).
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function agent(pid: number, name: string, over: Json = {}): Json {
  return {
    pid,
    name,
    project: 'demo',
    branch: 'main',
    session_id: 'abc',
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

function fleet(projects: Json[], over: Json = {}): Json {
  const all = projects.flatMap(p => (p.agents as Json[]) ?? [])
  return {
    agents: all.length,
    working: all.filter(a => a.state === 'working').length,
    unknown: all.filter(a => a.state === 'unknown').length,
    projects,
    quiet_means: 'no outstanding tool call as of the session log’s last flush',
    ...over,
  }
}

const project = (name: string, agents: Json[]): Json => ({
  name,
  root: `/home/x/${name}`,
  sources: ['process'],
  archived: false,
  agents,
})

/**
 * A fetch stub that answers the fleet route from a queue, and the log and
 * arrangement routes flatly.
 *
 * The arrangement is answered OUTSIDE the queue on purpose. It is a second
 * request the screen makes on its own schedule, so letting it consume a queue
 * entry would silently shift every later answer by one — and the tests that
 * depend on the ORDER of answers (a good measurement followed by a failed
 * refresh) would then be measuring something else while still passing or
 * failing for reasons nobody could see.
 */
function installFetch(answers: (() => Promise<unknown>)[], layout: unknown = { version: 1, groups: [], parked: [], ungrouped: [], missing: [] }) {
  let i = 0
  const stub = vi.fn((url: string) => {
    if (String(url).includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(layout) } as Response)
    }
    if (String(url).includes('/log')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }),
      } as Response)
    }
    const next = answers[Math.min(i, answers.length - 1)]
    i += 1
    return next() as Promise<Response>
  })
  vi.stubGlobal('fetch', stub)
  return stub
}

const ok = (body: unknown) => () =>
  Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as unknown as Response)
const never = () => () => new Promise<Response>(() => {})
const fails = (msg: string) => () => Promise.reject(new Error(msg))

beforeEach(() => {
  vi.useRealTimers()
  // Task 7.5 made the enlarged tile PERSISTENT, per project, in localStorage.
  // Without this the memory written by one test decides the starting state of
  // the next one — which is a real leak between tests, and it fails in the
  // direction that looks like a product defect rather than like a dirty
  // fixture: a screen that "starts enlarged" for no visible reason.
  try { localStorage.clear() } catch { /* no storage in this environment */ }
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('task 7.11 — an unfinished answer is not an empty one', () => {
  it('says it is looking, and shows no count at all, before discovery answers', async () => {
    installFetch([never()])
    const { container } = render(<Fleet />)

    expect(container.querySelector('[data-fleet-phase]')?.getAttribute('data-fleet-phase'))
      .toBe('looking')
    expect(screen.getByText(/looking for agents/i)).toBeTruthy()

    // The negative half, and it is the one that matters. A zero is an ANSWER,
    // and no answer has arrived. `\b0\b` rather than a hard-coded "0 agent",
    // because the defect is any rendered zero, not one phrasing of it.
    expect(container.textContent ?? '').not.toMatch(/\b0\b/)
    expect(container.textContent ?? '').not.toMatch(/idle/i)
  })

  it('distinguishes a completed discovery that found nothing from still looking', async () => {
    installFetch([ok(fleet([]))])
    const { container } = render(<Fleet />)

    await waitFor(() => {
      expect(container.querySelector('[data-fleet-phase]')?.getAttribute('data-fleet-phase'))
        .toBe('answered-empty')
    })
    // It reads as a RESULT — the word for the measurement, not for the wait.
    expect(screen.getByText(/discovery ran/i)).toBeTruthy()
    // And it is not the other screen wearing a different colour.
    expect(screen.queryByText(/looking for agents/i)).toBeNull()
  })

  it('keeps the last measurement when a refresh fails, and says how old it is', async () => {
    // Fake timers are installed BEFORE the render, because the poll interval is
    // armed during it: switching afterwards leaves a real interval that no
    // amount of advancing can fire, and the test then measures nothing.
    vi.useFakeTimers()
    installFetch([ok(fleet([project('demo', [agent(1, 'demo-a1')])])), fails('boom')])
    const { container } = render(<Fleet />)

    // `act` around the advance, not `waitFor`: waitFor's own polling is itself
    // driven by timers, so under fake timers it waits for a clock only it can
    // move and the test times out having asserted nothing.
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(screen.getByText('demo-a1')).toBeTruthy()

    await act(async () => { await vi.advanceTimersByTimeAsync(5100) })
    expect(screen.getByText(/the refresh failed/i)).toBeTruthy()
    // The agent is still on screen: trading a stale measurement for NO
    // measurement is the worse of the two on the landing screen.
    expect(screen.getByText('demo-a1')).toBeTruthy()
    expect(container.querySelector('[data-fleet-phase]')?.getAttribute('data-fleet-phase'))
      .toBe('answered')
  })

  it('says it knows nothing — not that there is nothing — when discovery never answered', async () => {
    installFetch([fails('connection refused')])
    const { container } = render(<Fleet />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-phase]')?.getAttribute('data-fleet-phase'))
        .toBe('unreachable')
    })
    expect(container.textContent ?? '').not.toMatch(/\b0\b/)
  })
})

describe('task 7.4 — one tile enlarged, the others still readable as rows', () => {
  const two = fleet([project('demo', [
    agent(1, 'demo-a1'),
    agent(2, 'demo-a2', { state: 'unknown', unknown_reason: 'no session log' }),
  ])])

  it('leaves every other agent as a row carrying its state', async () => {
    installFetch([ok(two)])
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a1')

    expect(container.querySelectorAll('[data-fleet-row]').length).toBe(0)
    // The enlarge control, not the log button. Since 2026-08-19 those are two
    // acts: opening a log no longer hides the other agents (asked for — the
    // grid tiles were too small to read anything in). What 7.4 asserts is
    // unchanged, and it is asserted below; only the control that triggers it
    // moved.
    fireEvent.click(container.querySelector('[data-fleet-enlarged-toggle="1"], [data-tile-controls="1"] [data-tile-control="enlarge"]')!)

    const rows = container.querySelectorAll('[data-fleet-row]')
    expect(rows.length).toBe(1)
    expect(container.querySelector('[data-fleet-enlarged="1"]')).toBeTruthy()
    // The row is not a bare name. An agent in an undetermined state must be
    // readable from the row, or enlarging one tile hides the broken one.
    expect(within(rows[0] as HTMLElement).getByText(/unknown/i)).toBeTruthy()
    expect(within(rows[0] as HTMLElement).getByText('demo-a2')).toBeTruthy()
  })

  it('a ROW keeps its input — enlarging a different tile must not disarm this agent', async () => {
    // The requirement is explicit: *"Under any density, the tile SHALL retain its
    // state and its input"*. The row used to carry identity, state, branch and
    // age and no input at all, so an agent you could instruct became
    // uninstructable purely because you enlarged somebody else's tile — an
    // affordance removed by a layout choice, with nothing on screen to say so.
    installFetch([ok(two)])
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a1')
    expect(container.querySelectorAll('[data-fleet-instruct]').length).toBe(2)

    fireEvent.click(container.querySelector('[data-fleet-enlarged-toggle="1"], [data-tile-controls="1"] [data-tile-control="enlarge"]')!)
    expect(container.querySelector('[data-fleet-row="2"]')).toBeTruthy()
    // Still two, and the second one is INSIDE the row.
    expect(container.querySelectorAll('[data-fleet-instruct]').length).toBe(2)
    expect(container.querySelector('[data-fleet-row="2"] [data-fleet-instruct]')).toBeTruthy()
  })

  it('typing in a row\'s input does not enlarge that row', async () => {
    // The row is a div with a guarded click now, and the guard is the load-bearing
    // half: without it every click inside the input would also select the row, so
    // giving the row an input would have taken away the ability to use it.
    installFetch([ok(two)])
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a1')
    fireEvent.click(container.querySelector('[data-fleet-enlarged-toggle="1"], [data-tile-controls="1"] [data-tile-control="enlarge"]')!)

    const surface = container.querySelector('[data-fleet-row="2"] [data-fleet-instruct]')!
    fireEvent.click(surface)
    expect(container.querySelector('[data-fleet-enlarged="1"]')).toBeTruthy()
    expect(container.querySelector('[data-fleet-enlarged="2"]')).toBeNull()
  })

  it('selects back: clicking a row enlarges that agent instead', async () => {
    installFetch([ok(two)])
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a1')
    fireEvent.click(container.querySelector('[data-fleet-enlarged-toggle="1"], [data-tile-controls="1"] [data-tile-control="enlarge"]')!)

    fireEvent.click(container.querySelector('[data-fleet-row="2"]')!)
    expect(container.querySelector('[data-fleet-enlarged="2"]')).toBeTruthy()
    expect(container.querySelector('[data-fleet-enlarged="1"]')).toBeNull()
    expect(container.querySelector('[data-fleet-row="1"]')).toBeTruthy()
  })
})

describe('task 7.12 — the log view leaves room for the timeline without building it', () => {
  it('offers the conversation, and names the timeline as absent rather than clickable', async () => {
    installFetch([ok(fleet([project('demo', [agent(1, 'demo-a1'), agent(2, 'demo-a2')])]))])
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a1')
    // Two agents on purpose. With exactly one the tile is enlarged by the
    // single-agent default (task 7.5) and its log is already open — so a
    // one-agent fixture would assert the tabs through a path the reader never
    // takes, and would break again the next time that default moves.
    fireEvent.click(container.querySelectorAll('[data-tile-control="log"]')[0])

    const conversation = container.querySelector('[data-log-tab="conversation"]')!
    expect(conversation.getAttribute('aria-selected')).toBe('true')

    const timeline = container.querySelector('[data-log-tab="timeline"]')!
    // Not a control that opens onto nothing, and not silence either: the
    // reader must be able to tell "not built" from "nothing to show".
    expect(timeline.getAttribute('aria-disabled')).toBe('true')
    expect(timeline.tagName).not.toBe('BUTTON')
    expect(timeline.textContent).toMatch(/not built yet/i)
  })
})

/**
 * One claim, one weight — found by LOOKING at the live screen on 2026-08-19,
 * where a tile carried `⚠ says it is blocked` in its header and `says: blocked`
 * one line below it.
 *
 * `fleetInstructWaiters.test.ts` asserts the decision; this asserts that the
 * tile actually asks it with the real answer. Both are needed, and a mutation
 * proved it: hard-coding `blockShown={true}` at the call site left the decision
 * tests entirely green while taking the block off every `waiting` tile.
 */
describe('a declared block is said once', () => {
  const blocked = { known: true, blocked: true, phase: 'blocked', focus: 'the merge queue' }

  it('drops the phase where the header is already shouting it', async () => {
    installFetch([ok(fleet([project('demo', [
      agent(1, 'demo-a1', { state: 'quiet', declared: blocked }),
      agent(2, 'demo-a2'),
    ])]))])
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a1')
    expect(container.querySelector('[data-fleet-declared-blocked="1"]')).toBeTruthy()
    expect(container.querySelector('[data-fleet-declared-phase="blocked"]')).toBeNull()
    // The focus is untouched — only the word that was doubled goes.
    expect(screen.getByText('the merge queue')).toBeTruthy()
  })

  /**
   * The direction that matters. Beside `waiting` the header marker is
   * deliberately absent (a block there is a reason, not a surprise), so the
   * phase is the only thing carrying it and must stay.
   */
  it('keeps the phase where nothing else on the tile carries the block', async () => {
    installFetch([ok(fleet([project('demo', [
      agent(1, 'demo-a1', { state: 'waiting', declared: blocked }),
      agent(2, 'demo-a2'),
    ])]))])
    const { container } = render(<Fleet />)
    await screen.findByText('demo-a1')
    expect(container.querySelector('[data-fleet-declared-blocked="1"]')).toBeNull()
    expect(container.querySelector('[data-fleet-declared-phase="blocked"]')).toBeTruthy()
  })
})
