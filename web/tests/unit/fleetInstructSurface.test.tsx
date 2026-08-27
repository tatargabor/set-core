/**
 * The instruction input and the waiter list as they REACH THE SCREEN.
 *
 * `fleetInstructWaiters.test.ts` asserts the decisions. This asserts the
 * rendering, and the gap between them is the one `evidence-discipline.md` names
 * as *the check verifies the MECHANISM and is silent about the RESULT*: a
 * correct model rendered through a component that prints "sent ✓" for every 200
 * passes every test in that file.
 *
 * The negatives are the point throughout. A test that only checks "the outcome
 * appears" passes on a build that shows `sits-unread` in green next to a tick.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'

import FleetInstruct from '../../src/components/FleetInstruct'
import FleetWaiters from '../../src/components/FleetWaiters'
import type { FleetAgent } from '../../src/lib/fleetTypes'

const agent = (over: Partial<FleetAgent> = {}): FleetAgent => ({
  pid: 42, name: 'a1', project: 'demo', branch: 'main', session_id: 's',
  binding_confirmed: true, sources: ['process'], kind: 'interactive',
  state: 'quiet', tool: null, tool_elapsed_seconds: null, other_tools: [],
  last_movement_seconds: 5, unknown_reason: null,
  instructable: true, seat: 'demo#abc',
  ...over,
})

function answerWith(status: number, body: unknown) {
  const stub = vi.fn(() => Promise.resolve({
    ok: status < 400,
    status,
    json: () => Promise.resolve(body),
  } as Response))
  vi.stubGlobal('fetch', stub)
  return stub
}

async function send(text = 'do the thing') {
  const box = screen.getByRole('textbox')
  fireEvent.change(box, { target: { value: text } })
  fireEvent.click(screen.getByText('send'))
}

beforeEach(() => { vi.useRealTimers() })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('a refusal says the CAUSE, not the failure four times', () => {
  /**
   * Reported 2026-08-19 with a screenshot. The card carried, in this order:
   * *refused* · *the agent does not have it* · *the send was not made*, then
   * *the send did not happen*, then the channel's actual reason, then — in
   * AMBER — a remedy about waiters that could not apply.
   *
   * Four ways of saying it failed, and the one line saying what to DO was the
   * faintest thing on the card while the wrong instruction had the alarm
   * colour. `ui-quality.md`: one visual weight per meaning, and density spent
   * on restatement is density taken from the reason.
   */
  const refused = {
    outcome: 'refused', accepted: false, delivered_to_agent: false, settled: true,
    waiters_here: 0,
    notices: ["`x#abc` is in no room you are in — join one first, then send there."],
  }

  it('does not restate the refusal as a delivery fact', async () => {
    answerWith(200, refused)
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-outcome]')).toBeTruthy())

    // `the agent does not have it` carries information when a send WAS made and
    // is being held. After a refusal it is the first fact restated: nothing was
    // sent, so of course it did not arrive.
    expect(screen.queryByText('the agent does not have it')).toBeNull()
    expect(screen.getByText('the send was not made')).toBeTruthy()
    // And the delivery fact is still MARKED, for anything reading the DOM —
    // suppressed from the eye, not from the record.
    expect(container.querySelector('[data-fleet-delivered]')!.getAttribute('data-fleet-delivered')).toBe('no')
  })

  it('does not offer a remedy for a cause the send never reached', async () => {
    answerWith(200, refused)
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-outcome]')).toBeTruthy())

    expect(
      container.querySelector('[data-fleet-remedy="no-waiter"]'),
      'a refused send has nothing sitting unread — the waiter count measures a '
      + 'condition it never reached',
    ).toBeNull()
  })

  it('still shows the channel’s own words, which are the only actionable thing', async () => {
    answerWith(200, refused)
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-notices]')).toBeTruthy())
    expect(screen.getByText(/join one first/)).toBeTruthy()
    // Not the faintest thing on the card. `fg-ghost` is what it was, and it lost
    // to an amber remedy that could not work.
    expect(container.querySelector('[data-fleet-notices]')!.className).not.toContain('fg-ghost')
  })

  /**
   * The mirror, so the suppression cannot swing too far: an accepted send that
   * nothing is listening for STILL gets the remedy. That is the case the remedy
   * was built for, and losing it would be the false-absence direction.
   */
  it('keeps the remedy when the send WAS made and nothing is listening', async () => {
    answerWith(200, {
      outcome: 'sits-unread', accepted: true, delivered_to_agent: false, settled: true,
      waiters_here: 0,
    })
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-remedy="no-waiter"]')).toBeTruthy())
    expect(screen.getByText('the agent does not have it')).toBeTruthy()
  })
})

describe('a 200 is not a delivery', () => {
  it('says the agent does NOT have it when the message sits unread', async () => {
    answerWith(200, {
      outcome: 'sits-unread', accepted: true, delivered_to_agent: false, settled: true,
      waiters_here: 0,
    })
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()

    await waitFor(() => expect(container.querySelector('[data-fleet-outcome]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-outcome]')!.getAttribute('data-fleet-outcome')).toBe('sits-unread')
    expect(container.querySelector('[data-fleet-delivered]')!.getAttribute('data-fleet-delivered')).toBe('no')
    expect(container.textContent).toMatch(/does not have it/)
    // The negative half: nothing on screen may CLAIM the agent has it.
    //
    // The refuted pattern is recorded because it is the obvious one and it is
    // wrong: `/\bsent\b/` matched the remedy's own explanation ("every
    // instruction sent here sits unread") — a sentence that says the opposite
    // of a delivery. Searching for a word instead of a claim is the same
    // substring-instead-of-structure defect this repository keeps finding.
    expect(container.textContent).not.toMatch(/the agent has it/)
    expect(container.querySelector('[data-fleet-delivered="yes"]')).toBeNull()
  })

  it('says the agent has it only when the producer says so', async () => {
    answerWith(200, {
      outcome: 'at-turn-end', accepted: true, delivered_to_agent: true, settled: true, waiters_here: 1,
    })
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-delivered]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-delivered]')!.getAttribute('data-fleet-delivered')).toBe('yes')
  })

  it('never reads an unknown answer as a quiet yes', async () => {
    answerWith(200, { outcome: 'unknown', accepted: true, delivered_to_agent: false, settled: true, waiters_here: 1 })
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-outcome]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-delivered]')!.getAttribute('data-fleet-delivered')).toBe('no')
  })
})

describe('a hold keeps moving, so the screen does too', () => {
  it('states the hold as a moment with an age, and says nothing re-checked it', async () => {
    answerWith(200, { outcome: 'held', accepted: true, delivered_to_agent: false, settled: false, waiters_here: 1 })
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()

    await waitFor(() => expect(container.querySelector('[data-fleet-outcome-open="held"]')).toBeTruthy())
    const line = container.querySelector('[data-fleet-outcome-open="held"]')!
    expect(line.textContent).toMatch(/as of/)
    expect(line.textContent).toMatch(/re-checked/)
    // A hold is never a delivery.
    expect(container.querySelector('[data-fleet-delivered]')!.getAttribute('data-fleet-delivered')).toBe('no')
  })

  it('does not open a clock for a settled outcome', async () => {
    answerWith(200, { outcome: 'arrives-now', accepted: true, delivered_to_agent: true, settled: true, waiters_here: 1 })
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-outcome]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-outcome-open]')).toBeNull()
  })
})

describe('the remedy goes where the count is zero', () => {
  it('offers it on a measured zero, as a command rather than a button with nothing behind it', async () => {
    answerWith(200, { outcome: 'sits-unread', accepted: true, delivered_to_agent: false, settled: true, waiters_here: 0 })
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-remedy]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-remedy]')!.textContent).toMatch(/sac wait/)
  })

  it('offers nothing when waiters were found', async () => {
    answerWith(200, { outcome: 'arrives-now', accepted: true, delivered_to_agent: true, settled: true, waiters_here: 2 })
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-outcome]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-remedy]')).toBeNull()
  })
})

describe('where there is nothing to type into', () => {
  it('puts the producer’s reason where the input would be, and offers no box', () => {
    const { container } = render(
      <FleetInstruct agent={agent({ instructable: false, reason: 'this session has no seat on the messaging bus' })} />,
    )
    expect(container.querySelector('[data-fleet-instruct]')!.getAttribute('data-fleet-instruct')).toBe('refused')
    expect(screen.queryByRole('textbox')).toBeNull()
    expect(container.textContent).toMatch(/no seat on the messaging bus/)
  })

  it('renders a 409 refusal as an outcome rather than as a generic error', async () => {
    answerWith(409, { detail: {
      outcome: 'refused', accepted: false, delivered_to_agent: false, settled: true,
      reason: 'the bus could not resolve the addressee', waiters_here: 1,
    } })
    const { container } = render(<FleetInstruct agent={agent()} />)
    await send()
    await waitFor(() => expect(container.querySelector('[data-fleet-outcome]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-outcome]')!.getAttribute('data-fleet-outcome')).toBe('refused')
    expect(container.textContent).toMatch(/the send was not made/)
  })

  /** Retyping a lost instruction is the kind of small cruelty that makes a surface untrustworthy. */
  it('keeps the text in the box when the send failed', async () => {
    answerWith(500, { detail: 'boom' })
    render(<FleetInstruct agent={agent()} />)
    await send('keep me')
    await waitFor(() => expect(screen.getByRole('textbox')).toHaveProperty('value', 'keep me'))
  })
})

describe('what an agent declares is shown and never written down', () => {
  /**
   * The confidentiality boundary is PERSISTENCE, not display (`CLAUDE.md`).
   * `declared.focus` and `declared.files` carry a consumer's own words and
   * paths — measured on this machine: one live focus named a client company and
   * an unpaid invoice. Showing them is the point of the abstraction; writing
   * them anywhere is the breach.
   *
   * Held as a test rather than as a comment, because the tempting change is
   * small and looks helpful: remembering the last focus per project so the tile
   * does not flicker on a refresh would put a consumer's sentence into
   * `localStorage`, where it survives the session and the screen.
   */
  it('puts nothing an agent declared into localStorage', async () => {
    const secret = 'ACME-Ltd unpaid invoice 2026-07'
    const { default: Fleet } = await import('../../src/pages/Fleet')
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      const u = String(url)
      if (u.includes('/api/fleet/layout')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ version: 1, groups: [], parked: [], ungrouped: [], missing: [] }) } as Response)
      }
      if (u.includes('/log')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }) } as Response)
      }
      if (u.includes('/api/fleet/waiters')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ measured: true, waiters: [], orphaned: [], orphaned_count: 0 }) } as Response)
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({
        agents: 1, working: 0, unknown: 0, owner_reachable: true,
        quiet_means: 'x',
        projects: [{ name: 'demo', root: '/r', sources: ['process'], archived: false, agents: [{
          ...agent({ pid: 7 }),
          declared: { known: true, focus: secret, phase: 'verify', blocked: true, files: ['/consumer/secret/path.ts'], declared_at: '2026-08-19T10:00:00Z' },
        }] }],
      }) } as Response)
    }))

    localStorage.clear()
    const { container } = render(<Fleet />)
    // It IS rendered — the display half of the boundary.
    await waitFor(() => expect(container.textContent).toContain(secret))

    // Drive the paths that actually WRITE. Without this the assertion below
    // passes on an empty store and measures nothing — the dead-test shape,
    // where a check that cannot fail reads exactly like one that held.
    fireEvent.click(container.querySelector('[data-tile-controls="7"] [data-tile-control="log"]')!)
    fireEvent.click(container.querySelector('[data-tile-controls="7"] [data-tile-control="focus"]')!)

    // Read by KEY rather than by enumerating the Storage object: in jsdom
    // `Object.entries(localStorage)` returns the prototype's methods, so the
    // haystack contained `getItem`/`setItem` and not one byte of stored data.
    // A "does not contain the secret" assertion over THAT string passes on any
    // build, including one that stores the secret — the measurement was looking
    // somewhere the data could never be.
    const stored = localStorage.getItem('set-fleet-view') ?? ''
    // The store was written — so the next three assertions are about real content.
    expect(stored).toContain('logs')

    expect(stored).not.toContain(secret)
    expect(stored).not.toContain('/consumer/secret/path.ts')
    expect(stored).not.toContain('verify')
  })
})

describe('waiters: only an orphan, only one at a time', () => {
  const waiters = (over: Record<string, unknown> = {}) => ({
    measured: true,
    reason: null,
    waiters: [
      { pid: 1, session_id: 'a', cwd: '/p/a', rooms: [], status: 'orphaned', removable: true },
      { pid: 2, session_id: 'b', cwd: '/p/b', rooms: [], status: 'live', removable: false },
      { pid: 3, session_id: null, cwd: '/p/c', rooms: [], status: 'undeterminable', removable: false },
    ],
    orphaned: [1],
    orphaned_count: 1,
    ...over,
  })

  it('offers removal for the orphan and for nothing else', async () => {
    answerWith(200, waiters())
    const { container } = render(<FleetWaiters />)
    await waitFor(() => expect(container.querySelector('[data-fleet-waiters="measured"]')).toBeTruthy())
    fireEvent.click(screen.getByRole('button'))

    await waitFor(() => expect(container.querySelector('[data-fleet-waiter="1"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-waiter-remove="1"]')).toBeTruthy()
    // The two that must never be offered, and they are different from each other.
    expect(container.querySelector('[data-fleet-waiter-remove="2"]')).toBeNull()
    expect(container.querySelector('[data-fleet-waiter-remove="3"]')).toBeNull()
    expect(container.querySelector('[data-fleet-waiter="3"]')!.textContent).toMatch(/undeterminable/)
  })

  it('says removal stops a process, and asks again before doing it', async () => {
    answerWith(200, waiters())
    const { container } = render(<FleetWaiters />)
    await waitFor(() => expect(container.querySelector('[data-fleet-waiters="measured"]')).toBeTruthy())
    fireEvent.click(screen.getByRole('button'))
    await waitFor(() => expect(container.querySelector('[data-fleet-waiter-remove="1"]')).toBeTruthy())

    expect(container.querySelector('[data-fleet-waiter-remove="1"]')!.textContent).toMatch(/stops the process/)
    fireEvent.click(container.querySelector('[data-fleet-waiter-remove="1"]')!)
    await waitFor(() => expect(container.querySelector('[data-fleet-waiter-confirm="1"]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-waiter-confirm="1"]')!.textContent).toMatch(/stops process 1/)
  })

  /**
   * The structural half of "no bulk form": not a missing endpoint, but no
   * affordance that could send more than one — a loop behind one button is the
   * same defect with better manners.
   */
  it('builds no control that would remove more than one', async () => {
    answerWith(200, waiters())
    const { container } = render(<FleetWaiters />)
    await waitFor(() => expect(container.querySelector('[data-fleet-waiters="measured"]')).toBeTruthy())
    fireEvent.click(screen.getByRole('button'))
    await waitFor(() => expect(container.querySelector('[data-fleet-waiter="1"]')).toBeTruthy())

    expect(container.textContent).not.toMatch(/remove all|clean up all|remove orphans/i)
    expect(container.querySelectorAll('[data-fleet-waiter-remove]')).toHaveLength(1)
    expect(container.querySelectorAll('input[type="checkbox"]')).toHaveLength(0)
  })

  /**
   * The false-absence direction, and the one that costs: "no orphans" invites
   * installing another waiter, "we could not look" does not.
   */
  it('never shows a clean list when nothing could be measured', async () => {
    answerWith(200, { measured: false, reason: 'the process table could not be read', waiters: [], orphaned: [], orphaned_count: 0 })
    const { container } = render(<FleetWaiters />)
    await waitFor(() => expect(container.querySelector('[data-fleet-waiters="unmeasured"]')).toBeTruthy())
    expect(container.textContent).toMatch(/could not be measured/)
    expect(container.textContent).not.toMatch(/none orphaned/)
    expect(container.querySelector('[data-fleet-waiter]')).toBeNull()
  })

  it('says a measured zero as a measurement', async () => {
    answerWith(200, { measured: true, reason: null, waiters: [], orphaned: [], orphaned_count: 0 })
    const { container } = render(<FleetWaiters />)
    await waitFor(() => expect(container.querySelector('[data-fleet-waiters="measured"]')).toBeTruthy())
    // A measured zero, said as one: the chip carries `0`, and the sentence
    // that makes it a measurement rather than a silence is on `aria-label`.
    const chip = container.querySelector('[data-fleet-jump="waiters"]')!
    expect(chip.textContent).toContain('0')
    expect(chip.getAttribute('aria-label')).toMatch(/none orphaned/)
  })
})
