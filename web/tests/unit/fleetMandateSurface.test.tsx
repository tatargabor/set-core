/**
 * The mandate through the rendered screen — the start form, the tile, and the
 * declare dialog.
 *
 * The decisions are tested as functions in `fleetMandate.test.ts`. These tests
 * exist because a rule that is right and never asked answers nothing: they
 * assert what the START REQUEST carries, what the TILE shows, and what the
 * declare dialog says came of it.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import Fleet from '../../src/pages/Fleet'
import { NO_GOAL_NOTE } from '../../src/lib/fleetMandate'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })

const PROJECT = { name: 'proj', root: '/repo', agents: [], sources: ['registry'], archived: false }

function stubFleet(opts: { agents?: any[]; declare?: { status: number; body: any } } = {}) {
  const calls: { started: any[]; declared: any[] } = { started: [], declared: [] }
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url)
    if (u === '/api/fleet/owner') return { ok: true, json: async () => ({ available: true, held: 0 }) } as any
    if (u.includes('/worktrees')) {
      return { ok: true, json: async () => ({ project: 'proj', root: '/repo', locations: [] }) } as any
    }
    if (u === '/api/fleet/mandates' && init?.method === 'POST') {
      calls.declared.push(JSON.parse(String(init.body)))
      const answer = opts.declare ?? { status: 200, body: { id: 'm-1', carrier: true } }
      return { ok: answer.status === 200, status: answer.status, json: async () => answer.body } as any
    }
    if (u === '/api/fleet/agents' && init?.method === 'POST') {
      const body = JSON.parse(String(init.body))
      calls.started.push(body)
      return { ok: true, json: async () => ({ label: body.label }) } as any
    }
    if (u.startsWith('/api/fleet/agents')) {
      const rows = opts.agents ?? []
      return {
        ok: true,
        json: async () => ({
          agents: rows.length, working: 0, unknown: 0, waiting: 0, quiet: rows.length,
          projects: [{ ...PROJECT, agents: rows }],
          measured_at: new Date().toISOString(), quiet_means: 'no outstanding tool call',
        }),
      } as any
    }
    return { ok: false, status: 404, json: async () => ({}) } as any
  }))
  return calls
}

function agentRow(over: Record<string, any> = {}) {
  return {
    pid: 4243, name: 'a1', project: 'proj', branch: 'main', session_id: 's1',
    binding_confirmed: true, sources: ['proc'], kind: 'agent', state: 'quiet',
    tool: null, tool_elapsed_seconds: null, other_tools: [],
    last_movement_seconds: 3, unknown_reason: null, ...over,
  }
}

async function found(selector: string): Promise<HTMLElement> {
  return waitFor(() => {
    const el = document.querySelector(selector)
    if (!el) throw new Error(`no ${selector} yet`)
    return el as HTMLElement
  })
}

async function openStartForm() {
  render(<Fleet />)
  fireEvent.click(await found('[data-fleet-start="offer"]'))
  return found('[data-fleet-start="form"]')
}

describe('the start form', () => {
  it('says an agent started with no goal will have no mandate, and sends none', async () => {
    const calls = stubFleet()
    const form = await openStartForm()
    expect((await found('[data-fleet-start="no-mandate"]')).textContent).toBe(NO_GOAL_NOTE)
    fireEvent.submit(form)
    await waitFor(() => expect(calls.started.length).toBe(1))
    expect('mandate' in calls.started[0]).toBe(false)
  })

  it('carries the goal, the scope and the closing condition to the start request', async () => {
    const calls = stubFleet()
    const form = await openStartForm()
    fireEvent.change(await found('[data-fleet-mandate-goal]'), { target: { value: ' ship the importer ' } })
    // The note about "no mandate" is gone the moment there is a goal.
    await waitFor(() => expect(document.querySelector('[data-fleet-start="no-mandate"]')).toBeNull())
    fireEvent.click(await found('[data-fleet-mandate-more]'))
    const extras = await found('[data-fleet-mandate-extras]')
    fireEvent.change(extras.querySelector('[aria-label="paths this agent is confined to"]')!,
                     { target: { value: 'src/import/\nsrc/shared/' } })
    fireEvent.change(extras.querySelector('[aria-label="what counts as done"]')!,
                     { target: { value: 'tests pass' } })
    fireEvent.submit(form)
    await waitFor(() => expect(calls.started.length).toBe(1))
    expect(calls.started[0].mandate).toEqual({
      goal: 'ship the importer', paths: ['src/import/', 'src/shared/'], done_when: 'tests pass',
    })
  })

  it('refuses to start with a scope and no goal', async () => {
    const calls = stubFleet()
    const form = await openStartForm()
    fireEvent.click(await found('[data-fleet-mandate-more]'))
    const extras = await found('[data-fleet-mandate-extras]')
    fireEvent.change(extras.querySelector('[aria-label="the change this agent works on"]')!,
                     { target: { value: 'importer' } })
    expect((await found('[data-fleet-start="mandate-problem"]')).textContent).toContain('needs a goal')
    fireEvent.submit(form)
    await new Promise(r => setTimeout(r, 30))
    expect(calls.started).toEqual([])
  })

  /**
   * The scope fields FLOAT. In jsdom nothing is laid out, so what can be held
   * here is the mechanism the layout rule rests on: the fields are positioned
   * out of the flow, and they have their own way out. The measured version —
   * the form's own height before and after — belongs to the browser check.
   */
  it('opens the scope fields out of the flow, with a control to close them', async () => {
    stubFleet()
    await openStartForm()
    fireEvent.click(await found('[data-fleet-mandate-more]'))
    const extras = await found('[data-fleet-mandate-extras]')
    expect(extras.className).toMatch(/\babsolute\b/)
    fireEvent.click(extras.querySelector('[data-fleet-mandate-extras-close]')!)
    await waitFor(() => expect(document.querySelector('[data-fleet-mandate-extras]')).toBeNull())
  })
})

describe('the tile', () => {
  it('shows the kind and the goal of a mandate in one line', async () => {
    stubFleet({ agents: [agentRow({
      terminal_label: 'a1', population: 'started-here',
      mandate: { id: 'm-1', kind: 'work', goal: 'ship the importer', delivered: true, source: 'start' },
      mandate_absent: null,
    })] })
    render(<Fleet />)
    const line = await found('[data-fleet-mandate="work"]')
    expect(line.textContent).toContain('work')
    expect(line.querySelector('[data-fleet-mandate-goal]')!.textContent).toBe('ship the importer')
    expect(line.querySelector('[data-fleet-mandate-told]')).toBeNull()
    expect(line.getAttribute('title')).toContain('Instructed to decline')
    expect(document.body.textContent).not.toMatch(/\bblocked from\b|requests are blocked/i)
  })

  it('marks a mandate the agent has not been told yet', async () => {
    stubFleet({ agents: [agentRow({
      terminal_label: 'a1',
      mandate: { id: 'm-1', kind: 'work', goal: 'g', delivered: false, source: 'declared' },
    })] })
    render(<Fleet />)
    expect((await found('[data-fleet-mandate-told="no"]')).textContent).toBe('not told yet')
  })

  it('says "no mandate" with its reason and offers to declare one', async () => {
    stubFleet({ agents: [agentRow({ terminal_label: 'a1', mandate: null, mandate_absent: { reason: 'not-declared' } })] })
    render(<Fleet />)
    const line = await found('[data-fleet-mandate="none"]')
    expect(line.getAttribute('data-fleet-mandate-reason')).toBe('not-declared')
    expect(line.textContent).toContain('no mandate')
    expect(line.textContent).toContain('none declared')
    expect(line.querySelector('[data-fleet-mandate-declare]')).toBeTruthy()
  })

  it('draws an unreadable store as unmeasured, with nothing to declare', async () => {
    stubFleet({ agents: [agentRow({ terminal_label: 'a1', mandate: null, mandate_absent: { reason: 'unmeasured' } })] })
    render(<Fleet />)
    const line = await found('[data-fleet-mandate="unmeasured"]')
    expect(line.textContent).not.toContain('no mandate')
    expect(document.querySelector('[data-fleet-mandate-declare]')).toBeNull()
  })

  it('draws nothing for a payload that carries no mandate fields', async () => {
    stubFleet({ agents: [agentRow({ terminal_label: 'a1' })] })
    render(<Fleet />)
    await found('[data-fleet-tile-head]')
    expect(document.querySelector('[data-fleet-mandate]')).toBeNull()
  })
})

describe('declaring a mandate from the tile', () => {
  async function declare(agent: Record<string, any>, answer?: { status: number; body: any }) {
    const calls = stubFleet({ agents: [agentRow({ mandate: null, ...agent })], declare: answer })
    render(<Fleet />)
    fireEvent.click(await found('[data-fleet-mandate-declare]'))
    const dialog = await found('[data-fleet-mandate-dialog]')
    fireEvent.change(dialog.querySelector('[data-fleet-mandate-goal]')!, { target: { value: 'tidy the docs' } })
    fireEvent.submit(dialog.querySelector('form')!)
    return { calls, dialog }
  }

  it('names a framework-held agent by its label and says it will be told later', async () => {
    const { calls } = await declare({ terminal_label: 'a1', mandate_absent: { reason: 'not-declared' } })
    const outcome = await found('[data-fleet-mandate-outcome]')
    expect(calls.declared).toEqual([{ goal: 'tidy the docs', label: 'a1' }])
    expect(outcome.getAttribute('data-fleet-mandate-outcome')).toBe('told-later')
    expect(outcome.textContent).toContain('next session start')
  })

  it('names a hand-opened agent by its session and says nothing tells it', async () => {
    const { calls } = await declare(
      { terminal_label: null, mandate_absent: { reason: 'not-started-here' } },
      { status: 200, body: { id: 'm-2', carrier: false } },
    )
    const outcome = await found('[data-fleet-mandate-outcome]')
    expect(calls.declared).toEqual([{ goal: 'tidy the docs', session_id: 's1' }])
    expect(outcome.getAttribute('data-fleet-mandate-outcome')).toBe('screen-only')
    expect(outcome.textContent).toContain('Nothing tells this agent')
  })

  it('shows a refusal and records no outcome', async () => {
    const { dialog } = await declare(
      { terminal_label: 'a1', mandate_absent: { reason: 'not-declared' } },
      { status: 409, body: { detail: 'this agent already has mandate m-9' } },
    )
    await waitFor(() => expect(dialog.textContent).toContain('already has mandate m-9'))
    expect(document.querySelector('[data-fleet-mandate-outcome]')).toBeNull()
  })

  it('closes on its own control', async () => {
    stubFleet({ agents: [agentRow({ terminal_label: 'a1', mandate: null, mandate_absent: { reason: 'not-declared' } })] })
    render(<Fleet />)
    fireEvent.click(await found('[data-fleet-mandate-declare]'))
    fireEvent.click((await found('[data-fleet-mandate-dialog-close]')))
    await waitFor(() => expect(document.querySelector('[data-fleet-mandate-dialog]')).toBeNull())
  })
})
