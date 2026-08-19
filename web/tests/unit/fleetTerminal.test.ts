/**
 * Which agents may be offered a terminal — task 8.2, asserted in BOTH directions.
 *
 * Task 9.6 states the reason this file is not just the happy path: *a
 * positive-only check passes on a build that offers a terminal for every agent.*
 * So every case below has a partner that must NOT produce an offer, and the two
 * negatives are deliberately different from each other — that difference is the
 * whole finding.
 *
 * The refuted implementation is held here rather than described in a comment: a
 * later simplification to `population === 'started-here' ? offer : 'no terminal'`
 * type-checks, reads as a cleanup, and reintroduces the exact defect. A comment
 * asks to be believed; a test refuses to be reverted.
 */
import { describe, expect, it } from 'vitest'

import {
  FOREIGN_REASON,
  OWNER_DOWN_REASON,
  parseControl,
  terminalOffer,
  terminalUrl,
} from '../../src/lib/fleetTerminal'

describe('a terminal is offered only where one can exist', () => {
  it('offers one for an agent the framework started, addressed by its label', () => {
    const offer = terminalOffer({ population: 'started-here', terminal_label: 'set-core-1120' }, true)
    expect(offer).toEqual({ kind: 'available', label: 'set-core-1120' })
  })

  it('offers none for a foreign agent, and says the reason rather than falling silent', () => {
    const offer = terminalOffer({ population: 'foreign', terminal_label: null }, true)
    expect(offer.kind).toBe('foreign')
    expect(offer.kind === 'foreign' && offer.reason).toBe(FOREIGN_REASON)
  })
})

describe('`unknown` is not `foreign` — the false absence this file exists for', () => {
  /**
   * The load-bearing one. While the owner service restarts, every agent it holds
   * arrives as `unknown`. A surface that reads that as `foreign` states "there is
   * no terminal" about agents that have one — confidently, and only for as long
   * as nobody is looking.
   */
  it('answers `unknown`, never `foreign`, when the owner could not be asked', () => {
    const offer = terminalOffer({ population: 'unknown', terminal_label: null }, false)
    expect(offer.kind).toBe('unknown')
    expect(offer.kind).not.toBe('foreign')
    expect(offer.kind === 'unknown' && offer.reason).toBe(OWNER_DOWN_REASON)
  })

  it('reads an ABSENT population as unknown, because a missing key is not an answer', () => {
    expect(terminalOffer({}).kind).toBe('unknown')
    expect(terminalOffer({ population: null, terminal_label: null }).kind).toBe('unknown')
    // The wrong implementation, held: `population !== 'started-here'` collapses
    // both negatives into one and would answer `foreign` here.
    expect(terminalOffer({}).kind).not.toBe('foreign')
  })

  it('does not turn an unknown into a foreign just because the owner is up', () => {
    // "The owner answered" is not evidence about a process the owner did not
    // list. `ownerReachable` may only change the WORDING.
    const up = terminalOffer({ population: 'unknown', terminal_label: null }, true)
    const down = terminalOffer({ population: 'unknown', terminal_label: null }, false)
    expect(up.kind).toBe('unknown')
    expect(down.kind).toBe('unknown')
    expect(up.kind === 'unknown' && down.kind === 'unknown' && up.reason).not.toBe(down.reason)
  })

  it('treats “ours but no address” as a contradiction, not as an absence', () => {
    // A producer bug. Rendering it as "no terminal" would file the bug as a
    // fact, and the reader would stop looking for the thing that is missing.
    expect(terminalOffer({ population: 'started-here', terminal_label: null }).kind).toBe('unknown')
    expect(terminalOffer({ population: 'started-here', terminal_label: '' }).kind).toBe('unknown')
  })
})

describe('the socket address', () => {
  it('follows the page scheme, so the dev proxy and the installed service both work', () => {
    expect(terminalUrl('a-1', { protocol: 'http:', host: 'localhost:5173' }))
      .toBe('ws://localhost:5173/ws/fleet/agents/a-1/terminal')
    expect(terminalUrl('a-1', { protocol: 'https:', host: 'x.example' }))
      .toBe('wss://x.example/ws/fleet/agents/a-1/terminal')
  })

  it('escapes a label, because a label is user-typed', () => {
    expect(terminalUrl('a b/c', { protocol: 'http:', host: 'h' }))
      .toBe('ws://h/ws/fleet/agents/a%20b%2Fc/terminal')
  })
})

describe('control frames', () => {
  it('parses an acknowledgement', () => {
    const c = parseControl('{"event":"attached","attached":"a","replayed_bytes":12,"replay_truncated":false,"viewers":1}')
    expect(c?.event).toBe('attached')
  })

  it('returns null rather than throwing on anything that is not a control frame', () => {
    // A terminal must never treat garbage as a state change, and throwing inside
    // a socket handler takes the screen down with it.
    expect(parseControl('not json')).toBeNull()
    expect(parseControl('[]')).toBeNull()
    expect(parseControl('{"no":"event"}')).toBeNull()
    expect(parseControl('123')).toBeNull()
  })
})

describe('task 5.5 — an agent the framework started but no longer holds', () => {
  it('is orphaned, not foreign — and carries the scope recovery needs', () => {
    const offer = terminalOffer(
      { population: 'orphaned', terminal_label: null, scope: 'set-agent-mine.scope' }, true)
    expect(offer.kind).toBe('orphaned')
    expect(offer.kind === 'orphaned' && offer.scope).toBe('set-agent-mine.scope')
    // Calling this `foreign` would state that the framework did not start it —
    // which is false, and it hides the one control that helps.
    expect(offer.kind).not.toBe('foreign')
  })

  it('refuses to offer recovery it cannot perform', () => {
    // `orphaned` with no scope is a producer contradiction. An offer whose
    // action cannot be performed is worse than no offer.
    const offer = terminalOffer({ population: 'orphaned', terminal_label: null, scope: null }, true)
    expect(offer.kind).toBe('unknown')
  })

  it('still tells a genuinely foreign session apart', () => {
    const offer = terminalOffer({ population: 'foreign', terminal_label: null, scope: null }, true)
    expect(offer.kind).toBe('foreign')
  })
})
