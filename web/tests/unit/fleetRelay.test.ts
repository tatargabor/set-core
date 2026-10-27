/**
 * The question relay's header control — the mode, when the switch may flip, what it says,
 * and the waiting order.
 */
import { describe, expect, it } from 'vitest'
import { canFlip, orderWaiting, parseRelayState, relayMode, relayTitle, setupCommands, type RelayState } from '../../src/lib/fleetRelay'

const state = (over: Partial<RelayState> = {}): RelayState =>
  ({ enabled: false, target: 'command', missing: [], ready: true, waiting: [], ...over })

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
