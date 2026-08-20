/**
 * What the PM strip SHOWS — the half a model test cannot reach.
 *
 * The queue's rules have their own tests, in Python, and they pass against a
 * component that prints one string for two different facts. The gap this file
 * covers is the one `evidence-discipline.md` names: *the check verifies the
 * mechanism and is silent about the result*.
 *
 * ⚠ Rewritten 2026-08-20 after the user looked at the first build and rejected
 * its shape — it was a full-screen overlay, and it replaced the fleet screen
 * instead of driving it. The strip carries the same facts; what it must NOT do
 * any more is be the whole screen.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import FleetPm from '../../src/components/FleetPm'
import type { PmSnapshot } from '../../src/lib/fleetPm'

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

let calls: string[] = []

function serve(snap: PmSnapshot) {
  calls = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? 'GET'} ${url}`)
    // The PM snapshot is NOT the answer to every URL. The presented agent's log
    // is a second endpoint, and a stub that hands the snapshot to it makes the
    // log throw rather than be empty — which would fail these tests for a
    // reason the product does not have.
    if (String(url).includes('/log')) {
      return { ok: true, status: 200, json: async () => ({ turns: [] }) } as unknown as Response
    }
    return { ok: true, status: 200, json: async () => snap } as unknown as Response
  }))
}

beforeEach(() => { vi.useRealTimers() })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('the frame is the price of the freeze', () => {
  it('counts what is queued behind the presented item', async () => {
    serve(snapshot({ counts: { queued: 7, idle: 12, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: true, judgment_reason: null, counted: true } }))
    render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
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
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-unmeasured]')).toBeTruthy())
    // `getByText(/unmeasured/)` matches twice — the banner and the empty
    // state both say it, which is correct and made the query ambiguous.
    // Asserting on the banner's own node is the narrower, honest check.
    expect(container.querySelector('[data-fleet-pm-unmeasured]')!.textContent)
      .toMatch(/unmeasured/)
    // The sentence a reader would otherwise act on by walking away.
    expect(container.textContent).not.toMatch(/nothing is waiting on you/i)
  })

  it('says plainly when there is genuinely nothing, and only then', async () => {
    serve(snapshot({ presented: null, queued: [], counts: { queued: 0, idle: 3, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: true, judgment_reason: null, counted: true } }))
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.textContent).toMatch(/nothing is waiting on you/i))
  })

  it('names what a bounded pass did not cover', async () => {
    serve(snapshot({ counts: { queued: 1, idle: 0, dismissed: 0, not_covered: 4, unclassified: 2, judgment_measured: true, judgment_reason: null, counted: true } }))
    render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(screen.getByText('not covered')).toBeTruthy())
    expect(screen.getByText('unclassified')).toBeTruthy()
  })
})

describe('history', () => {
  it('disables forward at the queue’s own position', async () => {
    serve(snapshot({ can_go_back: true, can_go_forward: false }))
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-back]')).toBeTruthy())
    expect((container.querySelector('[data-fleet-pm-back]') as HTMLButtonElement).disabled).toBe(false)
    expect((container.querySelector('[data-fleet-pm-forward]') as HTMLButtonElement).disabled).toBe(true)
  })
})

describe('the announced switch', () => {
  it('names where it would go and how long is left', async () => {
    serve(snapshot({ pending_switch: item(2, { project: 'beta', label: 'a2' }) }))
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-countdown]')).toBeTruthy())
    expect(screen.getByText('beta')).toBeTruthy()
    expect(screen.getByText(/type anything to stay/)).toBeTruthy()
  })

  it('is not shown when the server withholds it — the guard is server-side', async () => {
    // The server returns `pending_switch: null` while the typing window holds,
    // so the client cannot render a countdown it was not offered. This is the
    // assertion that the guard does not depend on the client remembering.
    serve(snapshot({ pending_switch: null }))
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-presented]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-pm-countdown]')).toBeNull()
  })

  it('sends the seconds since input so the server can decide', async () => {
    serve(snapshot())
    render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
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
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => { exited = true }} lastInputAt={null} />)
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
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.textContent).toMatch(/waiting/))
    expect(container.textContent).toMatch(/—\s*waiting/)
    expect(container.textContent).not.toMatch(/\b0\s*waiting/)
    expect(container.textContent).toMatch(/looking at the fleet/i)
  })

  it('shows a real zero once a cycle has counted', async () => {
    serve(snapshot({
      presented: null, queued: [],
      counts: { queued: 0, idle: 4, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: true, judgment_reason: null, counted: true },
    }))
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
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
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    expect(container.textContent).toMatch(/reading PM mode…/i)
    expect(container.textContent).not.toMatch(/unmeasured/)
    expect(container.querySelector('[data-fleet-pm-unmeasured]')).toBeNull()
  })

  it('still says unmeasured when it genuinely is, and shows the banner it points at', async () => {
    serve(snapshot({
      presented: null, queued: [],
      counts: { queued: 0, idle: 0, dismissed: 0, not_covered: 0, unclassified: 0, judgment_measured: false, judgment_reason: 'the judgment pass failed (RuntimeError)', counted: true },
    }))
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-unmeasured]')).toBeTruthy())
    // The strip's banner sits BELOW its row, so the sentence no longer says
    // "see above" — it says what happened, where the reader is standing.
    expect(container.querySelector('[data-fleet-pm-unmeasured]')!.textContent)
      .toMatch(/unmeasured/)
  })
})

describe('the mode names itself', () => {
  it('says what the reader is in, because the toggle is underneath it', async () => {
    // Asked for on 2026-08-20 — *"hol van a gomb, nem találom?"* — and the
    // question IS the finding: a full-screen overlay hides the control that
    // opened it, so the screen has to say what it is.
    serve(snapshot())
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-label]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-pm-label]')!.textContent).toMatch(/PM mode/)
  })

  it('labels the way out in words, not only in a tooltip', async () => {
    // A ✕ at a glance reads as "close this panel", not "leave the mode", and a
    // tooltip is not a label — nobody hovers to find out how to get back.
    serve(snapshot())
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm-exit]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-pm-exit]')!.textContent).toMatch(/exit/)
  })
})

describe('the strip drives the screen, it does not replace it', () => {
  it('asks the page to show the presented agent, once per change', async () => {
    // The correction this component was rebuilt for. It used to BE the screen;
    // now it names which agent the screen should show. Once per change, because
    // repeating the jump on every poll would fight the reader's own navigation
    // four times a minute.
    serve(snapshot())
    const shown: number[] = []
    render(<FleetPm onPresent={pid => shown.push(pid)} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(shown).toEqual([1]))
    await new Promise(r => setTimeout(r, 30))
    expect(shown).toEqual([1])
  })

  it('renders no full-screen container of its own', async () => {
    // The shape the user rejected: *"azt hittem ugyanúgy meghagyja a felületet
    // … ehelyett full screen használhatatlant csinált."*
    serve(snapshot())
    const { container } = render(<FleetPm onPresent={() => {}} onExit={() => {}} lastInputAt={null} />)
    await waitFor(() => expect(container.querySelector('[data-fleet-pm="on"]')).toBeTruthy())
    const root = container.querySelector('[data-fleet-pm="on"]') as HTMLElement
    expect(root.className).not.toMatch(/fixed/)
    expect(root.className).not.toMatch(/inset-0/)
  })
})
