/**
 * The question relay's header control — the mode, when the switch may flip, what it says,
 * and the waiting order.
 */
import { describe, expect, it } from 'vitest'
import { canFlip, orderWaiting, parseRelayState, relayMode, relayTitle, sendable, setupCommands, showUnwired, verdictLine, type RelayState } from '../../src/lib/fleetRelay'

const state = (over: Partial<RelayState> = {}): RelayState =>
  ({ enabled: false, target: 'command', missing: [], ready: true, waiting: [], unwired: [], ...over })

describe('relayMode', () => {
  it('names the four states, including on-but-not-configured', () => {
    expect(relayMode(state())).toBe('off')
    expect(relayMode(state({ enabled: true }))).toBe('on')
    expect(relayMode(state({ ready: false, missing: ['question_relay.audience'] }))).toBe('not-ready')
    expect(relayMode(state({ enabled: true, ready: false, missing: ['question_relay.audience'] }))).toBe('on-not-ready')
  })
})

describe('canFlip (AC-10, AC-11)', () => {
  it('turns a ready relay on, and always allows turning it off', () => {
    expect(canFlip(state())).toBe(true)
    expect(canFlip(state({ enabled: true, ready: false }))).toBe(true)
  })
  it('does not turn on an incomplete relay', () => {
    expect(canFlip(state({ ready: false, missing: ['question_relay.audience'] }))).toBe(false)
  })
})

describe('relayTitle', () => {
  it('names the missing keys when not ready', () => {
    expect(relayTitle(state({ ready: false, missing: ['question_relay.audience'] }))).toContain('question_relay.audience')
  })
  it('says a webhook is notify-only', () => {
    expect(relayTitle(state({ target: 'webhook' }))).toContain('notify only')
  })
  it('does not call an on-but-broken relay calm', () => {
    expect(relayTitle(state({ enabled: true, ready: false, missing: ['question_relay.target'] })))
      .toContain('released to the terminal')
  })
})

describe('setupCommands', () => {
  it('gives one set-config line per missing key', () => {
    const lines = setupCommands(state({ ready: false, missing: ['question_relay.command', 'question_relay.audience'] }))
    expect(lines).toHaveLength(2)
    expect(lines.every(l => l.startsWith('set-config set question_relay.'))).toBe(true)
  })
})

describe('orderWaiting (AC-12)', () => {
  it('lists the longest-waiting first and keeps every entry', () => {
    const w = (id: string, seconds: number | null) =>
      ({ session_id: id, project: 'p', questions: 1, target: 'command', seconds, release_requested: false })
    expect(orderWaiting([w('a', 10), w('b', 300), w('c', null)]).map(x => x.session_id)).toEqual(['b', 'a', 'c'])
  })
})

describe('parseRelayState', () => {
  it('refuses a payload without the arrays it renders — the shape that crashed the page', () => {
    expect(parseRelayState({ agents: [], projects: [] })).toBeNull()
    expect(parseRelayState({ enabled: true, ready: true, missing: [] })).toBeNull()
    expect(parseRelayState(null)).toBeNull()
  })
  it('keeps a well-formed answer', () => {
    const s = parseRelayState({ enabled: true, ready: true, target: 'command', missing: [],
      waiting: [{ session_id: 'a', project: 'p', questions: 1, target: 'command', seconds: 3, release_requested: false }, 'junk'] })
    expect(s?.waiting).toHaveLength(1)
  })
})

describe('unwired projects (B-182)', () => {
  const bare = { project: 'hand-authored', missing: ['set-hook-question-relay', 'set-hook-wait-detect'] }

  it('marks the closed header only while the relay is on', () => {
    expect(showUnwired(state({ enabled: true, unwired: [bare] }))).toBe(true)
    expect(showUnwired(state({ enabled: false, unwired: [bare] }))).toBe(false)
    expect(showUnwired(state({ enabled: true }))).toBe(false)
  })

  it('does not call an on relay calm while a project bypasses it', () => {
    const title = relayTitle(state({ enabled: true, unwired: [bare] }))
    expect(title).toMatch(/not wired/)
    expect(title).not.toMatch(/blocking questions go to/)
  })

  it('parses the list, and an older server without it as empty — never a crash', () => {
    const base = { enabled: true, ready: true, target: 'command', missing: [], waiting: [] }
    expect(parseRelayState({ ...base, unwired: [bare, { nope: 1 }] })?.unwired).toEqual([bare])
    expect(parseRelayState(base)?.unwired).toEqual([])
  })
})

describe('the decider verdict on a waiting row (fleet-auto-answer, 2026-11-24)', () => {
  const base = { state: 'forwarded', outcome: null, reason: '', choice: null, tier: null, seconds_left: null }
  it('says why nothing will be written, and what it would have proposed', () => {
    expect(verdictLine(null)).toBeNull()
    expect(verdictLine({ ...base, outcome: 'excluded', reason: 'outward step: delete', choice: '→ Check the replies' }))
      .toEqual({ text: 'auto: not written — outward step: delete; it proposed «Check the replies»', tone: 'held' })
    expect(verdictLine({ ...base, outcome: 'no-decision' })!.tone).toBe('muted')
  })
  it('a due proposal carries its countdown, a cancelled one does not', () => {
    expect(verdictLine({ ...base, state: 'proposed', outcome: 'allowed', choice: 'TEAL', seconds_left: 41.6 })!.text)
      .toBe('auto: writes «TEAL» in 42s')
    expect(verdictLine({ ...base, state: 'cancelled', outcome: 'allowed', choice: 'TEAL' })!.text)
      .toBe('auto: cancelled — waits for you')
  })
})

describe('the send-the-proposal button (2026-11-24)', () => {
  const w = { id: 'relay-x', session_id: 's', project: 'p', questions: 1, target: 'command', seconds: 5, release_requested: false }
  const v = { state: 'forwarded', outcome: 'excluded', reason: 'outward step: publish', choice: '→ Install both', tier: 'decided', seconds_left: null }
  it('offers an excluded proposal, stripped of its arrow, and a due one as "send now"', () => {
    expect(sendable({ ...w, auto_answer: v })).toEqual({ id: 'relay-x', choice: 'Install both', label: 'send it' })
    expect(sendable({ ...w, auto_answer: { ...v, outcome: 'allowed', state: 'proposed', seconds_left: 30 } })!.label).toBe('send now')
  })
  it('offers nothing without a proposal, an id, or while releasing', () => {
    expect(sendable({ ...w, auto_answer: { ...v, choice: null } })).toBeNull()
    expect(sendable({ ...w, id: null, auto_answer: v })).toBeNull()
    expect(sendable({ ...w, release_requested: true, auto_answer: v })).toBeNull()
    expect(sendable({ ...w, auto_answer: null })).toBeNull()
  })
})
