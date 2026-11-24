/**
 * Automatic answers on the fleet header (fleet-auto-answer, task 4.2): the pure rules, the
 * closed control's count, the panel's rows and its cancel, and the mark on the tile.
 * Whether the panel moves anything on the screen is a MEASUREMENT, taken in the browser
 * (`tests/e2e/fleet-auto-answer.spec.ts`), not here.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react'

import FleetAutoAnswer, { FleetAutoAnswerMark } from '../../src/components/FleetAutoAnswer'
import {
  agentName, autoMode, autoTitle, countdown, kindLabel, matched, outcomeLabel, parseAutoAnswerState, parseDecisions,
  pendingFor, publishAgentNames, publishPending, questionBody, shownChoice, tierLabel, wiringCommands,
} from '../../src/lib/fleetAutoAnswer'

afterEach(() => { cleanup(); vi.unstubAllGlobals(); publishPending([]); publishAgentNames({}) })

const PENDING = {
  id: 'relay-47f1763f-0123456789ab', key: 'Q1', session_id: 'sess-1', agent: 'proj · 47f1763f', project: 'proj',
  kind: 'ask', question: 'Which colour?', choice: 'TEAL', tier: 'decided', confidence: 0.9, seconds_left: 42,
  references: [{ kind: 'operator', quote: 'TEAL it is, always', checked: true }],
}
const STATE = { enabled: true, wired: true, forward: true, window_s: 60, likely_min: 0.8, pending: [PENDING], pending_count: 1 }
const DECISIONS = { decisions: [
  { ts: Date.now() / 1000 - 30, id: 'a', key: 'Q1', agent: 'proj · a', kind: 'ask', question: 'Q one?', choice: 'Yes',
    tier: 'likely', confidence: 0.85, outcome: 'overtaken', reason: '', human_answer: 'Yes', references: [] },
  { ts: Date.now() / 1000 - 90, id: 'b', key: 'Q1', agent: 'proj · b', kind: 'ask', question: 'Push?', choice: 'Yes',
    tier: 'decided', confidence: 0.9, outcome: 'excluded', reason: 'outward step: publish', human_answer: 'No', references: [] },
] }

describe('the wiring hint names what is configured (B-236)', () => {
  it('with no relay command, asks for one line and no placeholder', () => {
    const h = wiringCommands('')
    expect(h).toBe('set-config set question_relay.command set-auto-answer')
    expect(h).not.toContain('forward_command')
  })
  it('with a relay command, moves the REAL value behind the decider, shell-quoted', () => {
    const h = wiringCommands("my-bridge --to 'ops'")
    expect(h.split('\n')).toEqual([
      "set-config set auto_answer.forward_command 'my-bridge --to '\\''ops'\\'''",
      'set-config set question_relay.command set-auto-answer',
    ])
    expect(h).not.toContain('<the current')
  })
  it('parses the field, and an old server without it reads as none set', () => {
    expect(parseAutoAnswerState({ ...STATE, relay_command: 'x' })!.relay_command).toBe('x')
    expect(parseAutoAnswerState(STATE)!.relay_command).toBe('')
  })
})

describe('parsing — a widget must degrade, never take the page down', () => {
  it('refuses a payload without the fields it renders', () => {
    expect(parseAutoAnswerState(null)).toBeNull()
    expect(parseAutoAnswerState({ enabled: true })).toBeNull()
    expect(parseAutoAnswerState({ pending: [] })).toBeNull()
    expect(parseDecisions({ nope: 1 })).toBeNull()
  })
  it('keeps the well-formed rows and drops the rest', () => {
    const s = parseAutoAnswerState({ ...STATE, pending: [PENDING, { id: 'x' }, null] })!
    expect(s.pending.map(p => p.id)).toEqual([PENDING.id])
    expect(parseDecisions({ decisions: [...DECISIONS.decisions, { nope: 1 }] })!.map(d => d.id)).toEqual(['a', 'b'])
  })
})

describe('the words', () => {
  it('names the modes, including on-but-not-wired, and unread is not off', () => {
    expect(autoMode(null)).toBe('unread')
    expect(autoMode(parseAutoAnswerState({ ...STATE, enabled: false }))).toBe('off')
    expect(autoMode(parseAutoAnswerState({ ...STATE, wired: false }))).toBe('on-not-wired')
    expect(autoTitle(parseAutoAnswerState({ ...STATE, wired: false }))).toContain('nothing is decided')
    expect(autoTitle(null, 'HTTP 500')).toContain('unreadable')
    expect(autoTitle(parseAutoAnswerState(STATE))).toContain('1 proposal(s) will be written')
  })
  it('tiers, outcomes, matches and countdowns', () => {
    expect(tierLabel('likely', 0.8)).toBe('likely 0.80')
    expect(tierLabel('decided', 0.9)).toBe('decided')
    expect(outcomeLabel('written')).toEqual({ text: 'written', tone: 'loud' })
    expect(outcomeLabel('excluded').tone).toBe('warn')
    const [a, b] = parseDecisions(DECISIONS)!
    expect(matched(a)).toBe(true)
    expect(matched(b)).toBe(false)
    expect(matched({ ...a, human_answer: null })).toBeNull()
    expect(countdown(42.4)).toBe('42s')
    expect(countdown(125)).toBe('2m05s')
    expect(countdown(-3)).toBe('0s')
    expect(countdown(null)).toBe('?')
  })
})

function stubFetch(state: unknown = STATE, onPost?: (url: string, body: unknown) => unknown) {
  const calls: { url: string; method: string; body: unknown }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    const body = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ url, method, body })
    let payload: unknown = state
    if (url.startsWith('/api/fleet/auto-answer/decisions')) payload = DECISIONS
    else if (method === 'POST') payload = onPost ? onPost(url, body) : state
    return { ok: true, status: 200, json: async () => payload } as Response
  }))
  return calls
}

describe('the header control and its panel', () => {
  it('AC-20: the closed control carries the pending count', async () => {
    stubFetch()
    const { container } = render(<FleetAutoAnswer />)
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-pending-count="1"]')).not.toBeNull())
    expect(container.querySelector('[data-fleet-auto-toggle="on"]')).not.toBeNull()
    expect(container.querySelector('[data-fleet-auto-panel]')).toBeNull()
  })

  it('a failed read shows unread, never a calm zero', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 500, json: async () => ({}) }) as Response))
    const { container } = render(<FleetAutoAnswer />)
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-toggle="unread"]')).not.toBeNull())
    expect(container.querySelector('[data-fleet-auto-toggle]')!.getAttribute('title')).toContain('unreadable')
  })

  it('opens a floating panel with the proposal, its source, and the recent decisions', async () => {
    stubFetch()
    const { container, getByText } = render(<FleetAutoAnswer />)
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-pending-count]')).not.toBeNull())
    fireEvent.click(container.querySelector('[data-fleet-auto-toggle]')!)
    const panel = container.querySelector('[data-fleet-auto-panel]')!
    expect(panel.className).toContain('fixed')
    expect(panel.querySelector('[data-fleet-auto-row]')!.textContent).toContain('TEAL')
    expect(getByText('“TEAL it is, always”')).toBeTruthy()
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-decisions="2"]')).not.toBeNull())
    expect(container.querySelector('[data-fleet-auto-decision="excluded"]')!.textContent).toContain('outward step')
    expect(container.querySelector('[data-fleet-auto-match="yes"]')).not.toBeNull()
    fireEvent.click(container.querySelector('[data-fleet-auto-close]')!)
    expect(container.querySelector('[data-fleet-auto-panel]')).toBeNull()
  })

  it('AC-18: cancel calls the route for that proposal', async () => {
    const calls = stubFetch(STATE, () => ({ ...STATE, pending: [], pending_count: 0 }))
    const { container } = render(<FleetAutoAnswer />)
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-pending-count]')).not.toBeNull())
    fireEvent.click(container.querySelector('[data-fleet-auto-toggle]')!)
    fireEvent.click(container.querySelector(`[data-fleet-auto-cancel="${PENDING.id}"]`)!)
    await waitFor(() => expect(calls.some(c => c.method === 'POST'
      && c.url === `/api/fleet/auto-answer/${encodeURIComponent(PENDING.id)}/cancel`)).toBe(true))
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-pending="0"]')).not.toBeNull())
  })

  it('the switch posts the flipped value', async () => {
    const calls = stubFetch(STATE, (_u, body) => ({ ...STATE, enabled: (body as { enabled: boolean }).enabled }))
    const { container } = render(<FleetAutoAnswer />)
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-toggle="on"]')).not.toBeNull())
    fireEvent.click(container.querySelector('[data-fleet-auto-toggle]')!)
    fireEvent.click(container.querySelector('[data-fleet-auto-switch]')!)
    await waitFor(() => expect(calls.find(c => c.method === 'POST')?.body).toEqual({ enabled: false }))
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-toggle="off"]')).not.toBeNull())
  })
})

describe('the mark on the asking agent', () => {
  it('appears for the session with a pending proposal and nowhere else', () => {
    const { container, rerender } = render(<><FleetAutoAnswerMark sessionId="sess-1" /><FleetAutoAnswerMark sessionId="other" /></>)
    expect(container.querySelector('[data-fleet-auto-mark]')).toBeNull()
    act(() => publishPending(parseAutoAnswerState(STATE)!.pending))
    rerender(<><FleetAutoAnswerMark sessionId="sess-1" /><FleetAutoAnswerMark sessionId="other" /></>)
    const marks = container.querySelectorAll('[data-fleet-auto-mark]')
    expect(marks).toHaveLength(1)
    expect(marks[0].textContent).toContain('auto «TEAL» in 42s')
    expect(pendingFor('other')).toBeNull()
    act(() => publishPending([]))
    expect(container.querySelector('[data-fleet-auto-mark]')).toBeNull()
  })
})

describe('naming the agent the way its tile does (2026-11-24)', () => {
  it('the tile name wins; a session gone from the fleet keeps its logged name, marked', () => {
    publishAgentNames({ 'sess-1': { project: 'proj', label: 'video-orulet' } })
    expect(agentName('sess-1', 'proj · 47f1763f')).toEqual({ project: 'proj', label: 'video-orulet', live: true })
    expect(agentName('gone', 'proj · 47f1763f')).toEqual({ project: 'proj', label: '47f1763f', live: false })
    expect(agentName(null, null, 'proj')).toEqual({ project: 'proj', label: null, live: false })
  })

  it('a continuation shows its summary, not the relay header that repeats the agent', () => {
    const q = '✅ Finished, waiting for the next instruction — set-core · f7306bb0\nWired the decider.\nPick a suggestion or write what it should do next; the session continues with it.'
    expect(questionBody('continuation', q)).toBe('Wired the decider.')
    expect(questionBody('ask', 'Which colour?')).toBe('Which colour?')
    expect(kindLabel('continuation')).toBe('next step')
    expect(shownChoice('→ Report the result')).toBe('Report the result')
    expect(shownChoice('TEAL')).toBe('TEAL')
  })

  it('the panel rows carry the tile name, live', async () => {
    stubFetch()
    publishAgentNames({ 'sess-1': { project: 'proj', label: 'video-orulet' } })
    const { container } = render(<FleetAutoAnswer />)
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-pending-count]')).not.toBeNull())
    fireEvent.click(container.querySelector('[data-fleet-auto-toggle]')!)
    const row = container.querySelector('[data-fleet-auto-row]')!
    expect(row.querySelector('[data-fleet-auto-agent="live"]')!.textContent).toBe('proj · video-orulet')
    await waitFor(() => expect(container.querySelector('[data-fleet-auto-summary]')).not.toBeNull())
    expect(container.querySelector('[data-fleet-auto-summary]')!.textContent).toBe('0 written · 1/2 matched your answer')
  })
})
