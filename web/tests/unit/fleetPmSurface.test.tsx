/**
 * What the PM frame SHOWS — the half a model test cannot reach.
 *
 * The queue's rules have their own tests, in Python, and they pass against a
 * component that prints one string for two different facts. The gap this file
 * covers is the one `evidence-discipline.md` names: *the check verifies the
 * mechanism and is silent about the result*. A full-screen presentation is the
 * strongest hiding this surface does, so every test here is about something
 * that must remain visible while it hides everything else.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import FleetPm from '../../src/components/FleetPm'
import type { PmSnapshot } from '../../src/lib/fleetPm'
import type { FleetAgent } from '../../src/lib/fleetTypes'

const item = (pid: number, over: Partial<PmSnapshot['presented']> = {}) => ({
  pid, project: 'alpha', label: `a${pid}`, source: 'model',
  blocked_since: Date.now() / 1000 - 120, blockage_point: Date.now() / 1000 - 120,
  presented_count: 1, ...over,
}) as NonNullable<PmSnapshot['presented']>

const snapshot = (over: Partial<PmSnapshot> = {}): PmSnapshot => ({
  enabled: true,
  presented: item(1),
  queued: [item(1)],
  counts: {
    queued: 1, idle: 0, dismissed: 0, not_covered: 0, unclassified: 0,
    judgment_measured: true, judgment_reason: null, counted: true,
  },
  can_go_back: false,
  can_go_forward: false,
  pending_switch: null,
  last_cycle: 1,
  last_error: null,
  cycling: false,
  ...over,
})

const agent = (pid: number, over: Partial<FleetAgent> = {}): FleetAgent => ({
  pid, name: `a${pid}`, project: 'alpha', branch: null, session_id: 's',
  binding_confirmed: true, sources: ['process'], kind: 'interactive', state: 'asking',
  tool: 'AskUserQuestion', tool_elapsed_seconds: 120, other_tools: [],
  last_movement_seconds: 120, unknown_reason: null, waiting_for: null,
  declaration_ignored: null, terminal_label: null,
  ...over,
} as unknown as FleetAgent)

let calls: string[] = []

function serve(snap: PmSnapshot) {
  calls = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? 'GET'} ${url}`)
    return { ok: true, status: 200, json: async () => snap } as unknown as Response
  }))
}

beforeEach(() => { vi.useRealTimers() })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('the frame is the price of the freeze', () => {
  it('counts what is queued behind the presented item', async () => {
    serve(snapshot({ counts: { queued: 7, idle: 12, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: true, judgment_reason: null, counted: true } }))
    render(<FleetPm agents={[agent(1)]} onExit={() => {}} />)
    await waitFor(() => expect(screen.getByText('7')).toBeTruthy())
    // Idle is a SEPARATE number, never summed into the queue: one is work
    // waiting on the reader, the other is agents with nothing to ask.
    expect(screen.getByText('12')).toBeTruthy()
    expect(screen.getByText('idle')).toBeTruthy()
  })

  it('renders an unmeasured judgment as its own fact, not as an empty queue', async () => {
    serve(snapshot({
      presented: null, queued: [],
      counts: { queued: 0, idle: 0, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: false, judgment_reason: 'the judgment pass failed (RuntimeError)', counted: true },
    }))
    const { container } = render(<FleetPm agents={[]} onExit={() => {}} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-unmeasured]')).toBeTruthy())
    // `getByText(/unmeasured/)` matches twice — the banner and the empty
    // state both say it, which is correct and made the query ambiguous.
    // Asserting on the banner's own node is the narrower, honest check.
    expect(container.querySelector('[data-fleet-pm-unmeasured]')!.textContent)
      .toMatch(/unmeasured/)
    // The sentence a reader would otherwise act on by walking away.
    expect(container.textContent).not.toMatch(/Nothing is waiting on you\./)
  })

  it('says plainly when there is genuinely nothing, and only then', async () => {
    serve(snapshot({ presented: null, queued: [], counts: { queued: 0, idle: 3, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: true, judgment_reason: null, counted: true } }))
    render(<FleetPm agents={[]} onExit={() => {}} />)
    await waitFor(() => expect(screen.getByText('Nothing is waiting on you.')).toBeTruthy())
  })

  it('names what a bounded pass did not cover', async () => {
    serve(snapshot({ counts: { queued: 1, idle: 0, dismissed: 0, not_covered: 4, unclassified: 2, judgment_measured: true, judgment_reason: null, counted: true } }))
    render(<FleetPm agents={[agent(1)]} onExit={() => {}} />)
    await waitFor(() => expect(screen.getByText('not covered')).toBeTruthy())
    expect(screen.getByText('unclassified')).toBeTruthy()
  })
})

describe('an agent it cannot present', () => {
  it('says so instead of showing an empty frame', async () => {
    serve(snapshot())
    const { container } = render(<FleetPm agents={[agent(1, { terminal_label: null })]} onExit={() => {}} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-no-terminal]')).toBeTruthy())
    // "This agent has nothing to show" and "this surface cannot show it" are
    // different sentences and lead to different actions.
    expect(screen.getByText(/holds no terminal for this agent/)).toBeTruthy()
    expect(screen.getByText(/it is running, and it is waiting on you/)).toBeTruthy()
  })
})

describe('history', () => {
  it('disables forward at the queue’s own position', async () => {
    serve(snapshot({ can_go_back: true, can_go_forward: false }))
    const { container } = render(<FleetPm agents={[agent(1)]} onExit={() => {}} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-back]')).toBeTruthy())
    expect((container.querySelector('[data-fleet-pm-back]') as HTMLButtonElement).disabled).toBe(false)
    expect((container.querySelector('[data-fleet-pm-forward]') as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('the announced switch', () => {
  it('names where it would go and how long is left', async () => {
    serve(snapshot({ pending_switch: item(2, { project: 'beta', label: 'a2' }) }))
    const { container } = render(<FleetPm agents={[agent(1)]} onExit={() => {}} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-countdown]')).toBeTruthy())
    expect(screen.getByText('beta')).toBeTruthy()
    expect(screen.getByText(/type anything to stay/)).toBeTruthy()
  })

  it('is not shown when the server withholds it — the guard is server-side', async () => {
    // The server returns `pending_switch: null` while the typing window holds,
    // so the client cannot render a countdown it was not offered. This is the
    // assertion that the guard does not depend on the client remembering.
    serve(snapshot({ pending_switch: null }))
    const { container } = render(<FleetPm agents={[agent(1)]} onExit={() => {}} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-presented]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-pm-countdown]')).toBeNull()
  })

  it('sends the seconds since input so the server can decide', async () => {
    serve(snapshot())
    render(<FleetPm agents={[agent(1)]} onExit={() => {}} />)
    await waitFor(() => expect(calls.length).toBeGreaterThan(0))
    // Never typed → the parameter is omitted, which the server reads as the
    // ABSENCE of protection rather than as protection.
    expect(calls[0]).toBe('GET /api/fleet/pm')
  })
})

describe('leaving', () => {
  it('exits without acting on any agent', async () => {
    serve(snapshot())
    let exited = false
    const { container } = render(<FleetPm agents={[agent(1)]} onExit={() => { exited = true }} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-exit]')).toBeTruthy())
    fireEvent.click(container.querySelector('[data-fleet-pm-exit]')!)
    expect(exited).toBe(true)
    expect(calls.some(c => /\/stop|\/agents/.test(c))).toBe(false)
  })
})

describe('a zero nobody produced', () => {
  it('shows a dash, not 0, before the first cycle has finished', async () => {
    // Seen on the running screen: `0 waiting 0 idle` while the first cycle was
    // still in flight. The centre said "Looking at the fleet…", but the counts
    // are what a reader takes in at a glance, and those were defaults rendered
    // as measurements.
    serve(snapshot({
      presented: null, queued: [], cycling: true,
      counts: { queued: 0, idle: 0, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: true, judgment_reason: null, counted: false },
    }))
    const { container } = render(<FleetPm agents={[]} onExit={() => {}} />)
    await waitFor(() => expect(container.textContent).toMatch(/waiting/))
    expect(container.textContent).toMatch(/—\s*waiting/)
    expect(container.textContent).not.toMatch(/\b0\s*waiting/)
    expect(screen.getByText('Looking at the fleet…')).toBeTruthy()
  })

  it('shows a real zero once a cycle has counted', async () => {
    serve(snapshot({
      presented: null, queued: [],
      counts: { queued: 0, idle: 4, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: true, judgment_reason: null, counted: true },
    }))
    const { container } = render(<FleetPm agents={[]} onExit={() => {}} />)
    await waitFor(() => expect(container.textContent).toMatch(/waiting/))
    expect(container.textContent).toMatch(/0\s*waiting/)
    expect(container.textContent).not.toMatch(/—\s*waiting/)
  })
})

describe('not loaded is its own state', () => {
  it('does not claim the judgement is unmeasured before anything has been read', async () => {
    // Seen on the running screen: "the judgement is unmeasured — see above"
    // with nothing above it, because `counts` was undefined on the first
    // render and fell through to that branch. Two fields contradicting each
    // other on one screen — the defect a green suite cannot see.
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => { /* never resolves */ })))
    const { container } = render(<FleetPm agents={[]} onExit={() => {}} />)
    expect(container.textContent).toMatch(/Reading PM mode…/)
    expect(container.textContent).not.toMatch(/unmeasured/)
    expect(container.querySelector('[data-fleet-pm-unmeasured]')).toBeNull()
  })

  it('still says unmeasured when it genuinely is, and shows the banner it points at', async () => {
    serve(snapshot({
      presented: null, queued: [],
      counts: { queued: 0, idle: 0, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: false, judgment_reason: 'the judgment pass failed (RuntimeError)', counted: true },
    }))
    const { container } = render(<FleetPm agents={[]} onExit={() => {}} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-unmeasured]')).toBeTruthy())
    expect(container.textContent).toMatch(/unmeasured — see above/)
  })
})
