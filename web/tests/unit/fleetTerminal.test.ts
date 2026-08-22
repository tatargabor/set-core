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
  copySelection,
  isCopyRequest,
  mouseIsTakenByAgent,
  OWNER_DOWN_REASON,
  parseControl,
  terminalLinkTarget,
  terminalOffer,
  terminalUrl,
} from '../../src/lib/fleetTerminal'
import { fileReference } from '../../src/lib/fleetFiles'

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


/**
 * Which links in the output a click may follow — asked for 2026-08-20:
 * *"terminal ablakban URL nyitható legyen uj lapon"*.
 *
 * Asserted in both directions on purpose. A positive-only check passes on a
 * build that opens whatever the agent printed — and the terminal's text is
 * written by whatever the agent ran, so it is data, not an instruction. The
 * negatives below are the ones a prefix test would let through.
 */
describe('a link in the terminal output', () => {
  it('opens an ordinary http and https address', () => {
    expect(terminalLinkTarget('http://127.0.0.1:3301/rendelesek.html'))
      .toBe('http://127.0.0.1:3301/rendelesek.html')
    expect(terminalLinkTarget('https://example.test/a?b=1#c'))
      .toBe('https://example.test/a?b=1#c')
  })

  it('refuses a scheme that would execute something in the dashboard', () => {
    // eslint-disable-next-line no-script-url
    expect(terminalLinkTarget('javascript:alert(1)')).toBeNull()
    expect(terminalLinkTarget('data:text/html,<script>alert(1)</script>')).toBeNull()
    expect(terminalLinkTarget('file:///etc/passwd')).toBeNull()
  })

  it('is not fooled by text that merely STARTS with an allowed scheme', () => {
    // The refuted implementation, held here rather than described: a prefix
    // test on the raw string. `URL` parses the scheme; a prefix does not.
    expect(terminalLinkTarget('  javascript:alert(1)')).toBeNull()
    expect(terminalLinkTarget('httpx://example.test/')).toBeNull()
    expect(terminalLinkTarget('not a url at all')).toBeNull()
  })
})

/**
 * The copy path — B-60, reported 2026-08-22 as *"copy-pase mintha nem mene a
 * terminal ablakokban most"*.
 *
 * The measured cause is two-sided and both sides are asserted here, because
 * fixing either one alone leaves the reader with a terminal that still cannot be
 * copied out of: the agent's TUI owns the mouse (so a plain drag selects
 * nothing), and the emulator swallows `Ctrl+C` into the pty before any browser
 * copy can happen.
 */
describe('copying out of a terminal', () => {
  const key = (over: Partial<KeyboardEvent>) =>
    ({ type: 'keydown', ctrlKey: false, shiftKey: false, metaKey: false, key: 'a', ...over }) as KeyboardEvent

  it('takes Ctrl+Shift+C and Ctrl+Insert as the copy key', () => {
    expect(isCopyRequest(key({ ctrlKey: true, shiftKey: true, key: 'C' }))).toBe(true)
    expect(isCopyRequest(key({ ctrlKey: true, shiftKey: true, key: 'c' }))).toBe(true)
    expect(isCopyRequest(key({ ctrlKey: true, key: 'Insert' }))).toBe(true)
  })

  it('leaves Ctrl+C alone, because in a terminal it is SIGINT', () => {
    // The whole reason the copy key is not the obvious one: these agents are
    // long-running sessions, and an accidental interrupt costs real work. A
    // handler that claimed Ctrl+C would look friendlier and cost more.
    expect(isCopyRequest(key({ ctrlKey: true, key: 'c' }))).toBe(false)
    expect(isCopyRequest(key({ ctrlKey: true, key: 'C' }))).toBe(false)
    // ...and it is a keydown, not a keyup — otherwise one press copies twice.
    expect(isCopyRequest(key({ type: 'keyup', ctrlKey: true, shiftKey: true, key: 'C' }))).toBe(false)
  })

  it('reads whose mouse it is from the emulator, not from a guess', () => {
    const on = document.createElement('div')
    on.className = 'terminal xterm enable-mouse-events focus'
    const off = document.createElement('div')
    off.className = 'terminal xterm focus'
    expect(mouseIsTakenByAgent(on)).toBe(true)
    expect(mouseIsTakenByAgent(off)).toBe(false)
    // An absent element is not a claim that the mouse is free.
    expect(mouseIsTakenByAgent(null)).toBe(false)
  })

  it('says when the clipboard REFUSED the write, instead of reporting a copy', () => {
    // The false-absence shape this guards: a silent failure leaves the previous
    // clipboard content in place, and the reader pastes it somewhere else and
    // finds out much later.
    return Promise.all([
      copySelection('two lines\nof output', async () => {}).then(o =>
        expect(o).toEqual({ ok: true, chars: 19 })),
      copySelection('x', async () => { throw new Error('document is not focused') }).then(o =>
        expect(o).toEqual({ ok: false, reason: 'document is not focused' })),
      // Nothing selected is not a failure and must not be announced as one.
      copySelection('', async () => {}).then(o => expect(o).toBeNull()),
    ])
  })

  it('turns a clipboard that never answers into an answer', async () => {
    // Measured 2026-08-22, which is why this is a test and not a precaution: a
    // `writeText` from a context the browser did not consider focused hung for
    // 45 s and settled never. An unsettled promise announces NOTHING, so the
    // screen would sit silent while the reader believed the copy happened.
    const outcome = await copySelection(
      'never lands',
      () => new Promise<void>(() => { /* the hang, reproduced */ }),
      5,
      (fn, ms) => setTimeout(fn, ms),
    )
    expect(outcome).toEqual({ ok: false, reason: 'the clipboard did not answer' })
  })
})

/**
 * THE URL PATH IS UNTOUCHED — the regression the file links could have caused.
 *
 * Two link providers now sit on the same terminal: the addon that opens an
 * address in a new tab, and the one that opens a project file in the panel. The
 * hazard is not that either is wrong on its own corpus; it is that the file one
 * is hungrier. It splits on `:` to find a line number, and every URL contains a
 * `:` — so a build where the file provider answered first would turn
 * `http://host/a.ts:12` into a file open, and `javascript:alert(1)` into a token
 * it is at least willing to CONSIDER.
 *
 * So the two verdicts are asserted together, on one corpus: whatever the URL
 * path takes, the file path must refuse.
 */
describe('the file links did not take the URL path', () => {
  const root = '/home/x/proj'
  // Deliberately hostile: the known set contains exactly the names a URL's tail
  // would produce if the split were believed without checking the path part.
  const known = new Set(['a.ts', 'rendelesek.html', 'alert(1)'])

  it('leaves an http address to the tab-opening path', () => {
    expect(terminalLinkTarget('http://127.0.0.1:3301/rendelesek.html'))
      .toBe('http://127.0.0.1:3301/rendelesek.html')
    expect(fileReference('http://127.0.0.1:3301/rendelesek.html', root, known)).toBeNull()
  })

  it('does not read a URL port or a fragment as a line number', () => {
    expect(fileReference('http://example.test/a.ts:12', root, known)).toBeNull()
    expect(fileReference('https://example.test:8080/a.ts', root, known)).toBeNull()
  })

  it('opens NOWHERE for a scheme that would execute something', () => {
    // eslint-disable-next-line no-script-url
    expect(terminalLinkTarget('javascript:alert(1)')).toBeNull()
    // eslint-disable-next-line no-script-url
    expect(fileReference('javascript:alert(1)', root, known)).toBeNull()
    expect(fileReference('file:///etc/passwd', root, known)).toBeNull()
  })

  it('still opens a genuine project path, so the refusals above are not blanket', () => {
    // Without this the block would pass on a file provider that answers `null`
    // to everything — a check that cannot fail in the direction that matters.
    expect(fileReference('a.ts:12', root, known)).toEqual({ path: 'a.ts', line: 12 })
  })
})
