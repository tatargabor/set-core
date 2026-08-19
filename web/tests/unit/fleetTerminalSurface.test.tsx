/**
 * What the SCREEN does with `population` — task 8.2 on the tile, and 7.2's data
 * half now that the producer measures `waiting`.
 *
 * Separate from `fleetTerminal.test.ts` on purpose. That file asserts the
 * decision; this one asserts what the reader is shown, and the two differ
 * exactly when the surface is wrong — the same gap `evidence-discipline.md`
 * names as *the check verifies the MECHANISM and is silent about the RESULT*.
 * A correct model rendered through a component that prints one string for both
 * negatives passes every test in that file.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function agent(pid: number, name: string, extra: Json = {}): Json {
  return {
    pid, name, project: null, branch: 'main', session_id: 's', binding_confirmed: true,
    sources: ['process'], kind: 'interactive', state: 'quiet', tool: null,
    tool_elapsed_seconds: null, other_tools: [], last_movement_seconds: 5,
    unknown_reason: null, waiting_for: null, declaration_ignored: null,
    population: 'foreign', terminal_label: null,
    ...extra,
  }
}

const project = (name: string, agents: Json[] = []): Json => ({
  name, root: `/r/${name}`, sources: ['process'], archived: false, agents,
})

function fleet(projects: Json[], extra: Json = {}): Json {
  const all = projects.flatMap(p => (p.agents as Json[]) ?? [])
  return {
    agents: all.length,
    working: all.filter(a => a.state === 'working').length,
    unknown: all.filter(a => a.state === 'unknown').length,
    projects,
    quiet_means: 'no outstanding tool call',
    ...extra,
  }
}

/** A layout that places everything, so nothing renders in the orphan block. */
function layoutFor(names: string[]): Json {
  return {
    version: 1, groups: [], parked: [], parked_missing: [], parked_order: [],
    ungrouped: names, missing: [],
  }
}

function install(agentsBody: Json, names: string[]) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(layoutFor(names)) } as Response)
    }
    if (u.includes('/api/fleet/owner')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ available: true, held: 0 }) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [] }) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(agentsBody) } as Response)
  }))
}

beforeEach(() => { try { localStorage.clear() } catch { /* no storage */ } })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('the tile offers a terminal only where one can exist', () => {
  it('offers one for a framework-started agent, addressed by its label', async () => {
    install(fleet([project('p', [agent(1, 'a1', {
      population: 'started-here', terminal_label: 'p-1120',
    })])]), ['p'])
    const { container } = render(<Fleet />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-terminal-open="p-1120"]')).toBeTruthy()
    })
    expect(container.querySelector('[data-fleet-terminal-absent]')).toBeNull()
  })

  /**
   * The negative half. Task 9.6: a positive-only check passes on a build that
   * offers a terminal for every agent.
   */
  it('offers NONE for an agent the framework did not start, and states the reason', async () => {
    install(fleet([project('p', [agent(1, 'a1', { population: 'foreign' })])]), ['p'])
    const { container } = render(<Fleet />)
    const absent = await waitFor(() => {
      const el = container.querySelector('[data-fleet-terminal-absent]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(absent.getAttribute('data-fleet-terminal-absent')).toBe('foreign')
    // No control at all — not a disabled one, not a hidden one. A control that
    // opens onto nothing is what 8.2 forbids.
    expect(container.querySelector('[data-fleet-terminal-open]')).toBeNull()
    expect(absent.getAttribute('title') ?? '').not.toBe('')
  })

  /**
   * The one the whole `population` field exists for.
   *
   * `unknown` must read differently from `foreign` ON THE SCREEN, not only in
   * the model. Otherwise, for exactly as long as the owner service is restarting,
   * the tile states "there is no terminal" about agents that have one.
   */
  it('says “we do not know” for an unknown population, in different words from “not ours”', async () => {
    install(fleet([project('p', [agent(1, 'a1', { population: 'unknown' })])], {
      owner_reachable: false,
    }), ['p'])
    const { container } = render(<Fleet />)
    const absent = await waitFor(() => {
      const el = container.querySelector('[data-fleet-terminal-absent]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(absent.getAttribute('data-fleet-terminal-absent')).toBe('unknown')

    const text = absent.textContent ?? ''
    expect(text).toContain('nem tudjuk')
    // The refuted rendering, held: printing the foreign wording here is the
    // whole defect, and it looks identical in every structural count.
    expect(text).not.toContain('not the framework’s')
    expect(container.querySelector('[data-fleet-terminal-open]')).toBeNull()
  })

  it('names the unreachable owner ONCE, at the top, not on every row', async () => {
    install(fleet([
      project('p', [agent(1, 'a1', { population: 'unknown' }), agent(2, 'a2', { population: 'unknown' })]),
    ], { owner_reachable: false }), ['p'])
    const { container } = render(<Fleet />)
    await waitFor(() => {
      expect(container.querySelectorAll('[data-fleet-owner="unreachable"]')).toHaveLength(1)
    })
  })

  it('says nothing about the owner when the server does not report it — absent is not false', async () => {
    install(fleet([project('p', [agent(1, 'a1', { population: 'foreign' })])]), ['p'])
    const { container } = render(<Fleet />)
    await waitFor(() => expect(container.querySelector('[data-fleet-terminal-absent]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-owner="unreachable"]')).toBeNull()
  })
})

describe('a waiting agent, now that the producer measures it', () => {
  it('counts it instead of reporting the state as unmeasured', async () => {
    install(fleet([project('p', [agent(1, 'a1', { state: 'waiting', waiting_for: 'input needed' })])], {
      waiting: 1,
    }), ['p'])
    const { container } = render(<Fleet />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-jump="waiting"]')).toBeTruthy()
    })
    expect(container.querySelector('[data-fleet-waiting="unreported"]')).toBeNull()
    // The right-hand panel needs the column's first-selection effect to have
    // run. Waiting on the left column's jump button is NOT the same wait, and
    // asserting straight after it reads the panel one render too early.
    await waitFor(() => expect(container.textContent ?? '').toContain('input needed'))
  })

  it('is still waiting when the runtime did not write down what for', async () => {
    // `waiting_for: null` is a gap in the REASON, never a doubt about the state.
    // Softening the label here would let the calmer reading win.
    install(fleet([project('p', [agent(1, 'a1', { state: 'waiting', waiting_for: null })])], {
      waiting: 1,
    }), ['p'])
    const { container } = render(<Fleet />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-jump="waiting"]')).toBeTruthy()
    })
    await waitFor(() => expect(container.textContent ?? '').toContain('waiting for an answer'))
  })

  it('reports a real zero as a zero, and a missing measurement as missing', async () => {
    // The two must not look alike, and `!data.waiting` would collapse them.
    install(fleet([project('p', [agent(1, 'a1')])], { waiting: 0 }), ['p'])
    const { container } = render(<Fleet />)
    await waitFor(() => expect(container.querySelector('[data-fleet-attention]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-waiting="unreported"]')).toBeNull()
    expect(container.textContent ?? '').toContain('0 waiting for an answer')
  })
})

describe('a declaration the log refuted is shown, not swallowed', () => {
  it('marks the agent and counts the contradiction in the header', async () => {
    install(fleet([project('p', [agent(1, 'a1', {
      state: 'quiet', declaration_ignored: 'working',
    })])], { waiting: 0 }), ['p'])
    const { container } = render(<Fleet />)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-conflict-agent="1"]')).toBeTruthy()
    })
    expect(container.querySelector('[data-fleet-jump="conflict"]')).toBeTruthy()
    expect(container.textContent ?? '').toContain('1 contradicting declarations')
  })

  it('counts from the data: a null field is not a contradiction and an empty string is not one either', async () => {
    install(fleet([project('p', [
      agent(1, 'a1', { declaration_ignored: null }),
      agent(2, 'a2', { declaration_ignored: '' }),
    ])], { waiting: 0 }), ['p'])
    const { container } = render(<Fleet />)
    await waitFor(() => expect(container.querySelector('[data-fleet-attention]')).toBeTruthy())
    expect(container.querySelector('[data-fleet-jump="conflict"]')).toBeNull()
    expect(container.querySelector('[data-fleet-conflict-agent]')).toBeNull()
  })
})
