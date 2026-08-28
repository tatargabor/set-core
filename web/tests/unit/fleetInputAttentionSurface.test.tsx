/**
 * The input-wait escalation on the SCREEN — the project menu and the tile.
 *
 * `fleetInputAttention.test.ts` asserts the decisions; this asserts that the
 * decisions reach a reader. The two differ exactly when the wiring is wrong,
 * which is the failure this repo has already paid for once: a change whose
 * whole test suite was green while the panel it built rendered empty black.
 *
 * What this file CANNOT do is say whether the result is legible. That is the
 * visual check in the change's task list, and it is not replaced by anything
 * here.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor, within } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'

type Json = Record<string, unknown>

function agent(pid: number, name: string, over: Json = {}): Json {
  return {
    pid, name, project: null, branch: 'main', session_id: `s${pid}`, binding_confirmed: true,
    sources: ['process'], kind: 'interactive', state: 'quiet', tool: null,
    tool_elapsed_seconds: null, other_tools: [], last_movement_seconds: 5,
    unknown_reason: null, attention: 'unmeasured', input_wait_seconds: null,
    runtime_status: null, background_running: false,
    ...over,
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
    input_wait_thresholds: { amber_seconds: 15, red_seconds: 180 },
    ...extra,
  }
}

const LAYOUT = {
  version: 1,
  groups: [{ id: 'g-closed', name: 'closed', collapsed: true, projects: ['hidden'], missing: [] }],
  parked: [],
  ungrouped: ['visible'],
  missing: [],
}

function install(body: Json, layout: Json = LAYOUT) {
  // The layout is STORED here, and a PUT updates it — the collapse toggle is a
  // server-side document, so a harness that echoed the original would silently
  // re-collapse the group and make a test about opening one test nothing.
  let current = layout
  vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/api/fleet/layout')) {
      if (init?.method === 'PUT') {
        const sent = JSON.parse(String(init.body)) as Json
        current = {
          ...current,
          version: Number((current as Json).version ?? 0) + 1,
          groups: (sent.groups as Json[]).map(g => ({ ...g, missing: [], order: (g as Json).projects })),
        }
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(current) } as Response)
    }
    if (u.includes('/log')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ turns: [] }) } as Response)
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)
  }))
}

beforeEach(() => { try { localStorage.clear() } catch { /* no storage */ } })
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

async function column(body: Json, layout: Json = LAYOUT): Promise<HTMLElement> {
  install(body, layout)
  const { container } = render(<Fleet />)
  return await waitFor(() => {
    const el = container.querySelector('[data-fleet-project-column-width]')
    expect(el).toBeTruthy()
    return el as HTMLElement
  })
}

describe('the escalation on the project row', () => {
  it('is unmarked below 15 seconds, amber above it, red past three minutes', async () => {
    const el = await column(fleet([
      project('visible', [
        agent(1, 'fresh', { attention: 'input', input_wait_seconds: 5 }),
      ]),
    ]))
    await waitFor(() => {
      expect(el.querySelector('[data-fleet-input-wait]')).toBeTruthy()
    })
    expect(el.querySelector('[data-fleet-input-wait]')!.getAttribute('data-fleet-input-wait-tone'))
      .toBe('plain')

    cleanup()
    const amber = await column(fleet([
      project('visible', [agent(1, 'a', { attention: 'input', input_wait_seconds: 45 })]),
    ]))
    await waitFor(() => {
      expect(amber.querySelector('[data-fleet-input-wait-tone="amber"]')).toBeTruthy()
    })

    cleanup()
    const red = await column(fleet([
      project('visible', [agent(1, 'a', { attention: 'input', input_wait_seconds: 400 })]),
    ]))
    await waitFor(() => {
      expect(red.querySelector('[data-fleet-input-wait-tone="red"]')).toBeTruthy()
    })
  })

  it('takes the LONGEST wait, so a fresh agent cannot vouch for a stopped one', async () => {
    const el = await column(fleet([
      project('visible', [
        agent(1, 'fresh', { attention: 'input', input_wait_seconds: 5 }),
        agent(2, 'stuck', { attention: 'input', input_wait_seconds: 400 }),
      ]),
    ]))
    await waitFor(() => {
      expect(el.querySelector('[data-fleet-input-wait-tone="red"]')).toBeTruthy()
    })
    expect(el.querySelector('[data-fleet-input-wait]')!.getAttribute('data-fleet-input-wait'))
      .toBe('2')
  })

  it('tints the row itself, not only the dot — the user asked for the card', async () => {
    // *"a projekt kártya háttere lenne színezve, jobban látszik mint az agent
    // darab és perc"* (2026-08-28). A 6 px dot in a column of forty rows is a
    // small target; the row is the thing the eye lands on.
    const el = await column(fleet([
      project('visible', [agent(1, 'a', { attention: 'input', input_wait_seconds: 400 })]),
    ]))
    await waitFor(() => {
      expect(el.querySelector('[data-fleet-row-tone="red"]')).toBeTruthy()
    })
  })

  it('leaves a row under 15 seconds untinted, so a coloured row still means something', async () => {
    const el = await column(fleet([
      project('visible', [agent(1, 'a', { attention: 'input', input_wait_seconds: 5 })]),
    ]))
    await waitFor(() => expect(el.querySelector('[data-fleet-input-wait]')).toBeTruthy())
    expect(el.querySelector('[data-fleet-row-tone]')).toBeNull()
  })

  it('marks a COLLAPSED group, where the reader is standing', async () => {
    install(fleet([
      project('hidden', [agent(9, 'inside', { attention: 'input', input_wait_seconds: 300 })]),
      project('visible'),
    ]))
    const { container } = render(<Fleet />)
    const group = await waitFor(() => {
      const el = container.querySelector('[data-fleet-group="g-closed"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(group.getAttribute('data-fleet-group-collapsed')).toBe('true')
    // The row itself is off screen; the group header carries its escalation.
    expect(within(group).getByTitle(/waiting for you/)).toBeTruthy()
    expect(group.querySelector('[data-fleet-input-wait-tone="red"]')).toBeTruthy()
    // And the closed header carries the tint on itself: with the rows off
    // screen, this bar is the only thing between the wait and a calm screen.
    expect(group.querySelector('[data-fleet-group-tone="red"]')).toBeTruthy()
  })

  it('survives collapsing and re-opening a group', async () => {
    // The regression this exists for: the group header's tone was first written
    // as `open ? null : inputWaitTone(…, useWaitThresholds())` — a hook inside a
    // branch, which throws on the render after the first toggle. Nothing else in
    // the suite toggles a group, so nothing else would have caught it.
    install(fleet([
      project('hidden', [agent(9, 'inside', { attention: 'input', input_wait_seconds: 300 })]),
      project('visible'),
    ]))
    const { container } = render(<Fleet />)
    const group = await waitFor(() => {
      const el = container.querySelector('[data-fleet-group="g-closed"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    const toggle = within(group).getByRole('button', { expanded: false })
    fireEvent.click(toggle)
    await waitFor(() => {
      expect(container.querySelector('[data-fleet-project="hidden"]')).toBeTruthy()
    })
    // Open: the rows carry it themselves, and the header does not repeat it.
    expect(container.querySelector('[data-fleet-row-tone="red"]')).toBeTruthy()
    expect(group.querySelector('[data-fleet-group-tone]')).toBeNull()
    fireEvent.click(within(group).getByRole('button', { expanded: true }))
    await waitFor(() => {
      expect(group.querySelector('[data-fleet-group-tone="red"]')).toBeTruthy()
    })
  })

  it('does not mark a project whose only agent has a command running in the background', async () => {
    const el = await column(fleet([
      project('visible', [agent(1, 'bg', { attention: 'background', background_running: true })]),
    ]))
    await waitFor(() => {
      expect(el.querySelector('[data-fleet-background]')).toBeTruthy()
    })
    // The one case that looks idle and is waiting for nobody.
    expect(el.querySelector('[data-fleet-input-wait]')).toBeNull()
  })

  it('does not mark a project whose agents carry no class at all', async () => {
    const el = await column(fleet([project('visible', [agent(1, 'plain')])]))
    await waitFor(() => expect(el).toBeTruthy())
    expect(el.querySelector('[data-fleet-input-wait]')).toBeNull()
    expect(el.querySelector('[data-fleet-background]')).toBeNull()
  })
})

describe('the agent tile says what would happen if you typed', () => {
  async function tileFor(over: Json): Promise<HTMLElement> {
    install(fleet([project('visible', [agent(1, 'a', over)])]))
    const { container } = render(<Fleet />)
    return await waitFor(() => {
      const el = container.querySelector('[data-fleet-write-effect]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
  }

  it('an idle session is acted on now', async () => {
    const el = await tileFor({ attention: 'input', input_wait_seconds: 30 })
    expect(el.getAttribute('data-fleet-write-effect')).toBe('now')
  })

  it('a working session queues', async () => {
    const el = await tileFor({
      state: 'working', attention: 'working', tool: 'Bash', tool_elapsed_seconds: 3,
    })
    expect(el.getAttribute('data-fleet-write-effect')).toBe('queued')
  })

  it('a session with a background command queues, and is not called waiting', async () => {
    install(fleet([project('visible', [
      agent(1, 'a', { attention: 'background', background_running: true }),
    ])]))
    const { container } = render(<Fleet />)
    const line = await waitFor(() => {
      const el = container.querySelector('[data-fleet-attention="background"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(line.textContent).toMatch(/background command/)
    expect(line.textContent).not.toMatch(/waiting/)
    expect(line.querySelector('[data-fleet-write-effect="queued"]')).toBeTruthy()
  })

  it('an unmeasured session says so rather than claiming nobody is waiting', async () => {
    install(fleet([project('visible', [agent(1, 'a')])]))
    const { container } = render(<Fleet />)
    const line = await waitFor(() => {
      const el = container.querySelector('[data-fleet-attention="unmeasured"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(line.textContent).toMatch(/wait unmeasured/)
    expect(line.querySelector('[data-fleet-wait-tone]')).toBeNull()
  })

  it('carries the duration and its tone on the waiting tile', async () => {
    install(fleet([project('visible', [
      agent(1, 'a', { attention: 'input', input_wait_seconds: 400 }),
    ])]))
    const { container } = render(<Fleet />)
    const line = await waitFor(() => {
      const el = container.querySelector('[data-fleet-attention="input"]')
      expect(el).toBeTruthy()
      return el as HTMLElement
    })
    expect(line.querySelector('[data-fleet-wait-tone="red"]')).toBeTruthy()
    expect(line.textContent).toMatch(/waiting for input/)
  })
})
