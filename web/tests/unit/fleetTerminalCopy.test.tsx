/**
 * Copying out of a terminal — B-65, fourth round.
 *
 * Every previous round passed all its tests and failed a real hand:
 *
 *  - B-60 chose `Ctrl+Shift+C`, which Chrome claims for its inspector, so the
 *    handler never ran.
 *  - B-64 had the panel copy via the clipboard APIs; the async one never
 *    answered and the synchronous one was refused — but that was measured in a
 *    HIDDEN automation tab, a context no reader is ever in.
 *  - B-65 drew the wrong conclusion from that measurement — "let the browser do
 *    the copy" — and the reader refuted it in their own visible tab on
 *    2026-09-01: Ctrl+C and right-click copy BOTH failed on the served, fixed
 *    bundle. The reason was structural: **xterm's selection is not a DOM
 *    selection**, so the browser never had anything to copy; and the
 *    right-button mousedown clears the xterm selection before any menu opens.
 *
 * Round 4: the panel performs the copy itself, synchronously, inside the
 * gesture — from a real keystroke or contextmenu, transient activation is
 * intact, which is the context `execCommand` has always worked in. The
 * properties below are the ones that must survive any rewrite:
 *
 *   1. The copy runs INSIDE the keydown / contextmenu call stack, not after a
 *      timeout — and `copySelection` tries its synchronous write first.
 *   2. The outcome is never silent — success, refusal, or (when the agent owns
 *      the mouse and nothing is selected) the instruction to Shift-drag.
 *   3. The selection is cleared only AFTER the copy's outcome, so the
 *      interrupt stays one keystroke away.
 *   4. A right-click with a selection IS the copy; without one, the browser
 *      menu is left completely alone.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, waitFor } from '@testing-library/react'

let handler: ((e: KeyboardEvent) => boolean) | null = null
let term: any = null
let opened: string[] = []
let execCommand: ReturnType<typeof vi.fn>
let selChange: (() => void) | null = null
let writes: Uint8Array[] = []

vi.mock('@xterm/xterm/css/xterm.css', () => ({}))
vi.mock('@xterm/addon-fit', () => ({ FitAddon: class { fit() { /* geometry is elsewhere */ } } }))
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    cols = 120
    rows = 40
    _sel = ''
    constructor() { term = this }
    // Real xterm creates its `.terminal.xterm` root under the host during
    // open() — before the component reads that element for the mouse-tracking
    // class. The mock must create it too, or the component observes nothing
    // and every mouse-taken assertion measures a mock artifact.
    open(el: HTMLElement) {
      opened.push('open')
      el?.insertAdjacentHTML('beforeend', '<div class="terminal xterm"></div>')
    }
    loadAddon() { /* stubbed */ }
    focus() { /* no keyboard in jsdom */ }
    dispose() { /* nothing to release */ }
    resize() { /* geometry is elsewhere */ }
    write(b: Uint8Array) { writes.push(b) }
    onData() { return { dispose() { /* no listener */ } } }
    attachCustomKeyEventHandler(fn: (e: KeyboardEvent) => boolean) { handler = fn }
    getSelection() { return this._sel }
    // Real xterm fires its selection-change event when the selection clears —
    // the component's pause machinery hangs off that event, so the mock must too.
    clearSelection() { this._sel = ''; selChange?.() }
    onSelectionChange(fn: () => void) { selChange = fn; return { dispose() { /* nothing */ } } }
  },
}))

import FleetTerminal from '../../src/components/FleetTerminal'

class FakeSocket {
  static OPEN = 1
  static last: FakeSocket | null = null
  readyState = 1
  binaryType = ''
  onmessage: ((e: { data: unknown }) => void) | null = null
  onerror: (() => void) | null = null
  onclose: (() => void) | null = null
  constructor() { FakeSocket.last = this }
  send() { /* nothing measured here */ }
  close() { /* nothing to tear down */ }
}

const key = (over: Partial<KeyboardEvent>) =>
  ({ type: 'keydown', ctrlKey: false, shiftKey: false, altKey: false, metaKey: false, key: 'a', ...over }) as KeyboardEvent

const host = () => document.querySelector('[data-fleet-terminal-host]') as HTMLElement

/** A `copy` event shaped the way the browser fires one when it asks who owns the data. */
function fireCopy() {
  const written: Record<string, string> = {}
  const ev = new Event('copy', { bubbles: true, cancelable: true }) as ClipboardEvent
  Object.defineProperty(ev, 'clipboardData', {
    value: { setData: (t: string, v: string) => { written[t] = v } },
  })
  host().dispatchEvent(ev)
  return { ev, written }
}

/** The mouse-tracking class the agent's TUI sets, on the element the component reads. */
function agentTakesTheMouse() {
  host().querySelector('.xterm')!.classList.add('enable-mouse-events')
}

const notice = () => document.querySelector('[data-fleet-terminal-copied]')

beforeEach(async () => {
  handler = null; term = null; opened = []
  selChange = null
  writes = []
  FakeSocket.last = null
  // jsdom does not implement execCommand; the stub stands in for the real
  // browser's synchronous copy. The REFUSAL path flips this to `false`.
  execCommand = vi.fn(() => true)
  document.execCommand = execCommand as unknown as typeof document.execCommand
  vi.stubGlobal('WebSocket', FakeSocket)
  vi.stubGlobal('ResizeObserver', class {
    observe() { /* not this file's subject */ }
    disconnect() { /* nothing observed */ }
  })
  render(<FleetTerminal label="t-1" onClose={() => {}} />)
  await waitFor(() => expect(opened).toContain('open'))
  await waitFor(() => expect(handler).toBeTruthy())
})
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.useRealTimers() })

describe('round 4 — the panel copies, inside the gesture', () => {
  it('copies synchronously during the Ctrl+C keydown, not after a timeout', async () => {
    term._sel = 'the line the reader picked'
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(false)
    // Round 3's refuted pattern was trusting the browser to copy afterwards;
    // the panel now does it while the keystroke's activation is alive.
    expect(execCommand).toHaveBeenCalled()
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
    expect(notice()?.textContent).toContain('26')
  })

  it('clears the selection only AFTER the outcome, so the interrupt comes back', async () => {
    term._sel = 'exactly this'
    handler!(key({ ctrlKey: true, key: 'c' }))
    expect(term.getSelection()).toBe('exactly this')
    await waitFor(() => expect(term.getSelection()).toBe(''))
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(true)
  })

  it('ANNOUNCES a refused synchronous write instead of reporting a copy', async () => {
    execCommand.mockReturnValue(false)
    term._sel = 'doomed to be refused'
    handler!(key({ ctrlKey: true, key: 'c' }))
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('no'))
    expect(notice()!.textContent!.length).toBeGreaterThan(0)
  })

  it('does not reach the clipboard APIs when the synchronous write succeeded', async () => {
    const writeText = vi.fn()
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
    term._sel = 'already on the clipboard'
    handler!(key({ ctrlKey: true, key: 'c' }))
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
    expect(writeText).not.toHaveBeenCalled()
  })
})

describe('the empty-selection Ctrl+C is not silent', () => {
  it('teaches Shift-drag when the agent owns the mouse — and still interrupts', async () => {
    agentTakesTheMouse()
    term._sel = ''
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(true)
    await waitFor(() => expect(notice()?.textContent).toContain('Shift'))
  })

  it('says the interrupt was SENT when the reader owns the mouse', async () => {
    // Changed deliberately in round 5 — this previously asserted silence. A
    // bare Ctrl+C on a long-running agent session is a real act (SIGINT), and
    // an act without a receipt is exactly how a reader confuses "my copy
    // failed" with "nothing happened". The notice is the receipt.
    term._sel = ''
    expect(handler!(key({ ctrlKey: true, key: 'c' }))).toBe(true)
    await waitFor(() => expect(notice()?.textContent).toContain('interrupt'))
  })

  it('carries the round tag on success and failure alike', async () => {
    term._sel = 'tagged'
    handler!(key({ ctrlKey: true, key: 'c' }))
    await waitFor(() => expect(notice()?.textContent).toContain('r5'))
    execCommand.mockReturnValue(false)
    term._sel = 'tagged failure'
    handler!(key({ ctrlKey: true, key: 'c' }))
    await waitFor(() => expect(notice()?.textContent).toContain('not copied'))
    expect(notice()?.textContent).toContain('r5')
  })
})

describe('round 5 — the stream pauses while a selection is held', () => {
  const feed = (bytes: number[]) =>
    FakeSocket.last!.onmessage!({ data: new Uint8Array(bytes).buffer } as unknown as MessageEvent)

  it('queues output while text is selected, and flushes when it clears', async () => {
    term._sel = 'the reader is selecting'
    selChange!()
    feed([104, 105])
    // Nothing written: a write would scroll and destroy the very selection.
    expect(writes).toHaveLength(0)
    await waitFor(() => expect(document.querySelector('[data-fleet-terminal-paused]')).toBeTruthy())
    term._sel = ''
    selChange!()
    expect(writes).toHaveLength(1)
    await waitFor(() => expect(document.querySelector('[data-fleet-terminal-paused]')).toBeNull())
  })

  it('releases the hold on Escape', async () => {
    term._sel = 'held'
    selChange!()
    feed([104])
    expect(writes).toHaveLength(0)
    expect(handler!(key({ key: 'Escape' }))).toBe(false)
    expect(term.getSelection()).toBe('')
    expect(writes).toHaveLength(1)
  })

  it('resumes with an announcement when the pause buffer overflows', async () => {
    vi.useFakeTimers()
    term._sel = 'held against a firehose'
    selChange!()
    feed(new Array(16).fill(120)) // warm the queue
    // Overflow: the component announces BEFORE clearing, and clearing flushes.
    feed(new Array(20).fill(120).map((_, i) => i % 256))
    // (sizes matter, not contents — send the cap itself)
    FakeSocket.last!.onmessage!({ data: new Uint8Array(1_000_001).buffer } as unknown as MessageEvent)
    await vi.advanceTimersByTimeAsync(0)
    vi.useRealTimers()
    await waitFor(() => expect(notice()?.textContent).toContain('output resumed'))
    expect(term.getSelection()).toBe('')
    // The queued bytes were flushed, not dropped: 16 + 20 + 1_000_001 arrived.
    expect(writes).toHaveLength(3)
  })
})

describe('right-click with a selection IS the copy', () => {
  const rightDown = () =>
    host().dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 2 }))
  const contextMenu = () => {
    const ev = new MouseEvent('contextmenu', { bubbles: true, cancelable: true, button: 2 })
    host().dispatchEvent(ev)
    return ev
  }

  it('captures the selection on the way down and copies it, even after the emulator cleared it', async () => {
    term._sel = 'selected before the right-click'
    rightDown()
    // The real emulator clears the selection on mousedown — the reader measured
    // exactly that. The copy must survive the clearing.
    term._sel = ''
    const ev = contextMenu()
    expect(ev.defaultPrevented).toBe(true)
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
    expect(notice()?.textContent).toContain('31')
  })

  it('copies the still-live selection when the emulator did not clear it', async () => {
    term._sel = 'still here'
    const ev = contextMenu()
    expect(ev.defaultPrevented).toBe(true)
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
  })

  it('leaves the browser menu completely alone when nothing is selected', () => {
    term._sel = ''
    const ev = contextMenu()
    expect(ev.defaultPrevented).toBe(false)
    expect(notice()).toBeNull()
  })

  it('does not copy on an ordinary left-click', async () => {
    host().dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, button: 0 }))
    term._sel = ''
    const ev = contextMenu()
    expect(ev.defaultPrevented).toBe(false)
  })
})

describe('the copy event stays as the browser-driven safety net', () => {
  it('hands the terminal selection to the browser and says so', async () => {
    term._sel = 'exactly this'
    const { ev, written } = fireCopy()
    expect(written['text/plain']).toBe('exactly this')
    expect(ev.defaultPrevented).toBe(true)
    await waitFor(() => expect(notice()?.getAttribute('data-fleet-terminal-copied')).toBe('yes'))
    expect(notice()?.textContent).toContain('12')
  })

  it('ignores a copy event when the terminal has nothing selected', () => {
    term._sel = ''
    const { ev, written } = fireCopy()
    // Somebody else on the page owns that copy — taking it would replace their
    // clipboard content with nothing.
    expect(written['text/plain']).toBeUndefined()
    expect(ev.defaultPrevented).toBe(false)
  })
})

describe('the mouse-taken state is standing text, not a hover-only icon', () => {
  it('shows the Shift-drag instruction on the header while the agent owns the mouse', () => {
    agentTakesTheMouse()
    // The MutationObserver reads the class asynchronously; give it a tick.
    return waitFor(() => {
      const chip = document.querySelector('[data-fleet-terminal-mouse-taken="yes"]')
      expect(chip).toBeTruthy()
      // VISIBLE text, not a tooltip: a reader whose drag selected nothing must
      // meet the instruction without hovering anything. This is the assertion
      // the icon-plus-label version could never pass. Shift+drag is the half
      // that must stand visibly — it is the step that fails silently — and it
      // is also the half that fits a narrow dock without truncating; the copy
      // key lives in the tooltip, measurable here.
      expect(chip!.textContent).toContain('Shift+drag')
      expect(chip!.getAttribute('title')).toContain('Ctrl+C')
    })
  })

  it('shows nothing when the reader owns the mouse', async () => {
    agentTakesTheMouse()
    await waitFor(() => expect(
      document.querySelector('[data-fleet-terminal-mouse-taken="yes"]'),
    ).toBeTruthy())
    // Drop the class the way xterm does when the agent's program exits its
    // mouse mode; the chip must go with it, not linger as a stale warning.
    host().querySelector('.xterm')!.classList.remove('enable-mouse-events')
    await waitFor(() => expect(
      document.querySelector('[data-fleet-terminal-mouse-taken="yes"]'),
    ).toBeNull())
  })
})
