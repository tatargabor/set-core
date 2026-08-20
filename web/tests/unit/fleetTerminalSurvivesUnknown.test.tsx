/**
 * An open terminal survives a poll the owner did not answer — B-30, second half.
 *
 * Reported by the user on 2026-08-20: *"idonként megall a fleet view
 * connectionget ir és 1 perc mulva all vissza"*. The word `connecting…` is only
 * ever the MOUNT state of `FleetTerminal`, so reading it is proof the pane was
 * torn down and rebuilt — and the teardown came from one unanswered poll:
 * `_owned_by_pid()` returns `None`, every agent arrives `unknown` with no
 * `terminal_label`, and the screen read that absence as an answer.
 *
 * The direction is the whole defect. Filtering on unknown discards a terminal
 * that exists — silently, then re-attaching it at the cost of a 64 KB replay.
 * Keeping it costs nothing when the agent really is gone, because the socket
 * says so itself: the pane renders `closed`, which is a statement, not a gap.
 *
 * Both halves are asserted. A test that only checked "the terminal stays" would
 * pass on a build that never closes one — so the second describe measures the
 * case where the owner DOES answer and says the agent is not held.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, render } from '@testing-library/react'

vi.mock('../../src/components/FleetTerminal', () => ({
  default: ({ label }: { label: string }) => (
    <div data-fleet-terminal={label} data-fleet-own-surface="terminal">screen</div>
  ),
}))

import Fleet from '../../src/pages/Fleet'
import { VIEW_KEY_FOR_TESTS } from '../../src/lib/fleetViewState'
import { offerWithRemembered, rememberTerminalLabels } from '../../src/lib/fleetTerminal'
import { resolveTerminals } from '../../src/lib/fleetViewState'

type Json = Record<string, unknown>

function agent(pid: number, over: Json = {}): Json {
  return {
    pid, name: `a${pid}`, project: 'demo', branch: 'main', session_id: `s${pid}`,
    binding_confirmed: true, sources: ['process'], kind: 'interactive', state: 'quiet',
    tool: null, tool_elapsed_seconds: null, other_tools: [], last_movement_seconds: 5,
    unknown_reason: null, waiting_for: null, declaration_ignored: null,
    population: 'started-here', terminal_label: `t-${pid}`, ...over,
  }
}

const fleet = (agents: Json[], over: Json = {}): Json => ({
  agents: agents.length, working: 0, unknown: 0, owner_reachable: true,
  projects: [{ name: 'demo', root: '/home/x/demo', sources: ['process'], archived: false, agents }],
  quiet_means: 'no outstanding tool call as of the session log’s last flush',
  ...over,
})

function installFetch(answers: unknown[]) {
  let i = 0
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ version: 1, groups: [], parked: [], ungrouped: [], missing: [] }) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [], total_read: 0, truncated: false }) } as Response)
    }
    const body = answers[Math.min(i, answers.length - 1)]
    i += 1
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  }))
}

/** The reader had this terminal open — the memory the screen resolves against. */
function seedOpenTerminal(label: string) {
  localStorage.setItem(VIEW_KEY_FOR_TESTS, JSON.stringify({ demo: { terminals: [label] } }))
}

beforeEach(() => { vi.useRealTimers(); try { localStorage.clear() } catch { /* none */ } })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

const paneFor = (c: HTMLElement, label: string) => c.querySelector(`[data-fleet-terminal="${label}"]`)

describe('an unanswered owner poll must not close an open terminal', () => {
  it('keeps the pane when every agent comes back `unknown`', async () => {
    vi.useFakeTimers()
    seedOpenTerminal('t-11')
    installFetch([
      fleet([agent(11)]),
      // Exactly what the API sends when `_owned_by_pid()` returns None.
      fleet([agent(11, { population: 'unknown', terminal_label: null })], { owner_reachable: false }),
    ])
    const { container } = render(<Fleet />)

    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(paneFor(container, 't-11')).toBeTruthy()

    await act(async () => { await vi.advanceTimersByTimeAsync(5100) })
    expect(paneFor(container, 't-11')).toBeTruthy()
  })

  it('still says out loud that the owner is not answering', async () => {
    vi.useFakeTimers()
    seedOpenTerminal('t-11')
    installFetch([
      fleet([agent(11)]),
      fleet([agent(11, { population: 'unknown', terminal_label: null })], { owner_reachable: false }),
    ])
    const { container } = render(<Fleet />)
    await act(async () => { await vi.advanceTimersByTimeAsync(5100) })
    // Keeping the pane must not make the screen look calm — the cause is stated
    // where the reader is standing, which is what makes the keeping honest.
    expect(container.querySelector('[data-fleet-owner="unreachable"]')).toBeTruthy()
  })
})

describe('an ANSWER still closes it — the other direction', () => {
  it('drops the pane when the owner answers and does not hold the agent', async () => {
    vi.useFakeTimers()
    seedOpenTerminal('t-11')
    installFetch([
      fleet([agent(11)]),
      // The owner answered: this agent is not one of ours. That is a statement,
      // and a statement outranks anything the client remembers.
      fleet([agent(11, { population: 'foreign', terminal_label: null })], { owner_reachable: true }),
    ])
    const { container } = render(<Fleet />)

    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(paneFor(container, 't-11')).toBeTruthy()

    await act(async () => { await vi.advanceTimersByTimeAsync(5100) })
    expect(paneFor(container, 't-11')).toBeNull()
  })
})

describe('the pieces, on their own', () => {
  it('`resolveTerminals` treats null as “nobody could be asked”, not as empty', () => {
    const view = { terminals: ['t-1', 't-2'] }
    expect(resolveTerminals(view, [])).toEqual([])          // answered, holds nothing
    expect(resolveTerminals(view, null)).toEqual(['t-1', 't-2'])  // not answered
    expect(resolveTerminals(view, ['t-2'])).toEqual(['t-2'])      // answered, holds one
  })

  it('the label memory is rebuilt from an answer and frozen without one', () => {
    const answered = rememberTerminalLabels({}, [
      { pid: 1, population: 'started-here', terminal_label: 't-1' },
      { pid: 2, population: 'foreign', terminal_label: null },
    ], true)
    expect(answered).toEqual({ 1: 't-1' })

    // No answer: unchanged, because rebuilding from silence would empty it.
    expect(rememberTerminalLabels(answered, [
      { pid: 1, population: 'unknown', terminal_label: null },
    ], false)).toEqual({ 1: 't-1' })

    // An answer that stops listing pid 1 drops it — the memory cannot go stale.
    expect(rememberTerminalLabels(answered, [
      { pid: 1, population: 'foreign', terminal_label: null },
    ], true)).toEqual({})
  })

  it('the remembered label upgrades ONLY `unknown`, and ONLY while open', () => {
    const unknown = { kind: 'unknown', reason: 'r' } as const
    expect(offerWithRemembered(unknown, 't-1', true)).toEqual({ kind: 'available', label: 't-1' })
    // Closed: no offer is made from memory — an offer that cannot be performed
    // is worse than none, which is this file's own rule for `started-here`.
    expect(offerWithRemembered(unknown, 't-1', false)).toBe(unknown)
    expect(offerWithRemembered(unknown, undefined, true)).toBe(unknown)
    // A statement is never overruled.
    const foreign = { kind: 'foreign', reason: 'r' } as const
    expect(offerWithRemembered(foreign, 't-1', true)).toBe(foreign)
  })
})
